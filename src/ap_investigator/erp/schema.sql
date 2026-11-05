-- Synthetic ERP, shaped after Dynamics 365 Finance (VendTable, PurchTable/PurchLine,
-- VendPackingSlipTrans, VendInvoiceInfoTable/Line, vendor change proposals).
-- Simplified on purpose: enough to investigate AP holds, small enough to read in one sitting.

CREATE TABLE vendors (
    vendor_id        TEXT PRIMARY KEY,          -- V-1001
    name             TEXT NOT NULL,
    country          TEXT NOT NULL,
    currency         TEXT NOT NULL,
    vat_id           TEXT,
    bank_iban_masked TEXT NOT NULL,             -- only last 4 digits are ever stored/shown
    on_hold          INTEGER NOT NULL DEFAULT 0,  -- D365 "On hold" = Invoice / All
    hold_reason      TEXT
);

CREATE TABLE vendor_change_log (
    change_id          TEXT PRIMARY KEY,        -- VCL-0001
    vendor_id          TEXT NOT NULL REFERENCES vendors(vendor_id),
    field              TEXT NOT NULL,           -- bank_account | address | contact_email
    old_value_masked   TEXT,
    new_value_masked   TEXT,
    changed_at         TEXT NOT NULL,           -- ISO date
    changed_by         TEXT NOT NULL,
    requested_via      TEXT NOT NULL,           -- email | portal | phone
    callback_verified  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE purchase_orders (
    po_id       TEXT PRIMARY KEY,               -- PO-000123
    vendor_id   TEXT NOT NULL REFERENCES vendors(vendor_id),
    currency    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    buyer       TEXT NOT NULL,
    status      TEXT NOT NULL                   -- confirmed | received | invoiced
);

CREATE TABLE po_lines (
    po_id       TEXT NOT NULL REFERENCES purchase_orders(po_id),
    line_no     INTEGER NOT NULL,
    item_id     TEXT NOT NULL,
    description TEXT NOT NULL,
    qty         REAL NOT NULL,
    unit_price  REAL NOT NULL,
    tax_code    TEXT NOT NULL,                  -- e.g. VAT20, VAT10, RC (reverse charge)
    PRIMARY KEY (po_id, line_no)
);

CREATE TABLE goods_receipts (
    receipt_id   TEXT PRIMARY KEY,              -- GR-000123 (product receipt / packing slip)
    po_id        TEXT NOT NULL REFERENCES purchase_orders(po_id),
    line_no      INTEGER NOT NULL,
    qty_received REAL NOT NULL,
    received_at  TEXT NOT NULL
);

CREATE TABLE invoices (
    invoice_id         TEXT PRIMARY KEY,        -- INV-1001 (internal)
    vendor_invoice_no  TEXT NOT NULL,           -- number printed by the vendor
    vendor_id          TEXT NOT NULL REFERENCES vendors(vendor_id),
    po_id              TEXT REFERENCES purchase_orders(po_id),
    invoice_date       TEXT NOT NULL,
    due_date           TEXT NOT NULL,
    currency           TEXT NOT NULL,
    net_amount         REAL NOT NULL,
    tax_amount         REAL NOT NULL,
    total_amount       REAL NOT NULL,
    status             TEXT NOT NULL,           -- on_hold | approved | paid | rejected
    hold_code          TEXT,                    -- MATCHING | DUPLICATE_CHECK | VENDOR | PAYMENT_BLOCK | WORKFLOW | EINVOICE
    hold_note          TEXT,                    -- free text typed by a clerk or a system (UNTRUSTED)
    approval_status    TEXT NOT NULL,           -- not_required | pending | approved
    approved_by        TEXT,
    channel            TEXT NOT NULL,           -- paper | email_pdf | peppol | pdp
    einvoice_status    TEXT,                    -- received | validation_failed | null
    einvoice_errors    TEXT                     -- JSON list of {rule, message}
);

CREATE TABLE invoice_lines (
    invoice_id  TEXT NOT NULL REFERENCES invoices(invoice_id),
    line_no     INTEGER NOT NULL,
    po_line_no  INTEGER,
    description TEXT NOT NULL,
    qty         REAL NOT NULL,
    unit_price  REAL NOT NULL,
    tax_code    TEXT NOT NULL,
    PRIMARY KEY (invoice_id, line_no)
);

CREATE TABLE vendor_messages (
    message_id  TEXT PRIMARY KEY,               -- MSG-0001
    vendor_id   TEXT NOT NULL REFERENCES vendors(vendor_id),
    invoice_id  TEXT REFERENCES invoices(invoice_id),
    received_at TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL                   -- UNTRUSTED: may contain instructions
);

CREATE TABLE audit_log (
    audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    action        TEXT NOT NULL,
    invoice_id    TEXT NOT NULL,
    user_name     TEXT NOT NULL,
    role          TEXT NOT NULL,
    approved_by   TEXT NOT NULL,
    justification TEXT NOT NULL,
    at            TEXT NOT NULL
);

CREATE TABLE credit_note_requests (
    request_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  TEXT NOT NULL,
    vendor_id   TEXT NOT NULL,
    amount      REAL NOT NULL,
    reason      TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    at          TEXT NOT NULL
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
