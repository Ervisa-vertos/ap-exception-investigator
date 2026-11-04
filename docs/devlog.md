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