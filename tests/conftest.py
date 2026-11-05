"""Every test gets its own freshly generated ERP (seed 42), so tests never share state."""

import json

import pytest

from ap_investigator.erp.generator import build


@pytest.fixture(autouse=True)
def erp(tmp_path, monkeypatch):
    db = tmp_path / "erp.sqlite"
    cases_file = tmp_path / "cases.jsonl"
    build(42, db, cases_file)
    monkeypatch.setenv("AP_ERP_DB", str(db))          # point the repository at this test's database
    monkeypatch.delenv("AP_ERP_FAULT", raising=False)  # no simulated outages unless a test asks
    return [json.loads(line) for line in cases_file.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def cases(erp):
    return erp