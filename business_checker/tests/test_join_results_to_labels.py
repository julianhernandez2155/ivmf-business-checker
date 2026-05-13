"""Tests for the iter-13 join helper.

The join helper exists to attach historical human labels onto fresh
Results.xlsx output so Phase A gate A2 can run. These tests cover the
contract: normalized join keys, unmatched-row counts, preserved human
labels, and Phase A gate A2's actual happy path.
"""

from __future__ import annotations

import logging

import openpyxl
import pandas as pd
import pytest

from eval.join_results_to_labels import (
    _make_join_key,
    _normalize,
    join_results_to_labels,
)


def _write_results_xlsx(path, rows: list[dict]) -> None:
    """Mini helper: write a Results.xlsx with the headers run_checker emits."""
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["name", "website", "city", "state", "status",
               "confidence", "evidence", "checked_at"]
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    wb.save(path)


def test_normalize_strips_punctuation_and_lowercases():
    assert _normalize("Aabon 2, Inc.") == "aabon 2 inc"
    assert _normalize("St. Louis") == "st louis"
    assert _normalize(None) == ""


def test_join_key_combines_three_parts():
    assert _make_join_key("Acme", "Syracuse", "NY") == "acme|syracuse|ny"


def test_happy_path_all_match(tmp_path, caplog):
    results_path = tmp_path / "Results.xlsx"
    labels_path = tmp_path / "labels.csv"
    out_path = tmp_path / "joined.csv"

    _write_results_xlsx(results_path, [
        {"name": "Acme LLC", "website": "https://acme.com",
         "city": "Syracuse", "state": "NY", "status": "Active",
         "confidence": 90, "evidence": "loads", "checked_at": "2026-05-12"},
        {"name": "Zenith Corp", "website": "https://zenith.com",
         "city": "Buffalo", "state": "NY", "status": "Likely Closed",
         "confidence": 80, "evidence": "dead site", "checked_at": "2026-05-12"},
    ])
    pd.DataFrame([
        {"row_index": 2, "name": "Acme LLC", "city": "Syracuse",
         "state": "NY", "human_label": "Active",
         "human_justification": "site loads, products active"},
        {"row_index": 3, "name": "Zenith Corp", "city": "Buffalo",
         "state": "NY", "human_label": "Likely Closed",
         "human_justification": "site dead"},
    ]).to_csv(labels_path, index=False)

    counts = join_results_to_labels(results_path, labels_path, out_path)

    assert counts["matched"] == 2
    assert counts["unmatched_results"] == 0
    assert counts["unmatched_labels"] == 0

    out = pd.read_csv(out_path)
    assert len(out) == 2
    # Human labels are preserved verbatim (frozen ground truth).
    assert set(out["human_label"]) == {"Active", "Likely Closed"}
    # Fresh predictions come from the Results xlsx.
    assert set(out["predicted_status"]) == {"Active", "Likely Closed"}


def test_unmatched_results_logged_and_skipped(tmp_path, caplog):
    results_path = tmp_path / "Results.xlsx"
    labels_path = tmp_path / "labels.csv"
    out_path = tmp_path / "joined.csv"

    _write_results_xlsx(results_path, [
        {"name": "Acme", "website": "https://acme.com",
         "city": "Syracuse", "state": "NY", "status": "Active",
         "confidence": 90, "evidence": "ok", "checked_at": "2026-05-12"},
        {"name": "Unlabeled", "website": "", "city": "Albany", "state": "NY",
         "status": "Active", "confidence": 75, "evidence": "ok",
         "checked_at": "2026-05-12"},
    ])
    pd.DataFrame([
        {"name": "Acme", "city": "Syracuse", "state": "NY",
         "human_label": "Active"},
    ]).to_csv(labels_path, index=False)

    with caplog.at_level(logging.WARNING):
        counts = join_results_to_labels(results_path, labels_path, out_path)

    assert counts["matched"] == 1
    assert counts["unmatched_results"] == 1
    assert counts["unmatched_labels"] == 0
    # Skipped, not silently merged with NaN labels.
    out = pd.read_csv(out_path)
    assert len(out) == 1
    assert out["human_label"].tolist() == ["Active"]
    assert any("unmatched" in rec.message.lower() or "no matching label" in rec.message.lower()
               for rec in caplog.records)


def test_unmatched_labels_logged_and_skipped(tmp_path, caplog):
    results_path = tmp_path / "Results.xlsx"
    labels_path = tmp_path / "labels.csv"
    out_path = tmp_path / "joined.csv"

    _write_results_xlsx(results_path, [
        {"name": "Acme", "website": "", "city": "Syracuse",
         "state": "NY", "status": "Active", "confidence": 90,
         "evidence": "ok", "checked_at": "2026-05-12"},
    ])
    pd.DataFrame([
        {"name": "Acme", "city": "Syracuse", "state": "NY", "human_label": "Active"},
        {"name": "Phantom", "city": "Nowhere", "state": "ZZ",
         "human_label": "Likely Closed"},
    ]).to_csv(labels_path, index=False)

    with caplog.at_level(logging.WARNING):
        counts = join_results_to_labels(results_path, labels_path, out_path)

    assert counts["matched"] == 1
    assert counts["unmatched_labels"] == 1
    assert any("no matching results row" in rec.message.lower()
               or "no matching" in rec.message.lower()
               for rec in caplog.records)


def test_join_is_case_and_punctuation_insensitive(tmp_path):
    """Same business in different casing/punctuation joins correctly."""
    results_path = tmp_path / "Results.xlsx"
    labels_path = tmp_path / "labels.csv"
    out_path = tmp_path / "joined.csv"

    _write_results_xlsx(results_path, [
        {"name": "AABON 2, INC", "website": "", "city": "BIRMINGHAM",
         "state": "AL", "status": "Active", "confidence": 90,
         "evidence": "ok", "checked_at": "2026-05-12"},
    ])
    pd.DataFrame([
        {"name": "Aabon 2 Inc", "city": "Birmingham", "state": "al",
         "human_label": "Active"},
    ]).to_csv(labels_path, index=False)

    counts = join_results_to_labels(results_path, labels_path, out_path)
    assert counts["matched"] == 1
