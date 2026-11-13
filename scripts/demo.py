"""End-to-end demo: ask → investigate → review → (if an action was requested) the action gate.

    python scripts\\demo.py "Release the hold on INV-1171" --role AP.Clerk --user cem
    python scripts\\demo.py "Release the hold on INV-1213" --role AP.Manager --user mara --provider foundry

The demo changes the ERP when a release is approved. Reset with:
    python -m ap_investigator.erp.generator
"""

import argparse
import asyncio

from dotenv import load_dotenv

from ap_investigator import gate
from ap_investigator.erp import repo
from ap_investigator.security import ROLES, Principal
from ap_investigator.workflow import investigate


async def ask_second_person(request, requester):
    """The human approver, typed in the terminal. In a real app this is a second signed-in user."""
    print(f"\n🔐 APPROVAL NEEDED: {request.action} on {request.invoice_id}, requested by {requester.user}")
    name = input("   Second approver's name (press Enter to reject): ").strip()
    if not name:
        return None
    role = input(f"   {name}'s role {list(ROLES)}: ").strip() or "AP.Clerk"
    return Principal.of(name, role)


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--role", choices=ROLES, default="AP.Clerk")
    parser.add_argument("--user", default="ervisa")
    parser.add_argument("--provider", choices=["scripted", "ollama", "foundry"], default=None)
    args = parser.parse_args()
    me = Principal.of(args.user, args.role)

    print(f"\n👤 {me.user} ({args.role}) asks: {args.question}")
    out = await investigate(args.question, me, provider=args.provider)
    print(f"\n🔎 Investigation — status: {out.status}, review rounds: {out.review_rounds}\n")
    print(out.message)

    if out.action_request is None:
        return
    print(f"\n🚪 ACTION GATE: {out.action_request.action} on {out.action_request.invoice_id}")
    result = await gate.execute(out.action_request, me, ask_second_person)
    if result.executed:
        entry = repo.audit_log()[-1]
        print(f"\n✅ EXECUTED. Audit log: {entry['action']} on {entry['invoice_id']} by {entry['user_name']} "
              f"({entry['role']}), approved by {entry['approved_by']}, at {entry['at']}")
    else:
        print(f"\n⛔ REFUSED: {result.reason}")


if __name__ == "__main__":
    asyncio.run(main())