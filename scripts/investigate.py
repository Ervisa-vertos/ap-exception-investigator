"""Run the Investigator on one invoice: structured answer + evidence ledger.

    python scripts\\investigate.py INV-1213                 # uses MODEL_PROVIDER from .env (default: scripted)
    python scripts\\investigate.py INV-1213 --provider foundry
"""

import argparse
import asyncio
import json
import time

from dotenv import load_dotenv

from ap_investigator.agents.investigator import build_investigator
from ap_investigator.ledger import Ledger, ledger_middleware
from ap_investigator.models import Investigation


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("invoice_id")
    parser.add_argument("--provider", choices=["scripted", "ollama", "foundry"], default=None)
    args = parser.parse_args()

    agent = build_investigator(args.provider)
    ledger = Ledger()
    start = time.perf_counter()
    response = await agent.run(
        f"Why is {args.invoice_id} on hold?",
        options={"response_format": Investigation},      # the answer must match the Investigation schema
        middleware=[ledger_middleware(ledger)],           # record every tool call
    )
    seconds = time.perf_counter() - start

    print(f"\nTool calls ({len(ledger.calls)}, {seconds:.1f} s):")
    for call in ledger.calls:
        print(f"  -> {call.name}({json.dumps(call.arguments)})" + (f"  ERROR: {call.error}" if call.error else ""))
    print(f"\nRecords retrieved:        {sorted(ledger.records)}")
    print(f"Policy sections retrieved: {sorted(ledger.policy_sections)}")
    if ledger.injection_flags:
        print(f"Injection flags seen:     {sorted(ledger.injection_flags)}")

    inv = response.value
    if not isinstance(inv, Investigation):
        print("\nThe model did not return a valid Investigation. Raw text:\n" + response.text)
        return
    print("\nInvestigation:")
    print(inv.model_dump_json(indent=2))

    # The first check the Reviewer will automate: was every cited record and section really retrieved?
    unretrieved = [e.record_id for e in inv.evidence if e.record_id not in ledger.records]
    uncited = [c.policy_section for c in inv.citations if c.policy_section not in ledger.policy_sections]
    print(f"\nEvidence not actually retrieved: {unretrieved or 'none'}")
    print(f"Citations not actually retrieved: {uncited or 'none'}")


if __name__ == "__main__":
    asyncio.run(main())