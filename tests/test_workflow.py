"""Step 7 tests: the workflow routes every question the right way — most of them without any AI call."""

import pytest

from ap_investigator.security import Principal
from ap_investigator.workflow import investigate, parse_intent

CLERK = Principal.of("cem", "AP.Clerk")


def pick(cases, scenario, n=0):
    return [c for c in cases if c["scenario"] == scenario][n]


# --- Triage: answered by code, no AI call, no cost --------------------------------------------

async def test_no_invoice_number_asks_which_invoice():
    out = await investigate("Why is my invoice stuck?", CLERK, provider="scripted")
    assert out.status == "clarify"
    assert out.tool_calls == []                          # nothing was looked up


async def test_payment_request_is_refused_politely():
    out = await investigate("Please pay INV-1171 today", CLERK, provider="scripted")
    assert out.status == "refused"
    assert "can't make or schedule payments" in out.message


async def test_unknown_invoice_is_reported_not_guessed():
    out = await investigate("Why is INV-0001 on hold?", CLERK, provider="scripted")
    assert "not found" in out.message.lower()
    assert out.investigation is None


async def test_erp_outage_is_reported_not_guessed():
    out = await investigate("Why is INV-9999 on hold?", CLERK, provider="scripted")
    assert out.status == "error"
    assert "Nothing was guessed" in out.message


async def test_invoice_not_on_hold_needs_no_ai(cases):
    c = pick(cases, "not_on_hold")
    out = await investigate(f"Why is {c['invoice_id']} on hold?", CLERK, provider="scripted")
    assert out.investigation.root_causes[0].value == "NOT_ON_HOLD"
    assert out.tool_calls == ["triage.get_invoice"]      # one lookup by code, the AI was never called


# --- The full path: triage → investigator → reviewer → respond ----------------------------------

async def test_full_path_is_reviewed_and_approved(cases):
    c = pick(cases, "qty_mismatch")
    out = await investigate(f"Why is {c['invoice_id']} on hold?", CLERK, provider="scripted")
    assert out.status == "answered"
    assert out.review.approved
    assert out.investigation.root_causes[0].value == "QTY_MISMATCH"


# --- Bug found in the review: questions about releasing were treated as release requests ---------

@pytest.mark.parametrize("question", [
    "Should I release the hold on INV-1171?",
    "Why can't I release the hold on INV-1171?",
    "Who can release the hold on INV-1171?",
    "Can the hold on INV-1171 be lifted?",
])
def test_questions_about_releasing_are_not_release_requests(question):
    assert parse_intent(question) == "investigate"


@pytest.mark.parametrize("question", [
    "Release the hold on INV-1171",
    "Please release the hold on INV-1171.",
    "Can you release the hold on INV-1171?",
])
def test_real_release_requests_are_still_recognised(question):
    assert parse_intent(question) == "release_hold"