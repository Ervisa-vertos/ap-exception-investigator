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