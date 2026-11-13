"""Step 8 tests: the action gate — the only way anything gets changed in the ERP."""

from ap_investigator import gate
from ap_investigator.erp import repo
from ap_investigator.models import ActionRequest
from ap_investigator.security import Principal

CLERK = Principal.of("cem", "AP.Clerk")
MANAGER = Principal.of("mara", "AP.Manager")
SECOND_MANAGER = Principal.of("tom", "AP.Manager")


def pick(cases, scenario, n=0):
    return [c for c in cases if c["scenario"] == scenario][n]


def release(invoice_id):
    return ActionRequest(action="release_hold", invoice_id=invoice_id, amount=None, justification="test")


def approves_as(person):
    """A fake human approver who says yes, as `person` (a signed-in user with roles)."""
    async def approver(request, requester):
        return person
    return approver


async def says_no(request, requester):
    return None


# --- Part 1: the basic checks ---------------------------------------------------------------------

async def test_clerk_cannot_release_even_with_approval(cases):
    inv = pick(cases, "qty_mismatch")["invoice_id"]
    result = await gate.execute(release(inv), CLERK, approves_as(SECOND_MANAGER))
    assert not result.executed
    assert repo.get_invoice(inv)["status"] == "on_hold"


async def test_fraud_signal_blocks_even_a_manager(cases):
    inv = pick(cases, "bank_change")["invoice_id"]
    result = await gate.execute(release(inv), MANAGER, approves_as(SECOND_MANAGER))
    assert not result.executed
    assert "AP-POL-08 §3.2" in result.reason
    assert repo.get_invoice(inv)["status"] == "on_hold"


async def test_rejected_approval_changes_nothing(cases):
    inv = pick(cases, "qty_mismatch")["invoice_id"]
    result = await gate.execute(release(inv), MANAGER, says_no)
    assert not result.executed
    assert repo.audit_log() == []


async def test_nobody_approves_their_own_release(cases):
    inv = pick(cases, "qty_mismatch")["invoice_id"]
    result = await gate.execute(release(inv), MANAGER, approves_as(MANAGER))
    assert not result.executed
    assert "Four-eyes" in result.reason


async def test_clean_release_is_executed_and_audited(cases):
    inv = pick(cases, "qty_mismatch")["invoice_id"]
    result = await gate.execute(release(inv), MANAGER, approves_as(SECOND_MANAGER))
    assert result.executed
    assert repo.get_invoice(inv)["status"] == "approved"
    entry = repo.audit_log()[-1]
    assert (entry["user_name"], entry["approved_by"]) == ("mara", "tom")


# --- Bug 1 from the review: anyone could be the "second pair of eyes" ----------------------------

async def test_approver_must_be_allowed_to_release(cases):
    inv = pick(cases, "qty_mismatch")["invoice_id"]
    intern = Principal.of("random-intern", "AP.Clerk")
    result = await gate.execute(release(inv), MANAGER, approves_as(intern))
    assert not result.executed
    assert "approver" in result.reason.lower()
    assert repo.get_invoice(inv)["status"] == "on_hold"


# --- Bug 2 from the review: the audit log recorded the wrong role --------------------------------

async def test_audit_log_records_the_role_that_allowed_the_action(cases):
    inv = pick(cases, "qty_mismatch")["invoice_id"]
    sam = Principal.of("sam", "AP.Manager", "AP.Auditor")      # two roles
    await gate.execute(release(inv), sam, approves_as(SECOND_MANAGER))
    assert repo.audit_log()[-1]["role"] == "AP.Manager"      # not "AP.Auditor"