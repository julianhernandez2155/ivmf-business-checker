"""Tests for the Phase 0 retrieval-stability analyzer.

The paid runs are network-bound and tested manually. The pure analysis
functions (`_parse_citations`, `_jaccard`, `_bucket`, `diff_runs`, `classify`)
are the testable surface and are exercised here with fabricated inputs.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest

# Make `eval` package importable as `business_checker.eval` is not on path.
HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent.parent))

from eval.measure_retrieval_stability import (  # noqa: E402
    JACCARD_STABLE_THRESHOLD,
    RowDiff,
    _bucket,
    _jaccard,
    _parse_citations,
    classify,
    diff_runs,
)


class TestParseCitations:
    def test_empty_string_returns_empty_tuple(self):
        assert _parse_citations("") == ()

    def test_none_returns_empty_tuple(self):
        assert _parse_citations(None) == ()

    def test_single_citation(self):
        assert _parse_citations("https://example.com") == ("https://example.com",)

    def test_strips_trailing_slash_and_lowercases(self):
        result = _parse_citations("HTTPS://Example.com/, https://example.com")
        assert result == ("https://example.com",)

    def test_deduplicates_and_sorts(self):
        result = _parse_citations("https://b.com, https://a.com, https://b.com")
        assert result == ("https://a.com", "https://b.com")

    def test_strips_whitespace(self):
        result = _parse_citations("  https://a.com  ,  https://b.com  ")
        assert result == ("https://a.com", "https://b.com")


class TestJaccard:
    def test_identical_sets_return_one(self):
        a = ("https://a.com", "https://b.com")
        assert _jaccard(a, a) == 1.0

    def test_disjoint_sets_return_zero(self):
        a = ("https://a.com",)
        b = ("https://b.com",)
        assert _jaccard(a, b) == 0.0

    def test_partial_overlap(self):
        a = ("https://a.com", "https://b.com")
        b = ("https://b.com", "https://c.com")
        # intersection = 1, union = 3
        assert _jaccard(a, b) == pytest.approx(1 / 3)

    def test_empty_both_returns_one(self):
        # NWP rows: no citations in either pass means perfect agreement.
        assert _jaccard((), ()) == 1.0

    def test_one_empty_returns_zero(self):
        assert _jaccard((), ("https://a.com",)) == 0.0


class TestBucket:
    def test_stable_stable(self):
        assert _bucket(citation_stable=True, verdict_changed=False) == "stable_stable"

    def test_stable_drift(self):
        # The reasoning-drift signal: citations stable, verdict moved.
        assert _bucket(citation_stable=True, verdict_changed=True) == "stable_drift"

    def test_drift_stable(self):
        # Reasoning robust to retrieval churn.
        assert _bucket(citation_stable=False, verdict_changed=False) == "drift_stable"

    def test_drift_drift(self):
        # Mixed — can't fully attribute.
        assert _bucket(citation_stable=False, verdict_changed=True) == "drift_drift"


def _make_row(
    row_index: int,
    name: str,
    status_p1: str,
    status_p2: str,
    citations_p1: str,
    citations_p2: str,
    err_p1: str = "",
    err_p2: str = "",
) -> dict:
    return {
        "row_index": row_index,
        "name_p1": name,
        "name_p2": name,
        "predicted_status_p1": status_p1,
        "predicted_status_p2": status_p2,
        "predicted_confidence_p1": "90",
        "predicted_confidence_p2": "85",
        "predicted_citations_p1": citations_p1,
        "predicted_citations_p2": citations_p2,
        "rerun_error_p1": err_p1,
        "rerun_error_p2": err_p2,
    }


def _build_merged_dfs(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a merged-rows list into the pre-merge p1 / p2 frames diff_runs expects."""
    df1 = pd.DataFrame(
        [
            {
                "row_index": r["row_index"],
                "name": r["name_p1"],
                "predicted_status": r["predicted_status_p1"],
                "predicted_confidence": r["predicted_confidence_p1"],
                "predicted_citations": r["predicted_citations_p1"],
                "rerun_error": r["rerun_error_p1"],
            }
            for r in rows
        ]
    )
    df2 = pd.DataFrame(
        [
            {
                "row_index": r["row_index"],
                "name": r["name_p2"],
                "predicted_status": r["predicted_status_p2"],
                "predicted_confidence": r["predicted_confidence_p2"],
                "predicted_citations": r["predicted_citations_p2"],
                "rerun_error": r["rerun_error_p2"],
            }
            for r in rows
        ]
    )
    return df1, df2


class TestDiffRuns:
    def test_stable_stable_row(self):
        df1, df2 = _build_merged_dfs([
            _make_row(1, "Acme", "Active", "Active",
                      "https://acme.com, https://acme.com/about",
                      "https://acme.com, https://acme.com/about"),
        ])
        diffs = diff_runs(df1, df2)
        assert len(diffs) == 1
        assert diffs[0].bucket == "stable_stable"
        assert diffs[0].jaccard == 1.0

    def test_stable_drift_row(self):
        # Same citations, different verdict — reasoning drift.
        df1, df2 = _build_merged_dfs([
            _make_row(1, "Acme", "Active", "Likely Closed",
                      "https://acme.com, https://acme.com/about",
                      "https://acme.com, https://acme.com/about"),
        ])
        diffs = diff_runs(df1, df2)
        assert diffs[0].bucket == "stable_drift"

    def test_drift_stable_row(self):
        df1, df2 = _build_merged_dfs([
            _make_row(1, "Acme", "Active", "Active",
                      "https://a.com",
                      "https://b.com"),
        ])
        diffs = diff_runs(df1, df2)
        assert diffs[0].bucket == "drift_stable"
        assert diffs[0].jaccard == 0.0

    def test_drift_drift_row(self):
        df1, df2 = _build_merged_dfs([
            _make_row(1, "Acme", "Active", "Likely Closed",
                      "https://a.com",
                      "https://b.com"),
        ])
        diffs = diff_runs(df1, df2)
        assert diffs[0].bucket == "drift_drift"

    def test_errored_row_is_excluded(self):
        df1, df2 = _build_merged_dfs([
            _make_row(1, "Acme", "Active", "Active",
                      "https://a.com", "", err_p2="rate limit"),
            _make_row(2, "Beta", "Active", "Active",
                      "https://b.com", "https://b.com"),
        ])
        diffs = diff_runs(df1, df2)
        assert len(diffs) == 1
        assert diffs[0].row_index == 2

    def test_jaccard_threshold_boundary(self):
        # Build a row whose Jaccard is just below 0.80 — must be `drift`.
        # 4 of 5 in common → Jaccard = 4/6 ≈ 0.667 (< 0.80).
        df1, df2 = _build_merged_dfs([
            _make_row(1, "Acme", "Active", "Active",
                      "https://a.com, https://b.com, https://c.com, https://d.com, https://e.com",
                      "https://a.com, https://b.com, https://c.com, https://d.com, https://f.com"),
        ])
        diffs = diff_runs(df1, df2)
        assert diffs[0].citation_set_stable is False
        assert diffs[0].bucket == "drift_stable"


class TestClassify:
    @staticmethod
    def _make_diff(bucket: str, jaccard: float) -> RowDiff:
        citation_stable = jaccard >= JACCARD_STABLE_THRESHOLD
        verdict_changed = bucket in ("stable_drift", "drift_drift")
        return RowDiff(
            row_index=1, name="x",
            status_pass1="A", status_pass2="A" if not verdict_changed else "B",
            confidence_pass1="50", confidence_pass2="50",
            citations_pass1=(), citations_pass2=(),
            jaccard=jaccard, citation_set_stable=citation_stable,
            verdict_changed=verdict_changed, bucket=bucket,
        )

    def test_empty_returns_insufficient_data(self):
        classification, med, counts = classify([])
        assert classification == "insufficient_data"
        assert med == 0.0
        assert sum(counts.values()) == 0

    def test_reasoning_dominant(self):
        # 30% stable_drift, median Jaccard 0.85 → reasoning-dominant.
        diffs = (
            [self._make_diff("stable_drift", 0.85)] * 3
            + [self._make_diff("stable_stable", 0.95)] * 7
        )
        classification, med, _ = classify(diffs)
        assert classification == "reasoning-dominant"
        assert med == pytest.approx(0.90, abs=0.05)

    def test_retrieval_dominant(self):
        # 60% drift_* rows with median Jaccard < 0.50.
        diffs = (
            [self._make_diff("drift_drift", 0.20)] * 3
            + [self._make_diff("drift_stable", 0.30)] * 3
            + [self._make_diff("stable_stable", 0.95)] * 4
        )
        classification, med, _ = classify(diffs)
        assert classification == "retrieval-dominant"
        assert med < 0.50

    def test_both_when_thresholds_not_met(self):
        # Mixed signal that doesn't trigger either rule.
        diffs = (
            [self._make_diff("stable_drift", 0.85)] * 1
            + [self._make_diff("drift_drift", 0.40)] * 2
            + [self._make_diff("stable_stable", 0.95)] * 7
        )
        classification, _, _ = classify(diffs)
        assert classification == "both"
