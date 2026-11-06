"""Step 6 tests: the Reviewer's deterministic checks, on real mistakes seen in the Foundry runs."""

from ap_investigator.agents.reviewer import deterministic_review, quote_in_section
from ap_investigator.retrieval.policy_index import LocalPolicyIndex
from ap_investigator.domain import NextStep as NS
from ap_investigator.domain import RootCause as RC
from ap_investigator.ledger import Ledger
from ap_investigator.models import Citation, Evidence, Investigation


def pick(cases, scenario, n=0):
    return [c for c in cases if c["scenario"] == scenario][n]


def draft(invoice_id, causes, steps, evidence=(), citations=()):
    return Investigation(
        invoice_id=invoice_id, on_hold=True, root_causes=causes, summary="test draft",
        evidence=[Evidence(record_id=r, fact="f") for r in evidence],
        citations=[Citation(policy_section=s, quote=q) for s, q in citations],
        next_steps=steps, next_steps_explained="", proposed_action=None, confidence="high",
    )


def kinds(issues):
    return {i.kind for i in issues}


QTY_QUOTE = "If the invoiced quantity is greater than the quantity received, the invoice must not be paid in full."


def test_correct_answer_passes(cases):
    c = pick(cases, "qty_mismatch")
    ledger = Ledger(records=set(c["required_records"]), policy_sections={"AP-POL-01 §2.2"})
    inv = draft(c["invoice_id"], [RC.QTY_MISMATCH], [NS.WAIT_FOR_RECEIPT],
                evidence=c["required_records"], citations=[("AP-POL-01 §2.2", QTY_QUOTE)])
    assert deterministic_review(inv, ledger, user_requested_action=False) == []


def test_partial_receipt_called_missing_receipt_is_rejected(cases):
    # The real INV-1171 mistake: 75 of 100 received, labelled MISSING_RECEIPT, first step CONTACT_RECEIVING.
    c = pick(cases, "qty_mismatch")
    ledger = Ledger(records=set(c["required_records"]), policy_sections={"AP-POL-01 §2.2", "AP-POL-01 §2.3"})
    inv = draft(c["invoice_id"], [RC.MISSING_RECEIPT, RC.QTY_MISMATCH], [NS.CONTACT_RECEIVING],
                evidence=c["required_records"],
                citations=[("AP-POL-01 §2.3", "x"), ("AP-POL-01 §2.2", QTY_QUOTE)])
    found = kinds(deterministic_review(inv, ledger, user_requested_action=False))
    assert "unsupported_root_cause" in found       # the ERP shows 75 received, not 0
    # Both problems in ONE round. On Foundry, fixing only the cause left the wrong step in place,
    # so the answer ran out of rounds and went to human review.
    assert "unacceptable_next_step" in found       # CONTACT_RECEIVING doesn't fix a quantity mismatch


def test_invented_evidence_and_unretrieved_citation_are_rejected(cases):
    c = pick(cases, "qty_mismatch")
    ledger = Ledger(records={c["invoice_id"]}, policy_sections=set())
    inv = draft(c["invoice_id"], [RC.QTY_MISMATCH], [NS.WAIT_FOR_RECEIPT],
                evidence=[c["invoice_id"], "V-1020"], citations=[("AP-POL-01 §2.2", QTY_QUOTE)])
    found = kinds(deterministic_review(inv, ledger, user_requested_action=False))
    assert "evidence_not_retrieved" in found       # V-1020 was never fetched in this run
    assert "citation_not_retrieved" in found       # the policy was cited without being searched


def test_missed_bank_change_is_caught(cases):
    c = pick(cases, "mixed_price_bank")             # INV-1213: price variance AND bank change
    ledger = Ledger(records=set(c["required_records"]), policy_sections={"AP-POL-01 §3.1"})
    inv = draft(c["invoice_id"], [RC.PRICE_VARIANCE], [NS.REQUEST_CREDIT_NOTE],
                evidence=c["required_records"], citations=[("AP-POL-01 §3.1", "x")])
    found = kinds(deterministic_review(inv, ledger, user_requested_action=False))
    assert "missed_critical_cause" in found


def test_release_is_forbidden_while_fraud_signal_present(cases):
    c = pick(cases, "bank_change")
    ledger = Ledger(records=set(c["required_records"]), policy_sections={"AP-POL-03 §2.1"})
    inv = draft(c["invoice_id"], [RC.BANK_ACCOUNT_CHANGE], [NS.RELEASE_HOLD],
                evidence=c["required_records"], citations=[("AP-POL-03 §2.1", "x")])
    assert "forbidden_next_step" in kinds(deterministic_review(inv, ledger, user_requested_action=False))


# --- Finding 5: paraphrased "quotes" -------------------------------------------------------------

BANK_RULE = LocalPolicyIndex().get("AP-POL-03 §2.1").text


def test_exact_quote_is_accepted():
    # What the model wrote for INV-1196 (word for word):
    assert quote_in_section("If a vendor's bank account was changed within the last 30 days and the change "
                            "has not been verified by a callback, all payments to that vendor are blocked.", BANK_RULE)


def test_quote_with_ellipsis_is_accepted():
    assert quote_in_section("all payments to that vendor are blocked ... The case must be escalated "
                            "to the fraud review team.", BANK_RULE)


def test_paraphrase_is_rejected():
    # What the model wrote for INV-1213: right meaning, but not a quote.
    assert not quote_in_section("Change within 30 days and not callback-verified: all payments to that vendor "
                                "are blocked; escalate to fraud review.", BANK_RULE)


def test_reviewer_flags_a_paraphrased_quote(cases):
    c = pick(cases, "bank_change")
    ledger = Ledger(records=set(c["required_records"]), policy_sections={"AP-POL-03 §2.1"})
    inv = draft(c["invoice_id"], [RC.BANK_ACCOUNT_CHANGE], [NS.ESCALATE_FRAUD_REVIEW],
                evidence=c["required_records"],
                citations=[("AP-POL-03 §2.1", "Change within 30 days and not callback-verified: payments blocked.")])
    assert kinds(deterministic_review(inv, ledger, user_requested_action=False)) == {"quote_not_in_section"}



def test_wrong_step_is_reported_even_when_the_only_claimed_cause_is_wrong(cases):
    # Foundry run 3 on INV-1171: causes=[MISSING_RECEIPT] only, first step CONTACT_RECEIVING.
    c = pick(cases, "qty_mismatch")
    ledger = Ledger(records=set(c["required_records"]), policy_sections={"AP-POL-01 §2.3"})
    inv = draft(c["invoice_id"], [RC.MISSING_RECEIPT], [NS.CONTACT_RECEIVING],
                evidence=c["required_records"], citations=[("AP-POL-01 §2.3", "x")])
    found = kinds(deterministic_review(inv, ledger, user_requested_action=False))
    assert {"unsupported_root_cause", "unacceptable_next_step"} <= found


def test_step_feedback_says_how_to_fix_not_just_what_is_wrong(cases):
    # Foundry run 4: told only "CONTACT_VENDOR... does not address QTY_MISMATCH", the model guessed another wrong step.
    c = pick(cases, "qty_mismatch")
    ledger = Ledger(records=set(c["required_records"]), policy_sections={"AP-POL-01 §2.2"})
    inv = draft(c["invoice_id"], [RC.QTY_MISMATCH], [NS.CONTACT_VENDOR_MANAGEMENT],
                evidence=c["required_records"], citations=[("AP-POL-01 §2.2", QTY_QUOTE)])
    [issue] = deterministic_review(inv, ledger, user_requested_action=False)
    assert issue.kind == "unacceptable_next_step"
    for step in ["WAIT_FOR_RECEIPT", "PARTIAL_MATCH_PAY_RECEIVED", "REQUEST_CREDIT_NOTE"]:
        assert step in issue.detail