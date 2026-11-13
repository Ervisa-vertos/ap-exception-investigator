"""The action gate: the ONLY path to a consequential action.

Checks, in order, all in code:
1. The user explicitly requested the action (intent parsed from the user's own message,
   never from model output or vendor text).
2. The caller's role allows it (security.PERMISSIONS; Entra app roles in production).
3. Business rules re-checked against the ERP at execution time (AP-POL-08 §3.2):
   no release while a bank change / duplicate / vendor hold / e-invoice failure exists.
4. A human approves — and for release_hold the approver must be a different person
   (four-eyes, AP-POL-08 §3.1).
5. The action is executed and written to the audit log.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from . import facts
from .erp import repo
from .models import ActionRequest, ActionResult
from .security import PERMISSIONS, NotAuthorizedError, Principal, can, require

# Approver gets the request and returns the approving PERSON (a signed-in user with roles), or None to reject.
Approver = Callable[[ActionRequest, Principal], Awaitable[Principal | None]]


async def execute(request: ActionRequest, principal: Principal, approver: Approver) -> ActionResult:
    def refuse(reason: str) -> ActionResult:
        return ActionResult(action=request.action, invoice_id=request.invoice_id, executed=False, reason=reason)

    try:
        require(request.action, principal)
    except NotAuthorizedError as exc:
        return refuse(str(exc))

    try:
        inv = repo.get_invoice(request.invoice_id)
    except (repo.RecordNotFoundError, repo.ERPUnavailableError) as exc:
        return refuse(str(exc))

    if request.action == "release_hold":
        if inv["status"] != "on_hold":
            return refuse(f"{request.invoice_id} is not on hold (status: {inv['status']}).")
        blockers = facts.release_blockers(request.invoice_id)
        if blockers:
            return refuse("Policy AP-POL-08 §3.2 forbids releasing this hold while "
                          + ", ".join(b.value for b in blockers) + " is open. Route it to the owning process.")
    elif request.action == "request_credit_note":
        if not request.amount or request.amount <= 0:
            return refuse("A credit note request needs a positive amount.")
        if request.amount > inv["net_amount"]:
            return refuse("Credit note amount exceeds the invoice net amount.")

    approver_person = await approver(request, principal)
    if approver_person is None:
        return refuse("Rejected by the human approver. Nothing was changed.")
    if request.action == "release_hold" and approver_person.user == principal.user:
        return refuse("Four-eyes rule: the approver must be a different person than the requester (AP-POL-08 §3.1).")
    if not can(approver_person, request.action):
        return refuse(f"The approver '{approver_person.user}' is not allowed to approve '{request.action}' "
                      f"(requires: {', '.join(sorted(PERMISSIONS[request.action]))}). Nothing was changed.")
    approved_by = approver_person.user
 
    # Record the role that actually GRANTED this action, not just the first role alphabetically.
    role = sorted(principal.roles & PERMISSIONS[request.action])[0]
    if request.action == "release_hold":
        repo.set_invoice_released(request.invoice_id, user=principal.user, role=role, approved_by=approved_by,
                                  justification=request.justification)
    else:
        repo.add_credit_note_request(request.invoice_id, inv["vendor_id"], float(request.amount), request.justification,
                                     user=principal.user, role=role, approved_by=approved_by)
    return ActionResult(action=request.action, invoice_id=request.invoice_id, executed=True,
                        reason="Executed and audited.", approved_by=approved_by)
