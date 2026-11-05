# AP-POL-02 Duplicate invoice prevention

## §2.1 Duplicate definition and handling
An invoice is a duplicate when the same vendor has already submitted an invoice with the same vendor invoice number, or with the same amount and invoice date. A confirmed duplicate must be rejected and must never be paid. AP informs the vendor that the original was already processed and references the original internal invoice ID.

## §2.2 Detection window
The ERP compares new invoices with all invoices from the same vendor in the last 14 days and with all invoices carrying the same vendor invoice number regardless of date.

## §2.3 False positives
If the "duplicate" is a legitimate separate invoice (for example a second partial delivery with the same amount), AP documents the evidence and an AP manager releases the hold.
