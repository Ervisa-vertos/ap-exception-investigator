Q1/ap-investigate ask "Why is INV-1213 on hold?"

[answered] INV-1213 from Bratislava Pallets (244.20 EUR) is on hold because of: bank account change, price variance.

Causes: BANK_ACCOUNT_CHANGE, PRICE_VARIANCE
  - [PO-000309] Unit price 20.35 vs PO 18.5 (+10.0%, tolerance 2.0%).
  - [VCL-0006] Bank account changed 12 days ago via email, not callback-verified.
  > AP-POL-03 §2.1: "If a vendor's bank account was changed within the last 30 days and the change has not been verified by a callback, all payments to that vendor are blocked (hold code PAYMENT_BLOCK)"
  > AP-POL-01 §3.1: "Unit price variance up to 2.0% above the PO unit price is accepted automatically"
Next steps: ESCALATE_FRAUD_REVIEW → BUYER_PRICE_APPROVAL
1) Escalate to fraud review; verify the bank change by callback to the number on file. Do not pay. 2) Ask the buyer to approve the new price and amend the PO, or request a credit note.

  tools: triage.get_invoice → get_invoice → get_matching_details → find_similar_invoices → get_vendor → get_vendor_change_log → get_vendor_messages → search_policy → search_policy  |  review rounds: 0

Q2/ap-investigate ask "Release the hold on INV-1213" --role AP.Manager --user mara --approve-as tom

[answered] INV-1213 from Bratislava Pallets (244.20 EUR) is on hold because of: bank account change, price variance.

Causes: BANK_ACCOUNT_CHANGE, PRICE_VARIANCE
  - [PO-000309] Unit price 20.35 vs PO 18.5 (+10.0%, tolerance 2.0%).
  - [VCL-0006] Bank account changed 12 days ago via email, not callback-verified.
  > AP-POL-03 §2.1: "If a vendor's bank account was changed within the last 30 days and the change has not been verified by a callback, all payments to that vendor are blocked (hold code PAYMENT_BLOCK)"
  > AP-POL-01 §3.1: "Unit price variance up to 2.0% above the PO unit price is accepted automatically"
Next steps: ESCALATE_FRAUD_REVIEW → BUYER_PRICE_APPROVAL
1) Escalate to fraud review; verify the bank change by callback to the number on file. Do not pay. 2) Ask the buyer to approve the new price and amend the PO, or request a credit note.

  tools: triage.get_invoice → get_invoice → get_matching_details → find_similar_invoices → get_vendor → get_vendor_change_log → get_vendor_messages → search_policy → search_policy  |  review rounds: 0

  action release_hold: NOT EXECUTED — Policy AP-POL-08 §3.2 forbids releasing this hold while BANK_ACCOUNT_CHANGE is open. Route it to the owning process.

Q3/ap-investigate ask "Release the hold on INV-1171" --role AP.Clerk --user cem --approve-as tom

[answered] INV-1171 from Iberia Fasteners (4,668.00 EUR) is on hold because of: qty mismatch.

Causes: QTY_MISMATCH
  - [GR-000437] PO line 1: received 75, invoiced 100.
  > AP-POL-01 §2.2: "If the invoiced quantity is greater than the quantity received, the invoice must not be paid in full"
Next steps: WAIT_FOR_RECEIPT
1) Ask the buyer to confirm the open delivery; match the invoice once the rest is received.

  tools: triage.get_invoice → get_invoice → get_matching_details → find_similar_invoices → get_vendor → get_vendor_change_log → get_vendor_messages → search_policy  |  review rounds: 0

  action release_hold: NOT EXECUTED — User 'cem' with role(s) ['AP.Clerk'] may not 'release_hold' (requires: AP.Manager)

## 2026-11-04 — Step 2, Part A

A1. When is a bank-account change a reason to block payment, and when not?
...It blocks payment only when both conditions are true: the change was made in the last 30 days, and it was not verified by a callback (§2.1). A change older than 30 days, or one confirmed by calling the vendor on a number already on file, isn’t a reason to block by itself (§2.4).

A2.1 Why is BANK_ACCOUNT_CHANGE first in CAUSE_PRIORITY?
...Because it’s the only cause where a mistake can’t be undone. A quantity or price problem can be fixed later with a credit note. Money paid to a fraudster’s account is usually gone. It also makes the other causes irrelevant: there’s no point fixing the price on an invoice if the payment would go to the wrong account. So fraud review comes first, and everything else waits.

A2.2 One acceptable and one forbidden next step for BANK_ACCOUNT_CHANGE:
...Acceptable: ESCALATE_FRAUD_REVIEW
Forbidden: RELEASE_HOLD

A4.1 What does add_case() record, and why is the right answer written while the data is created?
...For each test case it records:

the invoice ID and the question a user would ask (picked from a few phrasings)
the correct root causes, in priority order, and the main one
the records the agent must retrieve (for example the invoice, the vendor and the change-log entry)
the policy sections it must cite
the acceptable next steps

The answer is written at the same moment the data is created because that’s the only time it’s known for certain: the generator made the problem, so it knows exactly what’s wrong. That gives you an exact answer key for the evals, with no need to label anything by hand afterwards.

A4.2 Why include a "hard negative" case?
...To catch an agent that’s too suspicious. Without it, an agent that shouted “fraud!” at every bank change would score perfectly. The hard negative is an old, verified bank change on an invoice that’s fine. The agent passes only if it correctly says there’s no problem. It tests that the agent applies the actual rule (30 days and unverified), not just a keyword.

## 2026-11-05 — Step 2 done
Did: copied policies, domain model, schema and generator into my repo; wrote D365 mapping;
3 tests pass; broke the policy-sync test on purpose and fixed it.

B1. Why are root causes and next steps closed lists (enums) instead of free text?

...So the answers can be checked automatically. If the agent could write anything, one run might say “bank details changed”, another “possible payment fraud”, another “vendor IBAN updated”. All mean the same thing, but code can’t reliably compare them, so you’d need a person, or another AI, to judge every answer. With a fixed list, the agent must answer exactly BANK_ACCOUNT_CHANGE, and the eval simply checks whether it equals the expected value.

Closed lists also block invented categories: an answer outside the list is rejected automatically. The free-text summary is still there for humans to read; the codes are what gets measured.

B2. Why does the generator use a fixed seed and a fixed "today" date (AS_OF = 2026-11-02)?

...So the data is exactly the same every time it’s generated.

The seed makes the “random” choices (vendors, amounts, which days) repeat identically. Your test proves this: two runs give byte-for-byte the same file.
The fixed date stops the data from changing over time. The bank-change rule depends on “within the last 30 days”. If the generator used the real date, a change made “12 days ago” today would be 42 days old next month. It would no longer count as fraud, and the expected answers would silently become wrong.

Together they mean a result you measure today can be reproduced next month, by you or by anyone who clones your repo. So when a score changes, you know it’s because the agent changed, not the data.

## 2026-11-05 — Step 3.1: ERP repository

3.1 Why does the repository return facts instead of verdicts?

The repository should return facts rather than verdicts because the responsibility for interpreting business data belongs to the AI agent, not the database layer.
For example, the repository might retrieve that 80 units were received, 100 were invoiced, and the variance is +10%. It should provide these values without deciding that this is a quantity mismatch.
This separation is important for several reasons:

* Separation of responsibilities: The repository retrieves reliable ERP data, while the agent interprets the information and determines what it means in the business context.
* Better testability: We can test whether the agent correctly identifies discrepancies and reaches conclusions based on the retrieved evidence, rather than simply repeating a conclusion already made by the repository.
* Traceability: Every conclusion should be supported by records the repository actually retrieved.
* Flexibility: Different business rules or policies can interpret the same facts differently without changing the database access layer.

Ultimately, I want the agent to reason from evidence rather than inherit assumptions from the repository. This makes the system more transparent, testable and reliable, especially in financial processes where incorrect conclusions can lead to incorrect business actions.

Note: facts.py does compute verdicts in code, but only the Reviewer and the action gate
use them, to check the agent. The agent never sees them; it must reach conclusions from facts.