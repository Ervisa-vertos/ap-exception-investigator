"""Ask the whole system a question, the way a user would.

    python scripts\\ask.py "Why is INV-1171 on hold?" --provider foundry
    python scripts\\ask.py "Please pay INV-1171" --role AP.Clerk
"""

import argparse
import asyncio
import time

from dotenv import load_dotenv

from ap_investigator.security import ROLES, Principal
from ap_investigator.workflow import investigate


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--provider", choices=["scripted", "ollama", "foundry"], default=None)
    parser.add_argument("--role", choices=ROLES, default="AP.Clerk")
    parser.add_argument("--user", default="ervisa")
    args = parser.parse_args()

    start = time.perf_counter()
    out = await investigate(args.question, Principal.of(args.user, args.role), provider=args.provider)
    seconds = time.perf_counter() - start

    print(f"\nStatus: {out.status}   |   review rounds: {out.review_rounds}   |   "
          f"tool calls: {len(out.tool_calls)}   |   {seconds:.1f} s\n")
    print(out.message)
    if out.action_request:
        print(f"\nAction requested: {out.action_request.action} on {out.action_request.invoice_id} "
              "(not executed — that needs the action gate, Step 8)")


if __name__ == "__main__":
    asyncio.run(main())