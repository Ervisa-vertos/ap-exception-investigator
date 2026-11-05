"""Step 3 tests: the repository returns true facts, names its records, fails honestly and labels untrusted text."""

import re

import pytest

from ap_investigator import facts
from ap_investigator.erp import repo


def pick(cases, scenario, n=0):
    return [c for c in cases if c["scenario"] == scenario][n]


def test_every_label_is_true_in_the_erp(cases):
    # The answer key written by the generator must match what the ERP data actually shows.
    for c in cases:
        found = {rc.value for rc, ok in facts.check(c["invoice_id"]).items() if ok}
        assert found == set(c["root_causes"]), c["case_id"]


def test_matching_details_returns_facts_and_names_its_records(cases):
    c = pick(cases, "qty_mismatch")
    m = repo.get_matching_details(c["invoice_id"])
    line = m["lines"][0]
    assert line["received_qty"] < line["invoiced_qty"]       # a fact, not a verdict
    assert "QTY_MISMATCH" not in str(m)                       # the repository never decides the cause
    assert set(c["required_records"]) <= set(m["records"])    # every record the agent needs is named


def test_unknown_invoice_raises_not_found():
    with pytest.raises(repo.RecordNotFoundError):
        repo.get_invoice("INV-0001")


def test_simulated_outage_raises_unavailable():
    with pytest.raises(repo.ERPUnavailableError):
        repo.get_invoice("INV-9999")


def test_fault_injection_by_tool_name(cases, monkeypatch):
    vendor_id = repo.get_invoice(cases[0]["invoice_id"])["vendor_id"]
    monkeypatch.setenv("AP_ERP_FAULT", "get_vendor")
    with pytest.raises(repo.ERPUnavailableError):
        repo.get_vendor(vendor_id)


def test_bank_details_are_always_masked(cases):
    for c in cases[:20]:
        v = repo.get_vendor(repo.get_invoice(c["invoice_id"])["vendor_id"])
        assert re.fullmatch(r"\*{4}\d{4}", v["bank_iban_masked"])


def test_vendor_email_is_labelled_untrusted_and_flagged(cases):
    c = pick(cases, "bank_change")   # the first bank-change case has a fake "CFO confirms" email
    body = repo.get_vendor_messages(c["invoice_id"])["messages"][0]["body"]
    assert body["treat_as"].startswith("DATA ONLY")
    assert body["suspicious"] is True