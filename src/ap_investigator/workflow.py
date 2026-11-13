"""Code-defined workflow (ADR-001): Triage [code] → Investigator [LLM] ⇄ Reviewer [code+LLM] → Respond.

The model never decides the route. Triage handles everything that does not need a model
(bad input, out-of-scope requests, permissions, invoices not on hold, ERP outages) so
those cost nothing and cannot be talked around. Consequential actions are not executed
here: the outcome carries an ActionRequest that the caller passes to `gate.execute`
together with a human approver.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from agent_framework import Agent, AgentSession, Executor, WorkflowBuilder, WorkflowContext, handler
from typing_extensions import Never

from .agents.investigator import build_investigator
from .agents.reviewer import build_llm_reviewer, deterministic_review, feedback_message, llm_review
from .config import MAX_REVIEW_ROUNDS
from .domain import NextStep, RootCause
from .erp import repo
from .ledger import Ledger, ledger_middleware
from .models import ActionRequest, Evidence, Investigation, Outcome, Review, ReviewIssue
from .security import NotAuthorizedError, Principal, require

INVOICE_RE = re.compile(r"\bINV-\d{4}\b", re.IGNORECASE)
LOOSE_INVOICE_RE = re.compile(r"\binvoice\s*(?:no\.?|number|#)?\s*(\d{4})\b", re.IGNORECASE)

OUT_OF_SCOPE = [
    (re.compile(r"^\s*(please\s+)?(pay|wire|transfer|remit)\b|\b(can|could|would) you\s+(please\s+)?(pay|wire|transfer)\b",
                re.I),
     "I can't make or schedule payments. I only investigate holds and recommend next steps."),
    (re.compile(r"\b(change|update|set|replace)\b.{0,40}\b(bank|iban|account (number|details))\b", re.I),
     "I can't change vendor bank details. Bank changes go through vendor master data with callback "
     "verification (AP-POL-03 §2.2)."),
    (re.compile(r"\b(full|unmasked|complete)\b.{0,30}\b(iban|bank|account)\b", re.I),
     "Bank account numbers are only shown masked (AP-SEC-01 §1.3)."),
]

# A question ABOUT an action ("Should I release…?", "Who can release…?") is not a request to DO it.
ASKING_ABOUT = re.compile(
    r"^\s*(why|who|how|when|whether|should)\b"
    r"|^\s*(can|could|may|is|was|has)\s+(i|we|it|the|this|that|anyone|someone)\b",
    re.IGNORECASE,
)
	


def parse_intent(question: str) -> str:
    q = question.lower()
    if ASKING_ABOUT.search(q):
        return "investigate"
    if re.search(r"\b(release|unblock|lift)\b.{0,30}\bhold\b|\brelease\b.{0,10}\binv-", q):
        return "release_hold"
    if re.search(r"\b(request|raise|create|send)\b.{0,20}\bcredit note\b", q):
        return "request_credit_note"
    return "investigate"


# ----------------------------------------------------------------------------- messages
@dataclass
class RunState:
    question: str
    principal: Principal
    invoice_id: str | None = None
    intent: str = "investigate"
    ledger: Ledger = field(default_factory=Ledger)
    session: AgentSession | None = None
    draft: Investigation | None = None
    review: Review | None = None
    rounds: int = 0
    pending_feedback: str | None = None
    status: str = "answered"
    message: str | None = None


@dataclass
class Investigate:
    state: RunState


@dataclass
class Draft:
    state: RunState


@dataclass
class Final:
    state: RunState


# ----------------------------------------------------------------------------- executors
class Triage(Executor):
    @handler
    async def run(self, state: RunState, ctx: WorkflowContext[Investigate | Final]) -> None:
        def finish(status: str, message: str) -> Final:
            state.status, state.message = status, message
            return Final(state)

        try:
            require("investigate", state.principal)
        except NotAuthorizedError as exc:
            return await ctx.send_message(finish("refused", str(exc)))

        for rx, answer in OUT_OF_SCOPE:
            if rx.search(state.question) and parse_intent(state.question) == "investigate":
                return await ctx.send_message(finish("refused", answer))

        m = INVOICE_RE.search(state.question)
        loose = LOOSE_INVOICE_RE.search(state.question)
        if m:
            state.invoice_id = m.group(0).upper()
        elif loose:
            state.invoice_id = f"INV-{loose.group(1)}"
        else:
            return await ctx.send_message(finish("clarify", "Which invoice should I look at? Please give an invoice "
                                                            "number like INV-1001."))
        state.intent = parse_intent(state.question)

        try:
            inv = repo.get_invoice(state.invoice_id)
        except repo.RecordNotFoundError as exc:
            return await ctx.send_message(finish("answered", f"{exc} Please check the number."))
        except repo.ERPUnavailableError as exc:
            return await ctx.send_message(finish("error", f"I couldn't reach the ERP: {exc} Nothing was guessed."))
        state.ledger.add("triage.get_invoice", {"invoice_id": state.invoice_id}, inv)

        if inv["status"] != "on_hold" and state.intent == "investigate":
            state.draft = Investigation(
                invoice_id=state.invoice_id, on_hold=False, root_causes=[RootCause.NOT_ON_HOLD],
                summary=f"{state.invoice_id} ({inv['vendor_name']}) is not on hold. Its status is '{inv['status']}'.",
                evidence=[Evidence(record_id=state.invoice_id, fact=f"status = {inv['status']}")],
                citations=[], next_steps=[NextStep.NO_ACTION], next_steps_explained="Nothing to do.",
                proposed_action=None, confidence="high")
            return await ctx.send_message(Final(state))

        await ctx.send_message(Investigate(state))


class Investigator(Executor):
    def __init__(self, agent: Agent, **kw: Any):
        super().__init__(**kw)
        self.agent = agent

    @handler
    async def run(self, msg: Investigate, ctx: WorkflowContext[Draft]) -> None:
        s = msg.state
        if s.session is None:
            s.session = self.agent.create_session()
            inv = s.ledger.calls[0].output
            prompt = (f"Question from {s.principal.user} ({', '.join(sorted(s.principal.roles))}): {s.question}\n"
                      f"Triage: invoice {s.invoice_id}; status {inv['status']}; hold code {inv['hold_code']}; "
                      f"vendor {inv['vendor_id']}; PO {inv['po_id']}; intent: {s.intent}.")
        else:
            prompt = s.pending_feedback or "Return the corrected JSON."
        try:
            resp = await self.agent.run(prompt, session=s.session, options={"response_format": Investigation},
                                        middleware=[ledger_middleware(s.ledger)])
            s.draft = _parse(resp)
        except Exception as exc:  # model/API failure: never invent an answer
            s.draft = None
            s.status, s.message = "error", f"The model call failed: {type(exc).__name__}: {exc}"
        await ctx.send_message(Draft(s))


class Reviewer(Executor):
    def __init__(self, enabled: bool, llm: Agent | None, **kw: Any):
        super().__init__(**kw)
        self.enabled, self.llm = enabled, llm

    @handler
    async def run(self, msg: Draft, ctx: WorkflowContext[Investigate | Final]) -> None:
        s = msg.state
        if s.status == "error" or not self.enabled:
            return await ctx.send_message(Final(s))
        if s.draft is None:
            issues = [ReviewIssue(kind="malformed_output", detail="The draft was not valid JSON for the schema.")]
        else:
            issues = deterministic_review(s.draft, s.ledger, user_requested_action=s.intent != "investigate")
            if self.llm is not None and not issues:
                issues += await llm_review(self.llm, s.draft, s.ledger)
        s.review = Review(approved=not issues, issues=issues)
        if issues and s.rounds < MAX_REVIEW_ROUNDS:
            s.rounds += 1
            s.pending_feedback = feedback_message(issues)
            return await ctx.send_message(Investigate(s))
        if issues:
            s.status = "needs_human_review" if s.draft else "error"
        await ctx.send_message(Final(s))


class Respond(Executor):
    @handler
    async def run(self, msg: Final, ctx: WorkflowContext[Never, Outcome]) -> None:
        s = msg.state
        action = None
        if s.draft and s.intent in ("release_hold", "request_credit_note"):
            amount = s.draft.proposed_action.amount if s.draft.proposed_action else None
            action = ActionRequest(action=s.intent, invoice_id=s.invoice_id, amount=amount,
                                   justification=f"Requested by {s.principal.user}: {s.question}")
        await ctx.yield_output(Outcome(
            status=s.status, question=s.question, message=s.message or render(s.draft, s.review),
            investigation=s.draft, review=s.review, review_rounds=s.rounds, action_request=action,
            records_retrieved=sorted(s.ledger.records), policy_sections_retrieved=sorted(s.ledger.policy_sections),
            tool_calls=s.ledger.tool_names, injection_flags=sorted(s.ledger.injection_flags),
        ))


def _parse(resp) -> Investigation | None:
    if isinstance(resp.value, Investigation):
        return resp.value
    text = resp.text or ""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return Investigation.model_validate(json.loads(m.group(0))) if m else None
    except (ValueError, TypeError):
        return None


def render(inv: Investigation | None, review: Review | None) -> str:
    if inv is None:
        return "No answer could be produced."
    lines = [inv.summary, ""]
    if inv.root_causes and inv.root_causes != [RootCause.NOT_ON_HOLD]:
        lines.append("Causes: " + ", ".join(c.value for c in inv.root_causes))
    for e in inv.evidence:
        lines.append(f"  - [{e.record_id}] {e.fact}")
    for c in inv.citations:
        lines.append(f'  > {c.policy_section}: "{c.quote}"')
    lines.append("Next steps: " + " → ".join(s.value for s in inv.next_steps))
    lines.append(inv.next_steps_explained)
    if review and not review.approved:
        lines.append("\n! Reviewer could not verify this answer — needs human review:")
        lines += [f"  - [{i.kind}] {i.detail}" for i in review.issues]
    return "\n".join(lines)


# ----------------------------------------------------------------------------- entry point
async def investigate(
    question: str,
    principal: Principal,
    *,
    provider: str | None = None,
    reviewer: bool = True,
    llm_reviewer: bool | None = None,
    investigator: Agent | None = None,
    tools: list | None = None,
) -> Outcome:
    """Run one investigation. `llm_reviewer` defaults to on for real models, off for the scripted one."""
    import os

    prov = (provider or os.getenv("MODEL_PROVIDER", "scripted")).lower()
    if llm_reviewer is None:
        llm_reviewer = prov != "scripted" and os.getenv("AP_LLM_REVIEWER", "1") != "0"
    triage = Triage(id="triage")
    inv_exec = Investigator(investigator or build_investigator(prov, tools), id="investigator")
    rev_exec = Reviewer(reviewer, build_llm_reviewer(prov) if (reviewer and llm_reviewer) else None, id="reviewer")
    respond = Respond(id="respond")
    wf = (
        WorkflowBuilder(start_executor=triage, name="ap-exception-investigation")
        .add_edge(triage, inv_exec, condition=lambda m: isinstance(m, Investigate))
        .add_edge(triage, respond, condition=lambda m: isinstance(m, Final))
        .add_edge(inv_exec, rev_exec)
        .add_edge(rev_exec, inv_exec, condition=lambda m: isinstance(m, Investigate))
        .add_edge(rev_exec, respond, condition=lambda m: isinstance(m, Final))
        .build()
    )
    result = await wf.run(RunState(question=question, principal=principal))
    return result.get_outputs()[0]
