"""Unit tests for eval.score — metric computation and report generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eval.score import score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUSES = ["Active", "Likely Closed", "Uncertain", "No Web Presence"]


def _make_labeled_csv(
    tmp_path: Path,
    predictions: list[str],
    labels: list[str],
    confidences: list[int] | None = None,
) -> Path:
    """Write a minimal labeled CSV for scoring tests.

    Args:
        tmp_path: Pytest tmp_path directory.
        predictions: List of predicted_status values.
        labels: List of human_label values (same length as predictions).
        confidences: Optional list of predicted_confidence ints.

    Returns:
        Path to the written CSV.
    """
    n = len(predictions)
    if confidences is None:
        confidences = [90] * n
    rows = {
        "row_index": list(range(n)),
        "name": [f"Biz {i}" for i in range(n)],
        "website": [f"https://example{i}.com" for i in range(n)],
        "predicted_status": predictions,
        "predicted_confidence": confidences,
        "predicted_evidence": ["Evidence text"] * n,
        "predicted_citations": [""] * n,
        "predicted_checked_at": ["2026-04-30 15:00:00"] * n,
        "human_label": labels,
        "human_justification": ["Checked manually"] * n,
        "reviewed_at": ["2026-04-30 16:00:00"] * n,
    }
    path = tmp_path / "labeled.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Agreement rate tests
# ---------------------------------------------------------------------------


class TestAgreementRate:
    """Overall agreement rate computation."""

    def test_perfect_agreement(self, tmp_path: Path) -> None:
        """All predictions match → agreement = 1.0."""
        preds = ["Active"] * 5 + ["Likely Closed"] * 5
        labels = preds.copy()
        path = _make_labeled_csv(tmp_path, preds, labels)

        result = score(path, out_dir=tmp_path / "reports")

        assert result["overall_agreement"] == pytest.approx(1.0)
        # CI upper bound is always ≤ 1.0; lower bound at n=10 is roughly 0.72.
        assert result["agreement_ci_high"] <= 1.0
        assert result["agreement_ci_low"] >= 0.6

    def test_zero_agreement(self, tmp_path: Path) -> None:
        """No predictions match → agreement = 0.0."""
        preds = ["Active"] * 10
        labels = ["Likely Closed"] * 10
        path = _make_labeled_csv(tmp_path, preds, labels)

        result = score(path, out_dir=tmp_path / "reports")

        assert result["overall_agreement"] == pytest.approx(0.0)

    def test_partial_agreement(self, tmp_path: Path) -> None:
        """8 of 10 match → agreement = 0.8."""
        preds = ["Active"] * 10
        labels = ["Active"] * 8 + ["Likely Closed"] * 2
        path = _make_labeled_csv(tmp_path, preds, labels)

        result = score(path, out_dir=tmp_path / "reports")

        assert result["overall_agreement"] == pytest.approx(0.8)
        # Wilson CI at n=10, p=0.8 should be roughly [0.49, 0.95].
        assert result["agreement_ci_low"] < 0.8
        assert result["agreement_ci_high"] > 0.8


# ---------------------------------------------------------------------------
# Exclusion logic
# ---------------------------------------------------------------------------


class TestExclusion:
    """'Unable to Determine' and empty rows are excluded."""

    def test_unable_to_determine_excluded(self, tmp_path: Path) -> None:
        """UTD rows are excluded from scoring but counted in total."""
        preds = ["Active"] * 10
        # First 8 agree, last 2 are Unable to Determine.
        labels = ["Active"] * 8 + ["Unable to Determine"] * 2
        path = _make_labeled_csv(tmp_path, preds, labels)

        result = score(path, out_dir=tmp_path / "reports")

        # Agreement computed on 8 rows that agree → 100%.
        assert result["overall_agreement"] == pytest.approx(1.0)

    def test_empty_label_excluded(self, tmp_path: Path) -> None:
        """Rows with empty human_label are excluded."""
        preds = ["Active"] * 10
        labels = ["Active"] * 7 + [""] * 3
        path = _make_labeled_csv(tmp_path, preds, labels)

        result = score(path, out_dir=tmp_path / "reports")

        assert result["overall_agreement"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------


class TestConfusionMatrix:
    """Confusion matrix shape and correctness."""

    def test_confusion_matrix_shape(self, tmp_path: Path) -> None:
        """Always returns 4×4 regardless of which statuses appear."""
        preds = ["Active"] * 5 + ["Uncertain"] * 5
        labels = ["Active"] * 5 + ["Uncertain"] * 5
        path = _make_labeled_csv(tmp_path, preds, labels)

        result = score(path, out_dir=tmp_path / "reports")

        cm = result["confusion_matrix"]
        assert len(cm) == 4
        assert all(len(row) == 4 for row in cm)

    def test_confusion_matrix_values(self, tmp_path: Path) -> None:
        """Known disagreements appear in the correct cell.

        sklearn confusion_matrix: rows = y_true (human label), cols = y_pred (predicted).
        STATUS_LABELS order: Active=0, Likely Closed=1, Uncertain=2, No Web Presence=3.
        """
        # human=Likely Closed (true), predicted=Active (pred)  → row 1, col 0 → 3 times.
        # human=Likely Closed (true), predicted=Likely Closed  → row 1, col 1 → 3 times.
        preds = ["Active"] * 3 + ["Likely Closed"] * 3
        labels = ["Likely Closed"] * 3 + ["Likely Closed"] * 3
        path = _make_labeled_csv(tmp_path, preds, labels)

        result = score(path, out_dir=tmp_path / "reports")

        cm = result["confusion_matrix"]
        # Row 1 = Likely Closed (human), col 0 = Active (predicted) → 3.
        assert cm[1][0] == 3
        # Row 1 = Likely Closed (human), col 1 = Likely Closed (predicted) → 3.
        assert cm[1][1] == 3


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    """Calibration curve buckets."""

    def test_calibration_buckets_populated(self, tmp_path: Path) -> None:
        """Rows with confidence in specific buckets appear in those buckets."""
        preds = ["Active"] * 10
        labels = ["Active"] * 10
        confs = [55, 55, 65, 65, 75, 75, 85, 85, 95, 95]
        path = _make_labeled_csv(tmp_path, preds, labels, confidences=confs)

        result = score(path, out_dir=tmp_path / "reports")

        cal = {c["bucket"]: c for c in result["calibration"]}
        assert cal["50–59"]["n"] == 2
        assert cal["60–69"]["n"] == 2
        assert cal["70–79"]["n"] == 2
        assert cal["80–89"]["n"] == 2
        assert cal["90–100"]["n"] == 2
        assert cal["0–49"]["n"] == 0

    def test_calibration_agreement_rate_perfect(self, tmp_path: Path) -> None:
        """100% agreement in a bucket yields agreement_rate = 1.0."""
        preds = ["Active"] * 5
        labels = ["Active"] * 5
        confs = [92] * 5
        path = _make_labeled_csv(tmp_path, preds, labels, confidences=confs)

        result = score(path, out_dir=tmp_path / "reports")

        cal = {c["bucket"]: c for c in result["calibration"]}
        assert cal["90–100"]["agreement_rate"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------


class TestFileOutput:
    """Reports and CSV artifacts are written correctly."""

    def test_score_writes_report(self, tmp_path: Path) -> None:
        """score() writes report.md and confusion_matrix.csv to out_dir."""
        preds = ["Active"] * 5 + ["Likely Closed"] * 5
        labels = preds.copy()
        path = _make_labeled_csv(tmp_path, preds, labels)
        out_dir = tmp_path / "reports"

        score(path, out_dir=out_dir)

        assert (out_dir / "report.md").exists()
        assert (out_dir / "confusion_matrix.csv").exists()

    def test_report_contains_headline(self, tmp_path: Path) -> None:
        """report.md contains the overall agreement line."""
        preds = ["Active"] * 10
        labels = ["Active"] * 8 + ["Likely Closed"] * 2
        path = _make_labeled_csv(tmp_path, preds, labels)
        out_dir = tmp_path / "reports"

        score(path, out_dir=out_dir)

        report_text = (out_dir / "report.md").read_text(encoding="utf-8")
        assert "Overall agreement" in report_text
        assert "Wilson CI" in report_text

    def test_confusion_matrix_csv_shape(self, tmp_path: Path) -> None:
        """confusion_matrix.csv is a 4×4 file with STATUS_LABELS as headers."""
        preds = ["Active"] * 5
        labels = ["Active"] * 5
        path = _make_labeled_csv(tmp_path, preds, labels)
        out_dir = tmp_path / "reports"

        score(path, out_dir=out_dir)

        cm_df = pd.read_csv(out_dir / "confusion_matrix.csv", index_col=0)
        assert cm_df.shape == (4, 4)
