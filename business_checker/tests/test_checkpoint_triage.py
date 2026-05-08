"""Tests for the triage-aware checkpoint changes (added 2026-05-08).

Verifies:
  - save_checkpoint persists requires_review / review_reason / pass_verdicts
  - Old call sites that omit those args still work (backward compat)
  - load_checkpoint returns the new fields
  - rewrite_checkpoint tolerates rows that lack the new fields (old data)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools.checkpoint import (
    FIELDNAMES,
    load_checkpoint,
    rewrite_checkpoint,
    save_checkpoint,
)


@pytest.fixture
def cp_path(tmp_path: Path) -> str:
    """Return a path for a fresh checkpoint file in a temp dir."""
    return str(tmp_path / "checkpoint.csv")


# ── Schema ────────────────────────────────────────────────────────────────────


def test_fieldnames_include_triage_columns() -> None:
    assert "AI_Requires_Review" in FIELDNAMES
    assert "AI_Review_Reason" in FIELDNAMES
    assert "AI_Pass_Verdicts" in FIELDNAMES


# ── save_checkpoint backward compat ───────────────────────────────────────────


def test_save_checkpoint_legacy_signature_still_works(cp_path: str) -> None:
    """Callers that don't pass the new kwargs (GUI, single-pass) should still
    succeed and write FALSE / empty for the triage cols."""
    save_checkpoint(
        cp_path, row_index=2, name="Acme", website="https://acme.com",
        status="Active", confidence="95",
        evidence="Live site with cart", checked_at="2026-05-08 10:00:00",
    )
    rows = load_checkpoint(cp_path)
    assert rows["2"]["AI_Status"] == "Active"
    assert rows["2"]["AI_Requires_Review"] == "FALSE"
    assert rows["2"]["AI_Review_Reason"] == ""
    assert rows["2"]["AI_Pass_Verdicts"] == ""


def test_save_checkpoint_persists_review_metadata(cp_path: str) -> None:
    save_checkpoint(
        cp_path, row_index=3, name="Foo", website="https://foo.com",
        status="Uncertain", confidence="55",
        evidence="hedge evidence", checked_at="2026-05-08 10:01:00",
        requires_review=True,
        review_reason="Status 'Uncertain' has low historical precision",
        pass_verdicts="P1: Uncertain(55) | P2: Likely Closed(72)",
    )
    rows = load_checkpoint(cp_path)
    r = rows["3"]
    assert r["AI_Status"] == "Uncertain"
    assert r["AI_Requires_Review"] == "TRUE"
    assert "low historical precision" in r["AI_Review_Reason"]
    assert "P1: Uncertain" in r["AI_Pass_Verdicts"]
    assert "P2: Likely Closed" in r["AI_Pass_Verdicts"]


def test_save_checkpoint_review_false_explicit(cp_path: str) -> None:
    save_checkpoint(
        cp_path, row_index=4, name="Bar", website="",
        status="Active", confidence="95",
        evidence="auto-trusted", checked_at="2026-05-08 10:02:00",
        requires_review=False,
    )
    rows = load_checkpoint(cp_path)
    assert rows["4"]["AI_Requires_Review"] == "FALSE"


# ── Concurrent appends keep the schema stable ────────────────────────────────


def test_multiple_appends_share_one_header(cp_path: str) -> None:
    save_checkpoint(
        cp_path, row_index=2, name="A", website="",
        status="Active", confidence="95", evidence="x", checked_at="t1",
    )
    save_checkpoint(
        cp_path, row_index=3, name="B", website="",
        status="Likely Closed", confidence="80", evidence="y", checked_at="t2",
        requires_review=True, review_reason="closure low-conf",
    )
    with open(cp_path, encoding="utf-8") as f:
        content = f.read()
    # Header should appear exactly once
    assert content.count("AI_Requires_Review") == 1


# ── rewrite_checkpoint backward compat ───────────────────────────────────────


def test_rewrite_tolerates_legacy_rows_missing_triage_cols(cp_path: str) -> None:
    """Old checkpoints (pre-2026-05-08) lack triage columns. rewrite must
    accept those dicts and write empty strings for the missing fields."""
    legacy_rows = [
        {
            "row_index": "2", "name": "Old", "website": "",
            "AI_Status": "Active", "AI_Confidence": "95",
            "AI_Evidence": "evidence", "AI_Checked_At": "old timestamp",
            # No AI_Requires_Review / AI_Review_Reason / AI_Pass_Verdicts
        }
    ]
    rewrite_checkpoint(cp_path, legacy_rows)
    rows = load_checkpoint(cp_path)
    assert rows["2"]["AI_Status"] == "Active"
    # Missing triage cols default to empty
    assert rows["2"]["AI_Requires_Review"] == ""


def test_rewrite_drops_unknown_extra_keys(cp_path: str) -> None:
    """Defensive: a row with an unknown key (e.g. from a 3rd-party tool)
    shouldn't crash the write."""
    rows_with_extras = [
        {
            "row_index": "2", "name": "X", "website": "",
            "AI_Status": "Active", "AI_Confidence": "95",
            "AI_Evidence": "ev", "AI_Checked_At": "t",
            "AI_Requires_Review": "FALSE", "AI_Review_Reason": "",
            "AI_Pass_Verdicts": "",
            "_internal_debug_field": "ignore me",  # not in FIELDNAMES
        }
    ]
    rewrite_checkpoint(cp_path, rows_with_extras)
    rows = load_checkpoint(cp_path)
    assert rows["2"]["AI_Status"] == "Active"
