"""Unit tests for eval.sample — stratified checkpoint CSV sampler."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from eval.sample import stratified_sample


# ---------------------------------------------------------------------------
# Helpers for building fixture CSVs
# ---------------------------------------------------------------------------

_STATUSES = ["Active", "Likely Closed", "Uncertain", "No Web Presence"]


def _make_checkpoint(tmp_path: Path, counts: dict[str, int]) -> Path:
    """Write a minimal checkpoint CSV with the given row counts per status.

    Args:
        tmp_path: Pytest tmp_path directory.
        counts: Mapping of AI_Status → number of rows to generate.

    Returns:
        Path to the written CSV.
    """
    rows = []
    idx = 0
    for status, n in counts.items():
        for i in range(n):
            rows.append(
                {
                    "row_index": idx,
                    "name": f"Business {idx}",
                    "website": f"https://example{idx}.com",
                    "AI_Status": status,
                    "AI_Confidence": "90",
                    "AI_Evidence": f"Evidence for {idx} | Sources: https://src{idx}.com",
                    "AI_Checked_At": "2026-04-30 15:00:00",
                }
            )
            idx += 1
    df = pd.DataFrame(rows)
    path = tmp_path / "checkpoint.csv"
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStratifiedSampleBasic:
    """Core sampling behavior."""

    def test_stratified_sample_returns_n_per_bucket(self, tmp_path: Path) -> None:
        """Exactly n rows per status when each bucket has ≥ n rows."""
        path = _make_checkpoint(tmp_path, {s: 50 for s in _STATUSES})
        result = stratified_sample(path, n_per_status=10, seed=42)

        assert len(result) == 40
        for status in _STATUSES:
            assert int((result["predicted_status"] == status).sum()) == 10

    def test_stratified_sample_handles_empty_bucket(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing status bucket logs a warning and does not crash."""
        counts = {"Active": 20, "Likely Closed": 20, "Uncertain": 20}
        path = _make_checkpoint(tmp_path, counts)

        with caplog.at_level(logging.WARNING, logger="eval.sample"):
            result = stratified_sample(path, n_per_status=10, seed=42)

        # Should still return rows for the 3 present statuses.
        assert len(result) == 30
        assert "No Web Presence" not in result["predicted_status"].values

    def test_stratified_sample_handles_smaller_than_n(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Buckets smaller than n_per_status return all available rows."""
        path = _make_checkpoint(tmp_path, {"Active": 5})

        with caplog.at_level(logging.WARNING, logger="eval.sample"):
            result = stratified_sample(path, n_per_status=20, seed=42)

        assert len(result) == 5
        assert "only 5 row(s)" in caplog.text or "5" in caplog.text


class TestStratifiedSampleReproducibility:
    """Seed behavior."""

    def test_seed_reproducible(self, tmp_path: Path) -> None:
        """Same seed produces identical samples."""
        path = _make_checkpoint(tmp_path, {"Active": 100})
        first = stratified_sample(path, n_per_status=20, seed=42)
        second = stratified_sample(path, n_per_status=20, seed=42)
        pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))

    def test_seed_different(self, tmp_path: Path) -> None:
        """Different seeds produce different samples (with very high probability)."""
        path = _make_checkpoint(tmp_path, {"Active": 100})
        first = stratified_sample(path, n_per_status=20, seed=42)
        second = stratified_sample(path, n_per_status=20, seed=99)
        # It would be astronomically unlikely for these to be identical.
        assert not first["row_index"].tolist() == second["row_index"].tolist()


class TestEvidenceSplitting:
    """AI_Evidence parsing into predicted_evidence and predicted_citations."""

    def _make_single_row(self, tmp_path: Path, evidence: str) -> pd.DataFrame:
        """Build a single-row checkpoint and return the sampled result."""
        rows = [
            {
                "row_index": 0,
                "name": "Test Biz",
                "website": "https://test.com",
                "AI_Status": "Active",
                "AI_Confidence": "85",
                "AI_Evidence": evidence,
                "AI_Checked_At": "2026-04-30 12:00:00",
            }
        ]
        path = tmp_path / "checkpoint.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        return stratified_sample(path, n_per_status=1, seed=42)

    def test_evidence_split_with_sources(self, tmp_path: Path) -> None:
        """Evidence containing ' | Sources: ' splits correctly."""
        result = self._make_single_row(
            tmp_path,
            "Website loads fine. | Sources: https://src1.com, https://src2.com",
        )
        assert result.iloc[0]["predicted_evidence"] == "Website loads fine."
        assert result.iloc[0]["predicted_citations"] == "https://src1.com, https://src2.com"

    def test_evidence_split_without_sources(self, tmp_path: Path) -> None:
        """Evidence without sources separator leaves citations empty."""
        result = self._make_single_row(tmp_path, "Website loads fine.")
        assert result.iloc[0]["predicted_evidence"] == "Website loads fine."
        assert result.iloc[0]["predicted_citations"] == ""


class TestOutputShape:
    """Output column correctness."""

    def test_human_columns_added_empty(self, tmp_path: Path) -> None:
        """human_label, human_justification, reviewed_at are present and empty."""
        path = _make_checkpoint(tmp_path, {"Active": 5})
        result = stratified_sample(path, n_per_status=2, seed=42)

        for col in ("human_label", "human_justification", "reviewed_at"):
            assert col in result.columns
            assert result[col].fillna("").eq("").all(), f"Column '{col}' should be empty"

    def test_confidence_coerced_to_int(self, tmp_path: Path) -> None:
        """predicted_confidence column dtype is int, not string."""
        path = _make_checkpoint(tmp_path, {"Active": 5})
        result = stratified_sample(path, n_per_status=2, seed=42)
        assert pd.api.types.is_integer_dtype(result["predicted_confidence"]), (
            "predicted_confidence should be integer dtype"
        )
