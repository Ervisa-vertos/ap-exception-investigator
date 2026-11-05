"""Paths and settings (env-overridable)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def erp_db_path() -> Path:
    return Path(os.getenv("AP_ERP_DB", ROOT / "data" / "erp.sqlite"))


def policy_dir() -> Path:
    return Path(os.getenv("AP_POLICY_DIR", ROOT / "data" / "policies"))


MAX_REVIEW_ROUNDS = int(os.getenv("AP_MAX_REVIEW_ROUNDS", "1"))  # Reviewer may send a draft back once
