"""Deterministic checks of ERP facts against policy thresholds.

Used by the Reviewer (to verify each root cause the Investigator *claims*) and by the action
gate (to refuse releases that policy forbids, whatever the model says). These are not the
Investigator's tools: the model must reach its conclusions from the records itself.
"""

from __future__ import annotations

from .domain import (
    APPROVAL_LIMIT_EUR,
    BANK_CHANGE_WINDOW_DAYS,
    PRICE_TOLERANCE_PCT,
    RootCause as RC,
)
from .erp import repo


def check(invoice_id: str) -> dict[RC, bool]:
    """Which root-cause predicates hold for this invoice right now."""
    inv = repo.get_invoice(invoice_id)
    out = {rc: False for rc in RC}
    out[RC.NOT_ON_HOLD] = inv["status"] != "on_hold"

    if inv["po_id"]:
        m = repo.get_matching_details(invoice_id)
        lines = m["lines"]
        out[RC.MISSING_RECEIPT] = any(ln["received_qty"] == 0 for ln in lines)
        out[RC.QTY_MISMATCH] = any(0 < ln["received_qty"] < ln["invoiced_qty"] for ln in lines)
        out[RC.PRICE_VARIANCE] = any((ln["price_variance_pct"] or 0) > PRICE_TOLERANCE_PCT for ln in lines)
        out[RC.CURRENCY_TAX_MISMATCH] = m["po_currency"] != m["invoice_currency"] or any(
            ln["po_tax_code"] != ln["invoice_tax_code"] for ln in lines)

    out[RC.DUPLICATE_INVOICE] = bool(repo.find_similar_invoices(invoice_id)["matches"])
    vendor = repo.get_vendor(inv["vendor_id"])
    out[RC.VENDOR_ON_HOLD] = vendor["on_hold"]
    changes = repo.get_vendor_change_log(inv["vendor_id"], days=BANK_CHANGE_WINDOW_DAYS)["changes"]
    out[RC.BANK_ACCOUNT_CHANGE] = any(c["field"] == "bank_account" and not c["callback_verified"] for c in changes)
    out[RC.APPROVAL_MISSING] = inv["total_amount"] > APPROVAL_LIMIT_EUR and inv["approval_status"] == "pending"
    out[RC.EINVOICE_VALIDATION_FAILED] = inv["einvoice_status"] == "validation_failed"
    return out


def release_blockers(invoice_id: str) -> list[RC]:
    """Causes that AP-POL-08 §3.2 says AP may never release, present right now."""
    c = check(invoice_id)
    return [rc for rc in (RC.BANK_ACCOUNT_CHANGE, RC.DUPLICATE_INVOICE, RC.VENDOR_ON_HOLD,
                          RC.EINVOICE_VALIDATION_FAILED) if c[rc]]
