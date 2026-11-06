"""Investigator + Reviewer: draft → review → (if rejected) feedback → corrected draft → review.

    python scripts\\investigate_and_review.py INV-1171 --provider foundry
    python scripts\\investigate_and_review.py INV-1171 --provider foundry --no-llm-review
"""

import argparse
import asyncio
import time

from dotenv import load_dotenv

from ap_investigator.agents.investigator import build_investigator
from ap_investigator.agents.reviewer import build_llm_reviewer, deterministic_review, feedback_message, llm_review
from ap_investigator.ledger import Ledger, ledger_middleware
from ap_investigator.models import Investigation

MAX_ROUNDS = 2   # first draft + one correction. More rounds cost more and rarely help.


def show(inv: Investigation) -> None:
    print(f"   causes:     {[c.value for c in inv.root_causes]}")
    print(f"   next steps: {[s.value for s in inv.next_steps]}")
    print(f"   citations:  {[c.policy_section for c in inv.citations]}")


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("invoice_id")
    parser.add_argument("--provider", choices=["scripted", "ollama", "foundry"], default=None)
    parser.add_argument("--no-llm-review", action="store_true", help="only the deterministic checks")
    args = parser.parse_args()

    investigator = build_investigator(args.provider)
    session = investigator.create_session()          # keeps the conversation, so feedback has context
    ledger = Ledger()                                # one ledger across rounds: evidence from round 1 still counts
    llm = None if args.no_llm_review or args.provider == "scripted" else build_llm_reviewer(args.provider)

    message = f"Why is {args.invoice_id} on hold?"
    start = time.perf_counter()
    for round_no in range(1, MAX_ROUNDS + 1):
        response = await investigator.run(message, session=session, options={"response_format": Investigation},
                                          middleware=[ledger_middleware(ledger)])
        inv = response.value
        if not isinstance(inv, Investigation):
            print(f"Round {round_no}: no valid Investigation returned.\n{response.text}")
            return
        print(f"\nRound {round_no} draft ({time.perf_counter() - start:.0f} s so far):")
        show(inv)

        issues = deterministic_review(inv, ledger, user_requested_action=False)
        if llm and not issues:                       # the LLM pass only runs when the cheap checks pass
            issues = await llm_review(llm, inv, ledger)
        if not issues:
            print(f"\n✅ APPROVED in round {round_no}.\n\nSummary: {inv.summary}")
            return
        print(f"\n❌ Reviewer rejected round {round_no}:")
        for i in issues:
            print(f"   [{i.kind}] {i.detail}")
        message = feedback_message(issues)

    print(f"\n⚠️  Still not approved after {MAX_ROUNDS} rounds → NEEDS HUMAN REVIEW. Not shown as a final answer.")


if __name__ == "__main__":
    asyncio.run(main())