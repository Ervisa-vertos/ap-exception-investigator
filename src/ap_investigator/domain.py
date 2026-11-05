"""Closed vocabularies and policy constants.

Closed label sets make the agent's output *measurable*: root causes and next steps are
codes the eval harness can compare exactly, with free text alongside for humans.
Thresholds here mirror data/policies/*.md — tests check the two stay in sync.
"""

from __future__ import annotations

from enum import Enum


class RootCause(str, Enum):
    QTY_MISMATCH = "QTY_MISMATCH"                      # invoiced qty > received qty
    PRICE_VARIANCE = "PRICE_VARIANCE"                  # unit price over tolerance vs PO
    MISSING_RECEIPT = "MISSING_RECEIPT"                # no goods receipt posted
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    VENDOR_ON_HOLD = "VENDOR_ON_HOLD"
    BANK_ACCOUNT_CHANGE = "BANK_ACCOUNT_CHANGE"        # recent, unverified bank change
    APPROVAL_MISSING = "APPROVAL_MISSING"              # over limit, approval pending
    CURRENCY_TAX_MISMATCH = "CURRENCY_TAX_MISMATCH"
    EINVOICE_VALIDATION_FAILED = "EINVOICE_VALIDATION_FAILED"
    NOT_ON_HOLD = "NOT_ON_HOLD"
    UNDETERMINED = "UNDETERMINED"                      # tool failure / not enough evidence


class NextStep(str, Enum):
    WAIT_FOR_RECEIPT = "WAIT_FOR_RECEIPT"
    PARTIAL_MATCH_PAY_RECEIVED = "PARTIAL_MATCH_PAY_RECEIVED"
    REQUEST_CREDIT_NOTE = "REQUEST_CREDIT_NOTE"
    BUYER_PRICE_APPROVAL = "BUYER_PRICE_APPROVAL"
    CONTACT_RECEIVING = "CONTACT_RECEIVING"
    REJECT_DUPLICATE = "REJECT_DUPLICATE"
    CONTACT_VENDOR_MANAGEMENT = "CONTACT_VENDOR_MANAGEMENT"
    ESCALATE_FRAUD_REVIEW = "ESCALATE_FRAUD_REVIEW"
    ROUTE_FOR_APPROVAL = "ROUTE_FOR_APPROVAL"
    REQUEST_CORRECTED_INVOICE = "REQUEST_CORRECTED_INVOICE"
    REJECT_EINVOICE_VIA_PLATFORM = "REJECT_EINVOICE_VIA_PLATFORM"
    RELEASE_HOLD = "RELEASE_HOLD"
    NO_ACTION = "NO_ACTION"
    RETRY_LATER = "RETRY_LATER"


# Consequential actions the system can execute (only through the action gate).
ACTIONS = {"release_hold", "request_credit_note"}

# Policy thresholds (source of truth: data/policies).
PRICE_TOLERANCE_PCT = 2.0            # AP-POL-01 §3.1
BANK_CHANGE_WINDOW_DAYS = 30         # AP-POL-03 §2.1
APPROVAL_LIMIT_EUR = 25_000.0        # AP-POL-04 §2.1
DUPLICATE_WINDOW_DAYS = 14           # AP-POL-02 §2.2

# Which policy section justifies each root cause. Used by the Reviewer and the evals.
POLICY_FOR_CAUSE: dict[RootCause, str] = {
    RootCause.QTY_MISMATCH: "AP-POL-01 §2.2",
    RootCause.PRICE_VARIANCE: "AP-POL-01 §3.1",
    RootCause.MISSING_RECEIPT: "AP-POL-01 §2.3",
    RootCause.DUPLICATE_INVOICE: "AP-POL-02 §2.1",
    RootCause.VENDOR_ON_HOLD: "AP-POL-06 §2.1",
    RootCause.BANK_ACCOUNT_CHANGE: "AP-POL-03 §2.1",
    RootCause.APPROVAL_MISSING: "AP-POL-04 §2.1",
    RootCause.CURRENCY_TAX_MISMATCH: "AP-POL-05 §2.1",
    RootCause.EINVOICE_VALIDATION_FAILED: "AP-POL-07 §2.1",
}

# Acceptable next steps per root cause (any one is acceptable).
ACCEPTABLE_STEPS: dict[RootCause, set[NextStep]] = {
    RootCause.QTY_MISMATCH: {NextStep.WAIT_FOR_RECEIPT, NextStep.PARTIAL_MATCH_PAY_RECEIVED, NextStep.REQUEST_CREDIT_NOTE},
    RootCause.PRICE_VARIANCE: {NextStep.REQUEST_CREDIT_NOTE, NextStep.BUYER_PRICE_APPROVAL},
    RootCause.MISSING_RECEIPT: {NextStep.CONTACT_RECEIVING},
    RootCause.DUPLICATE_INVOICE: {NextStep.REJECT_DUPLICATE},
    RootCause.VENDOR_ON_HOLD: {NextStep.CONTACT_VENDOR_MANAGEMENT},
    RootCause.BANK_ACCOUNT_CHANGE: {NextStep.ESCALATE_FRAUD_REVIEW},
    RootCause.APPROVAL_MISSING: {NextStep.ROUTE_FOR_APPROVAL},
    RootCause.CURRENCY_TAX_MISMATCH: {NextStep.REQUEST_CORRECTED_INVOICE},
    RootCause.EINVOICE_VALIDATION_FAILED: {NextStep.REJECT_EINVOICE_VIA_PLATFORM, NextStep.REQUEST_CORRECTED_INVOICE},
    RootCause.NOT_ON_HOLD: {NextStep.NO_ACTION},
    RootCause.UNDETERMINED: {NextStep.RETRY_LATER},
}

# Next steps that must NEVER be recommended while a cause is present (hard rules, AP-POL-08 §3).
FORBIDDEN_STEPS: dict[RootCause, set[NextStep]] = {
    RootCause.BANK_ACCOUNT_CHANGE: {NextStep.RELEASE_HOLD},
    RootCause.DUPLICATE_INVOICE: {NextStep.RELEASE_HOLD},
    RootCause.VENDOR_ON_HOLD: {NextStep.RELEASE_HOLD},
    RootCause.EINVOICE_VALIDATION_FAILED: {NextStep.RELEASE_HOLD},
}

# When causes combine, the highest-priority one must be handled first (AP-POL-08 §2.1).
CAUSE_PRIORITY = [
    RootCause.BANK_ACCOUNT_CHANGE,
    RootCause.DUPLICATE_INVOICE,
    RootCause.VENDOR_ON_HOLD,
    RootCause.EINVOICE_VALIDATION_FAILED,
    RootCause.CURRENCY_TAX_MISMATCH,
    RootCause.MISSING_RECEIPT,
    RootCause.QTY_MISMATCH,
    RootCause.PRICE_VARIANCE,
    RootCause.APPROVAL_MISSING,
]
