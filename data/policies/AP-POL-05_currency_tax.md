# AP-POL-05 Currency and tax validation

## §2.1 Currency or tax-code mismatch
The invoice currency must equal the PO currency, and each invoice line tax code must equal the PO line tax code. On a mismatch the invoice is held (code MATCHING). AP must not change currency or tax codes on the vendor's invoice; it requests a corrected invoice (or a credit note plus a new invoice) from the vendor.

## §2.2 Reverse charge
Reverse-charge (RC) lines carry no VAT on the invoice. An RC tax code on an invoice for a domestic vendor is a mismatch.
