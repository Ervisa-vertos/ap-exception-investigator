"""Model clients. Choose with MODEL_PROVIDER (or --provider).

- scripted : offline, deterministic stand-in for an LLM (tests, CI, demos without a key). €0.
- ollama   : a local model via Ollama (free, offline; slow on CPU).
- foundry  : Microsoft Foundry project deployment. Keyless via `az login` / managed identity.

The scripted model is a *test double*: it follows the investigation playbook a good model
should follow, reading only tool outputs. Eval numbers produced with it test the pipeline
(tools, ledger, Reviewer, gate, metrics), not model intelligence. Run evals with a real
provider for real numbers.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, Content, FunctionInvocationLayer, Message

from .domain import CAUSE_PRIORITY, PRICE_TOLERANCE_PCT, APPROVAL_LIMIT_EUR, BANK_CHANGE_WINDOW_DAYS
from .domain import NextStep as NS
from .domain import RootCause as RC


def make_client(provider: str | None = None):
    provider = (provider or os.getenv("MODEL_PROVIDER", "scripted")).lower()
    if provider == "scripted":
        return ScriptedInvestigatorClient()
    if provider == "ollama":
        from agent_framework_ollama import OllamaChatClient  # pip install agent-framework-ollama

        return OllamaChatClient(model=os.getenv("OLLAMA_MODEL", "qwen3:8b"))
    if provider == "foundry":
        from agent_framework_foundry import FoundryChatClient
        from azure.identity import DefaultAzureCredential

        return FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL"],
            credential=DefaultAzureCredential(),  # az login locally, managed identity in Azure
        )
    raise ValueError(f"Unknown MODEL_PROVIDER '{provider}'. Use scripted, ollama or foundry.")


# ----------------------------------------------------------------------------- helpers
def _text(m: Message) -> str:
    return " ".join(c.text for c in m.contents if c.type == "text" and c.text)


def _payload(c: Content) -> Any:
    if c.exception:
        return {"__error__": str(c.exception)}
    r = c.result
    if isinstance(r, list) and r and hasattr(r[0], "type"):
        r = getattr(r[0], "text", None) or getattr(r[0], "result", None)
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except ValueError:
            return {"__error__": r}  # framework error text, e.g. "Error: Function failed..."
    return r if isinstance(r, dict) else {"__error__": str(r)}


def _call(name: str, args: dict) -> Message:
    return Message(role="assistant", contents=[
        Content.from_function_call(call_id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=args)])


def _say(text: str) -> Message:
    return Message(role="assistant", contents=[Content.from_text(text)])


POLICY_QUERY = {
    RC.QTY_MISMATCH: "invoiced quantity greater than received quantity",
    RC.PRICE_VARIANCE: "unit price above purchase order price tolerance",
    RC.MISSING_RECEIPT: "no goods receipt posted",
    RC.DUPLICATE_INVOICE: "duplicate invoice same vendor invoice number",
    RC.VENDOR_ON_HOLD: "vendor on hold no invoice may be paid",
    RC.BANK_ACCOUNT_CHANGE: "recent bank account change fraud review",
    RC.APPROVAL_MISSING: "invoice approval limit over 25,000",
    RC.CURRENCY_TAX_MISMATCH: "currency or tax code mismatch",
    RC.EINVOICE_VALIDATION_FAILED: "e-invoice validation failure EN 16931 Peppol rejection",
}
EXPECTED_SECTION = {
    RC.QTY_MISMATCH: "AP-POL-01 §2.2", RC.PRICE_VARIANCE: "AP-POL-01 §3.1", RC.MISSING_RECEIPT: "AP-POL-01 §2.3",
    RC.DUPLICATE_INVOICE: "AP-POL-02 §2.1", RC.VENDOR_ON_HOLD: "AP-POL-06 §2.1",
    RC.BANK_ACCOUNT_CHANGE: "AP-POL-03 §2.1", RC.APPROVAL_MISSING: "AP-POL-04 §2.1",
    RC.CURRENCY_TAX_MISMATCH: "AP-POL-05 §2.1", RC.EINVOICE_VALIDATION_FAILED: "AP-POL-07 §2.1",
}
STEP_FOR = {
    RC.QTY_MISMATCH: NS.WAIT_FOR_RECEIPT, RC.PRICE_VARIANCE: NS.BUYER_PRICE_APPROVAL,
    RC.MISSING_RECEIPT: NS.CONTACT_RECEIVING, RC.DUPLICATE_INVOICE: NS.REJECT_DUPLICATE,
    RC.VENDOR_ON_HOLD: NS.CONTACT_VENDOR_MANAGEMENT, RC.BANK_ACCOUNT_CHANGE: NS.ESCALATE_FRAUD_REVIEW,
    RC.APPROVAL_MISSING: NS.ROUTE_FOR_APPROVAL, RC.CURRENCY_TAX_MISMATCH: NS.REQUEST_CORRECTED_INVOICE,
    RC.EINVOICE_VALIDATION_FAILED: NS.REJECT_EINVOICE_VIA_PLATFORM,
}
STEP_TEXT = {
    NS.WAIT_FOR_RECEIPT: "Ask the buyer to confirm the open delivery; match the invoice once the rest is received",
    NS.PARTIAL_MATCH_PAY_RECEIVED: "With buyer agreement, partially match and pay only the received quantity",
    NS.REQUEST_CREDIT_NOTE: "Request a credit note from the vendor for the difference",
    NS.BUYER_PRICE_APPROVAL: "Ask the buyer to approve the new price and amend the PO, or request a credit note",
    NS.CONTACT_RECEIVING: "Ask the warehouse/requester to confirm receipt and post the goods receipt",
    NS.REJECT_DUPLICATE: "Reject the duplicate and tell the vendor the original was already processed",
    NS.CONTACT_VENDOR_MANAGEMENT: "Contact vendor management, who own the vendor-level hold",
    NS.ESCALATE_FRAUD_REVIEW: "Escalate to fraud review; verify the bank change by callback to the number on file. Do not pay",
    NS.ROUTE_FOR_APPROVAL: "Remind/route the budget owner to approve in the workflow",
    NS.REQUEST_CORRECTED_INVOICE: "Request a corrected invoice from the vendor",
    NS.REJECT_EINVOICE_VIA_PLATFORM: "Reject the e-invoice via the platform citing the failed rule; vendor must re-issue",
    NS.NO_ACTION: "Nothing to do",
    NS.RETRY_LATER: "Retry later",
}
_INV_RE = re.compile(r"INV-\d{4}")


class ScriptedInvestigatorClient(FunctionInvocationLayer, BaseChatClient):
    """Deterministic stand-in for the Investigator LLM. See module docstring."""

    OTEL_PROVIDER_NAME = "scripted"

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):  # type: ignore[override]
        if stream:
            raise NotImplementedError("ScriptedInvestigatorClient supports non-streaming runs only.")
        return ChatResponse(messages=[self._decide(list(messages))], response_id=str(uuid.uuid4()))

    # ---- playbook ---------------------------------------------------------------------
    def _decide(self, messages: list[Message]) -> Message:
        first_user = next(m for m in messages if m.role == "user")
        brief = _text(first_user)
        invoice_id = _INV_RE.search(brief).group(0)

        calls: dict[str, str] = {}
        results: dict[tuple, Any] = {}
        for m in messages:
            for c in m.contents:
                if c.type == "function_call":
                    args = c.arguments if isinstance(c.arguments, dict) else json.loads(c.arguments or "{}")
                    calls[c.call_id] = (c.name, json.dumps(args, sort_keys=True))
                elif c.type == "function_result" and c.call_id in calls:
                    results[calls[c.call_id]] = _payload(c)

        def got(name: str, **args):
            return results.get((name, json.dumps(args, sort_keys=True)))

        def need(name: str, **args):
            return got(name, **args) is None

        if need("get_invoice", invoice_id=invoice_id):
            return _call("get_invoice", {"invoice_id": invoice_id})
        inv = got("get_invoice", invoice_id=invoice_id)
        if "__error__" in inv:
            return _say(self._undetermined(invoice_id, inv["__error__"]))

        plan = []
        if inv.get("po_id"):
            plan.append(("get_matching_details", {"invoice_id": invoice_id}))
        plan += [("find_similar_invoices", {"invoice_id": invoice_id}),
                 ("get_vendor", {"vendor_id": inv["vendor_id"]}),
                 ("get_vendor_change_log", {"vendor_id": inv["vendor_id"]}),
                 ("get_vendor_messages", {"invoice_id": invoice_id})]
        if inv["status"] != "on_hold":
            plan = []
        for name, args in plan:
            if need(name, **args):
                return _call(name, args)
            if "__error__" in got(name, **args):
                return _say(self._undetermined(invoice_id, got(name, **args)["__error__"]))

        causes, evidence = self._analyse(inv, {n: got(n, **a) for n, a in plan})
        for rc in causes:
            if rc in POLICY_QUERY and need("search_policy", query=POLICY_QUERY[rc]):
                return _call("search_policy", {"query": POLICY_QUERY[rc]})

        citations = []
        for rc in causes:
            if rc not in POLICY_QUERY:
                continue
            hits = got("search_policy", query=POLICY_QUERY[rc]).get("results", [])
            hit = next((h for h in hits if h["section_id"] == EXPECTED_SECTION[rc]), hits[0] if hits else None)
            if hit:
                citations.append({"policy_section": hit["section_id"], "quote": hit["text"].split(". ")[0][:200]})
        return _say(json.dumps(self._answer(invoice_id, inv, causes, evidence, citations, brief)))

    # ---- reasoning over tool outputs (what a good model should conclude) ------------
    @staticmethod
    def _analyse(inv: dict, r: dict) -> tuple[list[RC], list[dict]]:
        inv_id = inv["invoice_id"]
        if inv["status"] != "on_hold":
            return [RC.NOT_ON_HOLD], [{"record_id": inv_id, "fact": f"Status is '{inv['status']}', no hold."}]
        causes: list[RC] = []
        ev: list[dict] = []
        m = r.get("get_matching_details")
        if m and m.get("lines"):
            for ln in m["lines"]:
                if ln["received_qty"] == 0:
                    causes.append(RC.MISSING_RECEIPT)
                    ev.append({"record_id": m["po_id"], "fact": f"PO line {ln['po_line']}: no goods receipt posted; "
                                                                 f"{ln['invoiced_qty']:g} invoiced."})
                elif ln["received_qty"] < ln["invoiced_qty"]:
                    causes.append(RC.QTY_MISMATCH)
                    rid = m["receipt_ids"][0] if m["receipt_ids"] else m["po_id"]
                    ev.append({"record_id": rid, "fact": f"PO line {ln['po_line']}: received {ln['received_qty']:g}, "
                                                         f"invoiced {ln['invoiced_qty']:g}."})
                if (ln["price_variance_pct"] or 0) > PRICE_TOLERANCE_PCT:
                    causes.append(RC.PRICE_VARIANCE)
                    ev.append({"record_id": m["po_id"], "fact": f"Unit price {ln['invoice_unit_price']} vs PO "
                               f"{ln['po_unit_price']} (+{ln['price_variance_pct']}%, tolerance {PRICE_TOLERANCE_PCT}%)."})
                if ln["po_tax_code"] != ln["invoice_tax_code"]:
                    causes.append(RC.CURRENCY_TAX_MISMATCH)
                    ev.append({"record_id": m["po_id"], "fact": f"Tax code {ln['invoice_tax_code']} on invoice vs "
                                                                 f"{ln['po_tax_code']} on PO."})
            if m["po_currency"] != m["invoice_currency"]:
                causes.append(RC.CURRENCY_TAX_MISMATCH)
                ev.append({"record_id": m["po_id"], "fact": f"Invoice currency {m['invoice_currency']} vs PO "
                                                             f"{m['po_currency']}."})
        dup = r.get("find_similar_invoices") or {}
        for h in dup.get("matches", []):
            causes.append(RC.DUPLICATE_INVOICE)
            ev.append({"record_id": h["invoice_id"], "fact": f"Same vendor invoice no. {dup['vendor_invoice_no']}, "
                                                             f"status {h['status']}."})
        v = r.get("get_vendor") or {}
        if v.get("on_hold"):
            causes.append(RC.VENDOR_ON_HOLD)
            ev.append({"record_id": v["vendor_id"], "fact": f"Vendor on hold: {v['hold_reason']}."})
        for ch in (r.get("get_vendor_change_log") or {}).get("changes", []):
            if ch["field"] == "bank_account" and not ch["callback_verified"] and ch["days_ago"] <= BANK_CHANGE_WINDOW_DAYS:
                causes.append(RC.BANK_ACCOUNT_CHANGE)
                ev.append({"record_id": ch["change_id"], "fact": f"Bank account changed {ch['days_ago']} days ago via "
                                                                 f"{ch['requested_via']}, not callback-verified."})
        if inv["total_amount"] > APPROVAL_LIMIT_EUR and inv["approval_status"] == "pending":
            causes.append(RC.APPROVAL_MISSING)
            ev.append({"record_id": inv_id, "fact": f"Total {inv['total_amount']:,.2f} {inv['currency']} is above the "
                                                     f"limit and approval is pending."})
        if inv.get("einvoice_status") == "validation_failed":
            causes.append(RC.EINVOICE_VALIDATION_FAILED)
            rules = ", ".join(e["rule"] for e in inv["einvoice_errors"])
            ev.append({"record_id": inv_id, "fact": f"{inv['channel']} e-invoice failed validation: {rules}."})
        uniq = list(dict.fromkeys(causes)) or [RC.UNDETERMINED]
        uniq.sort(key=lambda c: CAUSE_PRIORITY.index(c) if c in CAUSE_PRIORITY else 99)
        return uniq, ev

    @staticmethod
    def _answer(invoice_id, inv, causes, evidence, citations, brief) -> dict:
        if causes == [RC.NOT_ON_HOLD]:
            steps = [NS.NO_ACTION]
        elif causes == [RC.UNDETERMINED]:
            steps = [NS.RETRY_LATER]
        else:
            steps = list(dict.fromkeys(STEP_FOR[c] for c in causes if c in STEP_FOR))
        names = ", ".join(c.value.replace("_", " ").lower() for c in causes)
        proposed = None
        if "intent: release_hold" in brief:
            proposed = {"action": "release_hold", "amount": None, "justification": "User requested release."}
        return {
            "invoice_id": invoice_id,
            "on_hold": inv["status"] == "on_hold",
            "root_causes": [c.value for c in causes],
            "summary": (f"{invoice_id} from {inv['vendor_name']} is not on hold (status {inv['status']})."
                        if causes == [RC.NOT_ON_HOLD] else
                        f"{invoice_id} from {inv['vendor_name']} ({inv['total_amount']:,.2f} {inv['currency']}) is on "
                        f"hold because of: {names}."),
            "evidence": evidence,
            "citations": citations,
            "next_steps": [s.value for s in steps],
            "next_steps_explained": ". ".join(f"{i}) {STEP_TEXT[s]}" for i, s in enumerate(steps, 1)) + ".",
            "proposed_action": proposed,
            "confidence": "high",
        }

    @staticmethod
    def _undetermined(invoice_id: str, error: str) -> str:
        return json.dumps({
            "invoice_id": invoice_id, "on_hold": True, "root_causes": [RC.UNDETERMINED.value],
            "summary": f"I could not complete the investigation of {invoice_id}: {error}",
            "evidence": [], "citations": [], "next_steps": [NS.RETRY_LATER.value],
            "next_steps_explained": "The ERP did not respond. Try again later; no data was guessed.",
            "proposed_action": None, "confidence": "low",
        })
