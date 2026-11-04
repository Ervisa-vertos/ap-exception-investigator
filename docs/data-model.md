# D365 Finance & Operations – Data Model Mapping

## Overview

This document maps the synthetic procurement and accounts payable data model to its closest equivalents in Microsoft Dynamics 365 Finance & Operations (D365 F&O).

The project focuses primarily on pending vendor invoices and the business controls that determine whether an invoice can proceed to approval and posting.

The synthetic model simplifies the underlying ERP structures to make business information accessible to AI agents.

## 1. Core Table Mapping

| Synthetic table | D365 F&O equivalent | Notes / simplifications |
|---|---|---|
| `vendors` | `VendTable` + `VendBankAccount` | Vendor master and bank account information are maintained separately in D365. The synthetic `bank_iban_masked` field combines these structures. |
| `vendor_change_log` | `SysDatabaseLog` + vendor change proposals/workflow | Database logging provides an audit trail when configured. Change proposals and approval workflows provide business controls over sensitive changes. |
| `purchase_orders` | `PurchTable` | Purchase order header, including vendor, PO number, status and currency. |
| `po_lines` | `PurchLine` | Purchase order lines, including item, quantity, unit price and delivery information. |
| `goods_receipts` | `VendPackingSlipJour` + `VendPackingSlipTrans` | Product receipt header and lines, combined into one simplified structure. |
| `invoices` | `VendInvoiceInfoTable` | Pending vendor invoice header. Represents invoices awaiting validation, matching, approval or posting. |
| `invoice_lines` | `VendInvoiceInfoLine` | Pending vendor invoice lines, simplified for matching and analysis. |

## 2. Hold Code Mapping

The synthetic `hold_code` field consolidates several different D365 F&O business controls.

| Synthetic hold code | D365 F&O concept | Notes |
|---|---|---|
| `VENDOR` | `VendTable.Blocked` | Vendor-level blocking, particularly invoice-related blocking. |
| `MATCHING` | Pending vendor invoice matching | Price and quantity discrepancies, product receipt matching and configured tolerances. |
| `DUPLICATE_CHECK` | Accounts payable invoice number validation | Checks whether an invoice number has already been used, according to configured duplicate-check behavior. |
| `WORKFLOW` | Vendor invoice approval workflow | Represents pending approval, rejection or other workflow outcomes. |
| `PAYMENT_BLOCK` | Vendor / open transaction payment blocking | Payment restrictions are separate from invoice approval and should be checked at the appropriate level. |
| `EINVOICE` | Electronic Reporting (ER) / Electronic invoicing | Represents import, mapping or electronic document validation failures. |

These codes are business-level abstractions rather than direct mappings to individual D365 database fields.

## 3. Important Business Relationships

The procurement and accounts payable lifecycle can be represented as:

1. Vendor information is maintained in `VendTable`, with bank information stored separately in `VendBankAccount`.
2. Purchase orders are created using `PurchTable` and `PurchLine`.
3. Product receipts are recorded using `VendPackingSlipJour` and `VendPackingSlipTrans`.
4. Vendor invoices enter the pending invoice process through `VendInvoiceInfoTable` and `VendInvoiceInfoLine`.
5. Invoice matching, validation and approval determine whether the invoice can proceed to posting.
6. Posted invoices are represented by `VendInvoiceJour` and `VendInvoiceTrans`.
7. Payment and settlement information is subsequently reflected in vendor transactions (`VendTrans`) and settlement records (`VendSettlement`).

## 4. Important Simplifications

- **Vendor bank information:** The synthetic model combines vendor master data and bank account information. In D365, IBAN and other bank details belong to the separate vendor bank account structure.
- **Vendor change history:** Database logging and vendor change approval are different mechanisms. One records changes; the other controls whether proposed changes can be approved.
- **Pending versus posted invoices:** This project primarily focuses on pending vendor invoices. Posted invoices are a later stage of the process.
- **Invoice matching:** D365 supports purchase order and product receipt matching, including configured price and quantity tolerances. The synthetic model consolidates matching outcomes.
- **Duplicate validation:** Duplicate invoice-number checking depends on Accounts payable parameters and configuration.
- **Payment blocking:** Vendor-level payment restrictions and open transaction payment restrictions should not be confused with invoice workflow status.
- **Electronic invoicing:** Incoming electronic invoices can be processed through Electronic Reporting configurations and the Electronic Invoicing service. The synthetic model simplifies the import and validation process into an `EINVOICE` hold category.

## 5. Electronic Reporting and Invoice Integration

In D365 F&O, Electronic Reporting (ER) configurations can be used to transform incoming vendor invoice documents into the structures required by the application.

This involves data models, model mappings, format configurations and destination mappings.

The import process can include vendor identification, external item mapping, document validation and error handling.

My professional experience with D365 Electronic Reporting, including configuration and mapping, provides relevant domain knowledge for understanding these integration and validation stages.

## 6. AI Agent Considerations

An AI agent investigating a vendor invoice hold should:

- Identify the vendor using its vendor account.
- Check whether the vendor is blocked for invoicing.
- Retrieve the pending invoice header and lines.
- Follow purchase order and product receipt references.
- Investigate matching discrepancies and configured tolerances.
- Check duplicate invoice-number validation.
- Retrieve workflow status and approval history.
- Distinguish invoice approval from payment eligibility.
- Inspect electronic invoice import and validation results when relevant.
- Explain the reason for the hold using evidence from the underlying business records.

The objective is to preserve essential D365 F&O business logic while exposing a simplified, AI-friendly data model.