"""Who is calling, and what may they do? Authorization lives here — never in a prompt.

Locally the principal is set by the CLI/tests. In the deployed version it comes from a
validated Entra ID token: the `roles` claim carries the app roles below (ADR-004).
"""

from __future__ import annotations

from dataclasses import dataclass

CLERK, MANAGER, AUDITOR = "AP.Clerk", "AP.Manager", "AP.Auditor"
ROLES = (CLERK, MANAGER, AUDITOR)

# Permission matrix: action -> roles allowed. Read tools are open to every AP role.
PERMISSIONS: dict[str, set[str]] = {
    "investigate": {CLERK, MANAGER, AUDITOR},
    "request_credit_note": {CLERK, MANAGER},
    "release_hold": {MANAGER},
    "read_audit_log": {MANAGER, AUDITOR},
}


@dataclass(frozen=True)
class Principal:
    user: str
    roles: frozenset[str]

    @classmethod
    def of(cls, user: str, *roles: str) -> "Principal":
        unknown = set(roles) - set(ROLES)
        if unknown:
            raise ValueError(f"Unknown role(s): {', '.join(sorted(unknown))}")
        return cls(user, frozenset(roles))


class NotAuthorizedError(PermissionError):
    pass


def can(principal: Principal, permission: str) -> bool:
    return bool(principal.roles & PERMISSIONS.get(permission, set()))


def require(permission: str, p: Principal) -> Principal:
    if not can(p, permission):
        allowed = ", ".join(sorted(PERMISSIONS.get(permission, set()))) or "nobody"
        raise NotAuthorizedError(
            f"User '{p.user}' with role(s) {sorted(p.roles) or '[]'} may not '{permission}' (requires: {allowed})."
        )
    return p
