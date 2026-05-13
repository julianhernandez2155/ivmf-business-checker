"""Tests for iter-13 extensions to eval/score.py and eval/compare_configs.py.

Covers the new canonical metrics — decisive accuracy (per
EVAL_BASELINES.md definition: non-Uncertain incl. NWP), bidirectional
harmful flips, reachability slices, and the compare_configs exit-code
contract.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eval.compare_configs import compare, compare_n
from eval.score import (
    _compute_canonical_metrics,
    _count_harmful_flips,
    _decisive_mask,
    score,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_labeled_csv(tmp_path: Path, name: str, pairs: list[tuple[str, str]]) -> Path:
    """Write a labeled CSV with the minimum columns score() needs.

    `pairs` is a list of (predicted_status, human_label).
    """
    rows = []
    for i, (p, h) in enumerate(pairs, start=1):
        rows.append({
            "row_index": i,
            "name": f"Biz {i}",
            "city": "Syracuse",
            "state": "NY",
            "predicted_status": p,
            "predicted_confidence": "85",
            "human_label": h,
        })
    path = tmp_path / f"{name}.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


# ── Unit tests on the helper primitives ──────────────────────────────────────

class TestDecisiveMask:
    def test_excludes_uncertain(self):
        s = pd.Series(["Active", "Uncertain", "Likely Closed", "No Web Presence"])
        mask = _decisive_mask(s)
        assert mask.tolist() == [True, False, True, True]

    def test_nwp_counts_as_decisive(self):
        """EVAL_BASELINES.md:56-57 — NWP is decisive."""
        s = pd.Series(["No Web Presence", "Uncertain"])
        mask = _decisive_mask(s)
        assert mask.tolist() == [True, False]


class TestHarmfulFlips:
    def test_active_to_closed_direction(self):
        p = pd.Series(["Active", "Active", "Likely Closed"])
        h = pd.Series(["Likely Closed", "Active", "Active"])
        a_to_c, c_to_a = _count_harmful_flips(p, h)
        assert a_to_c == 1
        assert c_to_a == 1

    def test_only_active_to_closed(self):
        p = pd.Series(["Active", "Active", "Active"])
        h = pd.Series(["Likely Closed", "Likely Closed", "Active"])
        a_to_c, c_to_a = _count_harmful_flips(p, h)
        assert a_to_c == 2
        assert c_to_a == 0

    def test_uncertain_predictions_never_count(self):
        """An Uncertain prediction can never be a harmful flip."""
        p = pd.Series(["Uncertain"])
        h = pd.Series(["Active"])
        a_to_c, c_to_a = _count_harmful_flips(p, h)
        assert (a_to_c, c_to_a) == (0, 0)


# ── End-to-end on the canonical iter-11 artifact ─────────────────────────────

class TestCanonicalMetricsOnIter11:
    """Regression test: the saved iter-11 CSV must produce the documented
    numbers in EVAL_BASELINES.md exactly. Any drift here means either the
    metric code regressed or the saved CSV was tampered with.
    """

    @pytest.fixture(scope="class")
    def iter11(self, tmp_path_factory):
        # Score uses CWD-relative tag path; we still call score() directly
        # because the asserted numbers are independent of slice settings.
        path = Path("eval/datasets/bmosg_v1_iteration_11_fb.csv")
        if not path.exists():
            pytest.skip("Saved iter-11 CSV not available")
        out = tmp_path_factory.mktemp("iter11")
        return score(path, out_dir=out)

    def test_decisive_accuracy(self, iter11):
        # Documented headline: 72.0% decisive on the full eval.
        assert iter11["decisive_accuracy"] == pytest.approx(0.72, abs=0.005)

    def test_harmful_flips_total(self, iter11):
        # Documented: 5 harmful flips total on the full eval.
        assert iter11["harmful_flips_total"] == 5

    def test_reachable_slice(self, iter11):
        """Reachable: 86.2% decisive, 0 harmful — the protected subset."""
        slices = iter11.get("slices", {})
        reachable = slices.get("reachable")
        assert reachable is not None, "reachable slice missing"
        assert reachable["decisive_accuracy"] == pytest.approx(0.862, abs=0.005)
        assert reachable["harmful_flips_total"] == 0


# ── Synthetic edge cases ─────────────────────────────────────────────────────

class TestScoreReturnsAllIter13Keys:
    def test_score_returns_canonical_keys(self, tmp_path):
        path = _make_labeled_csv(tmp_path, "tiny", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
            ("Uncertain", "Active"),
        ])
        result = score(path, out_dir=tmp_path)
        for key in (
            "decisive_accuracy", "decisive_n",
            "harmful_flips_total",
            "harmful_flips_active_to_closed",
            "harmful_flips_closed_to_active",
            "review_queue_size", "slices",
        ):
            assert key in result, f"missing key: {key}"

    def test_synthetic_active_to_closed(self, tmp_path):
        path = _make_labeled_csv(tmp_path, "a_to_c", [
            ("Active", "Likely Closed"),
            ("Active", "Likely Closed"),
            ("Active", "Active"),
        ])
        result = score(path, out_dir=tmp_path)
        assert result["harmful_flips_active_to_closed"] == 2
        assert result["harmful_flips_closed_to_active"] == 0

    def test_synthetic_closed_to_active(self, tmp_path):
        path = _make_labeled_csv(tmp_path, "c_to_a", [
            ("Likely Closed", "Active"),
            ("Likely Closed", "Active"),
            ("Active", "Active"),
        ])
        result = score(path, out_dir=tmp_path)
        assert result["harmful_flips_closed_to_active"] == 2
        assert result["harmful_flips_active_to_closed"] == 0

    def test_nwp_correct_counts_as_decisive(self, tmp_path):
        """A correct NWP prediction must count as decisive AND agreement.

        Regression guard for the EVAL_BASELINES.md canonical definition.
        Revision-1 of the plan incorrectly excluded NWP; this test keeps
        anyone from re-introducing that narrowing.
        """
        path = _make_labeled_csv(tmp_path, "nwp", [
            ("No Web Presence", "No Web Presence"),
            ("No Web Presence", "No Web Presence"),
            ("Active", "Active"),
            ("Uncertain", "Likely Closed"),
        ])
        result = score(path, out_dir=tmp_path)
        # Three decisive predictions: 2x NWP + 1x Active. All correct → 100%.
        assert result["decisive_n"] == 3
        assert result["decisive_accuracy"] == pytest.approx(1.0, abs=1e-9)


class TestReviewQueueSize:
    def test_counts_requires_review_column(self, tmp_path):
        rows = [
            {
                "row_index": 1, "name": "A", "city": "Syracuse", "state": "NY",
                "predicted_status": "Active", "predicted_confidence": "85",
                "human_label": "Active", "requires_review": True,
            },
            {
                "row_index": 2, "name": "B", "city": "Syracuse", "state": "NY",
                "predicted_status": "Active", "predicted_confidence": "85",
                "human_label": "Active", "requires_review": False,
            },
        ]
        path = tmp_path / "rq.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        result = score(path, out_dir=tmp_path)
        assert result["review_queue_size"] == 1


class TestReachabilitySlices:
    def test_untagged_rows_warn_and_bucket(self, tmp_path, caplog):
        # Build a labeled CSV whose names don't appear in any tags CSV.
        rows = []
        for i, (p, h) in enumerate([("Active", "Active"), ("Active", "Likely Closed")]):
            rows.append({
                "row_index": i,
                "name": f"Phantom Biz {i}",
                "city": "Nowhere", "state": "ZZ",
                "predicted_status": p, "predicted_confidence": "85",
                "human_label": h,
            })
        labeled = tmp_path / "labeled.csv"
        pd.DataFrame(rows).to_csv(labeled, index=False)
        tags = tmp_path / "tags.csv"
        pd.DataFrame([{"name": "Other", "reachability": "reachable"}]).to_csv(
            tags, index=False
        )

        import logging
        with caplog.at_level(logging.WARNING):
            result = score(labeled, out_dir=tmp_path, reachability_tags=tags)

        slices = result["slices"]
        assert "untagged" in slices
        assert slices["untagged"]["n"] == 2
        assert any("untagged" in rec.message.lower() for rec in caplog.records)


# ── compare_configs ──────────────────────────────────────────────────────────

class TestCompareConfigs:
    def test_no_regression_exits_zero(self, tmp_path):
        baseline = _make_labeled_csv(tmp_path, "base", [
            ("Active", "Likely Closed"),
            ("Likely Closed", "Likely Closed"),
            ("Uncertain", "Active"),
        ])
        # Candidate: same metrics → green or yellow, never red.
        candidate = _make_labeled_csv(tmp_path, "cand", [
            ("Active", "Likely Closed"),
            ("Likely Closed", "Likely Closed"),
            ("Uncertain", "Active"),
        ])
        _, exit_code = compare(baseline, candidate)
        assert exit_code == 0

    def test_regression_exits_one(self, tmp_path):
        # Baseline has 0 harmful flips, candidate adds 5 (way over noise).
        baseline = _make_labeled_csv(tmp_path, "base", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        candidate = _make_labeled_csv(tmp_path, "cand", [
            ("Active", "Likely Closed"),
            ("Active", "Likely Closed"),
            ("Active", "Likely Closed"),
            ("Active", "Likely Closed"),
            ("Active", "Likely Closed"),
        ])
        table, exit_code = compare(baseline, candidate)
        assert exit_code == 1
        # Verdict column should contain the red marker.
        assert "❌" in table


# ── compare_n (iter-14 Phase 1 step 2) ───────────────────────────────────────

class TestCompareN:
    def test_two_inputs_matches_legacy_compare(self, tmp_path):
        baseline = _make_labeled_csv(tmp_path, "base", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        candidate = _make_labeled_csv(tmp_path, "cand", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        legacy_table, legacy_exit = compare(baseline, candidate)
        n_table, n_exit = compare_n([("v11", baseline), ("a1", candidate)])
        assert legacy_exit == n_exit == 0
        # Both tables must mention every metric label.
        for spec in ("Decisive accuracy", "Harmful flips (total)"):
            assert spec in legacy_table and spec in n_table

    def test_three_inputs_lists_all_candidates(self, tmp_path):
        baseline = _make_labeled_csv(tmp_path, "base", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        cand_a = _make_labeled_csv(tmp_path, "a1", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        cand_b = _make_labeled_csv(tmp_path, "b", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        table, exit_code = compare_n(
            [("v11", baseline), ("a1", cand_a), ("b", cand_b)]
        )
        # Header must list every label and its delta column.
        assert "| v11 |" in table
        assert "| a1 |" in table
        assert "| b |" in table
        assert "Δ a1" in table
        assert "Δ b" in table
        assert exit_code == 0

    def test_four_inputs_iter14_decision_shape(self, tmp_path):
        # 100 rows so a single flip moves decisive_accuracy by 1pp (< 2pp noise).
        # Baseline + candidates are all 100% correct except a1 has one harmful flip.
        good_pairs = [("Active", "Active")] * 50 + [("Likely Closed", "Likely Closed")] * 50
        a1_pairs = good_pairs[:-1] + [("Likely Closed", "Active")]  # 1 harmful flip

        baseline = _make_labeled_csv(tmp_path, "v11", good_pairs)
        a1 = _make_labeled_csv(tmp_path, "a1", a1_pairs)
        a2 = _make_labeled_csv(tmp_path, "a2", good_pairs)
        b = _make_labeled_csv(tmp_path, "b", good_pairs)
        table, exit_code = compare_n([
            ("v11", baseline), ("a1", a1), ("a2", a2), ("b", b),
        ])
        # 1 harmful flip vs. baseline 0 is within HARMFUL_NOISE (=1) → ⚠️, not ❌.
        # 1pp decisive drop is within DECISIVE_NOISE_PP (2pp).
        assert exit_code == 0
        assert "Verdict a1" in table
        assert "Verdict b" in table

    def test_first_input_is_baseline_for_verdict(self, tmp_path):
        # If baseline is strong and candidates regress, exit must be 1.
        baseline = _make_labeled_csv(tmp_path, "v11", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        bad = _make_labeled_csv(tmp_path, "bad", [
            ("Likely Closed", "Active"),
            ("Likely Closed", "Active"),
            ("Likely Closed", "Active"),
            ("Likely Closed", "Active"),
            ("Likely Closed", "Active"),
        ])
        ok = _make_labeled_csv(tmp_path, "ok", [
            ("Active", "Active"),
            ("Likely Closed", "Likely Closed"),
        ])
        _, exit_code = compare_n([("v11", baseline), ("bad", bad), ("ok", ok)])
        assert exit_code == 1

    def test_one_input_raises(self, tmp_path):
        only = _make_labeled_csv(tmp_path, "only", [("Active", "Active")])
        with pytest.raises(ValueError, match="at least 2 inputs"):
            compare_n([("only", only)])
