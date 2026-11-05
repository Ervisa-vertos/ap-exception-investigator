# AP-POL-07 Inbound electronic invoices (EN 16931, Peppol, French PDP)

## §1.1 Scope
Applies to structured e-invoices received via Peppol or via a French partner dematerialisation platform (PDP). The structured data (UBL / CII / Factur-X) is the legal invoice.

## §2.1 Validation failure
An inbound e-invoice that fails EN 16931 business rules (for example BR-CO-15 totals, BR-S-08 VAT breakdown) or Peppol rules (for example PEPPOL-EN16931-R003 missing buyer or PO reference) is held with code EINVOICE. AP must never correct the structured data manually. AP rejects the invoice through the platform with the rule ID as rejection reason, and the vendor must issue a corrected invoice.

## §2.2 Lifecycle status
For PDP invoices the rejection is sent as a lifecycle status ("Rejetée") so that the vendor and the tax administration receive it. A rejected e-invoice is never paid.

## §2.3 Missing PO reference
If the only error is a missing PO reference and AP can identify the PO with certainty, AP still rejects and asks the vendor to re-issue with the reference, because the received document cannot be changed.
