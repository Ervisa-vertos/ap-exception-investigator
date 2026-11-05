"""Step 2 tests: the synthetic data is reproducible, complete, and in sync with the policy text."""

import hashlib
import json

from ap_investigator.config import policy_dir
from ap_investigator.domain import (APPROVAL_LIMIT_EUR, BANK_CHANGE_WINDOW_DAYS,
                                    DUPLICATE_WINDOW_DAYS, PRICE_TOLERANCE_PCT)
from ap_investigator.erp.generator import build


def test_same_seed_gives_identical_data(tmp_path):
    a, b = tmp_path / "a.sqlite", tmp_path / "b.sqlite"
    build(42, a)
    build(42, b)
    assert hashlib.md5(a.read_bytes()).hexdigest() == hashlib.md5(b.read_bytes()).hexdigest()


def test_every_scenario_is_generated(tmp_path):
    build(42, tmp_path / "erp.sqlite", tmp_path / "cases.jsonl")
    cases = [json.loads(line) for line in open(tmp_path / "cases.jsonl", encoding="utf-8")]
    scenarios = {c["scenario"] for c in cases}
    for s in ["qty_mismatch", "price_variance", "missing_receipt", "duplicate", "vendor_on_hold",
              "bank_change", "approval_missing", "currency_tax", "einvoice_rejected"]:
        assert s in scenarios, f"missing scenario: {s}"
    assert len(cases) >= 40


def test_code_thresholds_match_policy_text():
    text = " ".join(p.read_text(encoding="utf-8") for p in policy_dir().glob("*.md"))
    assert f"{PRICE_TOLERANCE_PCT}%" in text
    assert f"last {BANK_CHANGE_WINDOW_DAYS} days" in text
    assert f"EUR {APPROVAL_LIMIT_EUR:,.0f}" in text
    assert f"last {DUPLICATE_WINDOW_DAYS} days" in text