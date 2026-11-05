# AP-POL-01 Three-way matching and tolerances

## §1.1 Scope
Applies to every vendor invoice that references a purchase order (PO). Invoices are matched against the PO line (ordered quantity, unit price, tax code, currency) and the posted goods receipts (product receipts).

## §2.1 Matching rule
An invoice line may be paid only when invoice quantity, PO quantity and received quantity agree, and the invoiced unit price is within tolerance of the PO unit price. The ERP places the invoice on hold with code MATCHING when any check fails.

## §2.2 Quantity mismatch (invoiced quantity exceeds received quantity)
If the invoiced quantity is greater than the quantity received, the invoice must not be paid in full. AP may (a) wait for the remaining delivery if the PO is still open and the vendor confirms a delivery date, (b) partially match and pay only the received quantity with buyer agreement, or (c) request a credit note from the vendor for the undelivered quantity. Over-invoicing against receipts is never released without one of these.

## §2.3 Missing goods receipt
If no goods receipt has been posted for a PO line, AP must contact the receiving warehouse or the requester to confirm whether goods or services were received and ask them to post the receipt. AP must not post receipts on behalf of the warehouse (segregation of duties).

## §3.1 Price tolerance
Unit price variance up to 2.0% above the PO unit price is accepted automatically. Above 2.0%, AP must either request a credit note for the difference or obtain the buyer's written approval and a PO price amendment before the invoice can be matched. Price decreases are always accepted.

## §3.2 Rounding
Differences under EUR 1.00 per invoice caused by rounding are accepted.
