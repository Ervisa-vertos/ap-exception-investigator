"""Read/write access to the synthetic ERP.

Every read returns plain dicts with a `records` list naming the primary record IDs it
returned — the evidence ledger uses it to know what the agent has actually seen.
Functions here return *facts* (quantities, variances, dates), never verdicts: deciding what
the facts mean against policy is the Investigator's job, checking it is the Reviewer's.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from ..config import erp_db_path
from ..safety import wrap_untrusted

OUTAGE_INVOICE_ID = "INV-9999"  # simulated ERP outage for failure-handling tests


class ERPUnavailableError(ConnectionError):
    pass


class RecordNotFoundError(LookupError):
    pass


@contextmanager
def _db(path: Path | None = None):
    path = path or erp_db_path()
    if not path.exists():
        raise ERPUnavailableError(f"ERP database not found at {path}. Run: python -m ap_investigator.erp.generator")
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _fault(tool: str) -> None:
    if tool in os.getenv("AP_ERP_FAULT", "").split(","):
        raise ERPUnavailableError(f"ERP service unavailable while calling {tool} (simulated). Try again later.")


def as_of() -> date:
    with _db() as con:
        return date.fromisoformat(con.execute("SELECT value FROM meta WHERE key='as_of_date'").fetchone()[0])


# ---------------------------------------------------------------- invoices
def get_invoice(invoice_id: str) -> dict:
    _fault("get_invoice")
    if invoice_id == OUTAGE_INVOICE_ID:
        raise ERPUnavailableError("ERP service unavailable (simulated outage). Try again later.")
    with _db() as con:
        row = con.execute("SELECT * FROM invoices WHERE invoice_id=?", (invoice_id,)).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Invoice {invoice_id} was not found.")
        inv = dict(row)
        lines = [dict(r) for r in con.execute(
            "SELECT line_no, po_line_no, description, qty, unit_price, tax_code FROM invoice_lines "
            "WHERE invoice_id=? ORDER BY line_no", (invoice_id,))]
        vendor_name = con.execute("SELECT name FROM vendors WHERE vendor_id=?", (inv["vendor_id"],)).fetchone()[0]
    inv["einvoice_errors"] = json.loads(inv["einvoice_errors"]) if inv["einvoice_errors"] else []
    inv["hold_note"] = wrap_untrusted(inv["hold_note"], "invoice.hold_note")
    inv["vendor_name"] = vendor_name
    inv["lines"] = lines
    inv["records"] = [invoice_id]
    return inv


def get_purchase_order(po_id: str) -> dict:
    _fault("get_purchase_order")
    with _db() as con:
        row = con.execute("SELECT * FROM purchase_orders WHERE po_id=?", (po_id,)).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Purchase order {po_id} was not found.")
        lines = [dict(r) for r in con.execute(
            "SELECT line_no, item_id, description, qty, unit_price, tax_code FROM po_lines WHERE po_id=? "
            "ORDER BY line_no", (po_id,))]
    return {**dict(row), "lines": lines, "records": [po_id]}


def get_goods_receipts(po_id: str) -> dict:
    _fault("get_goods_receipts")
    with _db() as con:
        if con.execute("SELECT 1 FROM purchase_orders WHERE po_id=?", (po_id,)).fetchone() is None:
            raise RecordNotFoundError(f"Purchase order {po_id} was not found.")
        rows = [dict(r) for r in con.execute(
            "SELECT receipt_id, line_no, qty_received, received_at FROM goods_receipts WHERE po_id=? "
            "ORDER BY receipt_id", (po_id,))]
    return {"po_id": po_id, "receipts": rows, "receipt_count": len(rows),
            "records": [po_id] + [r["receipt_id"] for r in rows]}


def get_matching_details(invoice_id: str) -> dict:
    """Line-by-line comparison of invoice vs PO vs receipts (like D365 'Invoice matching details')."""
    _fault("get_matching_details")
    inv = get_invoice(invoice_id)
    if not inv["po_id"]:
        return {"invoice_id": invoice_id, "po_id": None, "lines": [], "note": "Invoice has no PO reference.",
                "records": [invoice_id]}
    po = get_purchase_order(inv["po_id"])
    grs = get_goods_receipts(inv["po_id"])
    po_lines = {ln["line_no"]: ln for ln in po["lines"]}
    out = []
    for ln in inv["lines"]:
        pl = po_lines.get(ln["po_line_no"])
        received = sum(r["qty_received"] for r in grs["receipts"] if r["line_no"] == ln["po_line_no"])
        out.append({
            "invoice_line": ln["line_no"],
            "po_line": ln["po_line_no"],
            "description": ln["description"],
            "po_qty": pl["qty"] if pl else None,
            "received_qty": received,
            "invoiced_qty": ln["qty"],
            "po_unit_price": pl["unit_price"] if pl else None,
            "invoice_unit_price": ln["unit_price"],
            "price_variance_pct": round((ln["unit_price"] - pl["unit_price"]) / pl["unit_price"] * 100, 2) if pl else None,
            "po_tax_code": pl["tax_code"] if pl else None,
            "invoice_tax_code": ln["tax_code"],
        })
    return {
        "invoice_id": invoice_id,
        "po_id": inv["po_id"],
        "po_currency": po["currency"],
        "invoice_currency": inv["currency"],
        "receipt_ids": [r["receipt_id"] for r in grs["receipts"]],
        "lines": out,
        "records": [invoice_id, inv["po_id"], *[r["receipt_id"] for r in grs["receipts"]]],
    }


def find_similar_invoices(invoice_id: str, window_days: int = 14) -> dict:
    """Other invoices from the same vendor with the same vendor invoice number, or same total within the window."""
    _fault("find_similar_invoices")
    inv = get_invoice(invoice_id)
    d = date.fromisoformat(inv["invoice_date"])
    with _db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT invoice_id, vendor_invoice_no, invoice_date, total_amount, currency, status FROM invoices "
            "WHERE vendor_id=? AND invoice_id<>?", (inv["vendor_id"], invoice_id))]
    hits = []
    for r in rows:
        same_no = r["vendor_invoice_no"] == inv["vendor_invoice_no"]
        close = abs((date.fromisoformat(r["invoice_date"]) - d).days) <= window_days
        same_amount = abs(r["total_amount"] - inv["total_amount"]) < 0.01 and close
        if same_no or same_amount:
            hits.append({**r, "same_vendor_invoice_no": same_no, "same_amount_within_window": same_amount})
    return {"invoice_id": invoice_id, "vendor_invoice_no": inv["vendor_invoice_no"], "matches": hits,
            "records": [invoice_id] + [h["invoice_id"] for h in hits]}


# ---------------------------------------------------------------- vendors
def get_vendor(vendor_id: str) -> dict:
    _fault("get_vendor")
    with _db() as con:
        row = con.execute("SELECT * FROM vendors WHERE vendor_id=?", (vendor_id,)).fetchone()
    if row is None:
        raise RecordNotFoundError(f"Vendor {vendor_id} was not found.")
    v = dict(row)
    v["on_hold"] = bool(v["on_hold"])
    v["records"] = [vendor_id]
    return v


def get_vendor_change_log(vendor_id: str, days: int = 90) -> dict:
    _fault("get_vendor_change_log")
    today = as_of()
    with _db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM vendor_change_log WHERE vendor_id=? ORDER BY changed_at DESC", (vendor_id,))]
    out = []
    for r in rows:
        age = (today - date.fromisoformat(r["changed_at"])).days
        if age <= days:
            r["days_ago"] = age
            r["callback_verified"] = bool(r["callback_verified"])
            out.append(r)
    return {"vendor_id": vendor_id, "as_of": today.isoformat(), "changes": out,
            "records": [vendor_id] + [r["change_id"] for r in out]}


def get_vendor_messages(invoice_id: str) -> dict:
    _fault("get_vendor_messages")
    with _db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT message_id, vendor_id, received_at, subject, body FROM vendor_messages WHERE invoice_id=? "
            "ORDER BY received_at", (invoice_id,))]
    for r in rows:
        r["body"] = wrap_untrusted(r["body"], f"vendor_message:{r['message_id']}")
    return {"invoice_id": invoice_id, "messages": rows, "records": [r["message_id"] for r in rows]}


def list_holds(limit: int = 50) -> list[dict]:
    with _db() as con:
        return [dict(r) for r in con.execute(
            "SELECT invoice_id, vendor_id, total_amount, currency, hold_code, invoice_date FROM invoices "
            "WHERE status='on_hold' ORDER BY invoice_id LIMIT ?", (limit,))]


# ---------------------------------------------------------------- writes (only via the action gate)
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def set_invoice_released(invoice_id: str, *, user: str, role: str, approved_by: str, justification: str) -> None:
    with _db() as con:
        con.execute("UPDATE invoices SET status='approved', hold_code=NULL WHERE invoice_id=?", (invoice_id,))
        con.execute("INSERT INTO audit_log (action, invoice_id, user_name, role, approved_by, justification, at) "
                    "VALUES ('release_hold', ?, ?, ?, ?, ?, ?)", (invoice_id, user, role, approved_by, justification, _now()))


def add_credit_note_request(invoice_id: str, vendor_id: str, amount: float, reason: str, *, user: str, role: str,
                            approved_by: str) -> int:
    with _db() as con:
        cur = con.execute("INSERT INTO credit_note_requests (invoice_id, vendor_id, amount, reason, requested_by, at) "
                          "VALUES (?, ?, ?, ?, ?, ?)", (invoice_id, vendor_id, amount, reason, user, _now()))
        con.execute("INSERT INTO audit_log (action, invoice_id, user_name, role, approved_by, justification, at) "
                    "VALUES ('request_credit_note', ?, ?, ?, ?, ?, ?)", (invoice_id, user, role, approved_by, reason, _now()))
        return cur.lastrowid


def audit_log() -> list[dict]:
    with _db() as con:
        return [dict(r) for r in con.execute("SELECT * FROM audit_log ORDER BY audit_id")]
