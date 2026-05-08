"""Tests for check_business_with_verification (deferred 2-pass mode).

Verifies the merge logic when pass 2 agrees vs disagrees vs fails, and
that auto-trusted pass-1 results skip pass 2 entirely.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tools import check_business as check_module
from tools.check_business import check_business_with_verification


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_result(
    status: str = "Likely Closed",
    confidence: str = "75",
    evidence: str = "stub evidence",
    requires_review: bool = True,
    review_reason: str | None = "stub reason",
    error: str | None = None,
    cost: float = 0.01,
) -> dict:
    """Build a check_business return-shape dict for mocking."""
    return {
        "status":          status,
        "confidence":      confidence,
        "evidence":        evidence,
        "citations":       [],
        "cost_usd":        cost,
        "error":           error,
        "requires_review": requires_review,
        "review_reason":   review_reason,
    }


# ── Skip-pass-2 cases ─────────────────────────────────────────────────────────


class TestVerifySkipsPass2WhenNotNeeded:
    def test_auto_trusted_pass1_skips_pass2(self) -> None:
        """If pass 1 doesn't require review, pass 2 must not run."""
        pass1 = _make_result(
            status="Active", confidence="95",
            requires_review=False, review_reason=None,
        )
        with patch.object(check_module, "check_business", return_value=pass1) as mock:
            result = check_business_with_verification(
                "fake_key", "Acme Corp", "https://acme.com", "City", "ST"
            )
            assert mock.call_count == 1
            assert result["status"] == "Active"
            assert result.get("verifier_ran") is None  # didn't run

    def test_pass1_error_skips_pass2(self) -> None:
        """API errors should not trigger pass 2 — they need human attention."""
        pass1 = _make_result(error="API timeout")
        with patch.object(check_module, "check_business", return_value=pass1) as mock:
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
            assert mock.call_count == 1
            assert result["error"] == "API timeout"


# ── Agreement: pass 2 confirms pass 1 ─────────────────────────────────────────


class TestPass2Agreement:
    def test_agreement_above_floor_promotes_to_auto_trusted(self) -> None:
        """High-confidence Likely Closed confirmed by 2nd pass → auto-trusted."""
        pass1 = _make_result(status="Likely Closed", confidence="82")
        pass2 = _make_result(status="Likely Closed", confidence="85")
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["status"] == "Likely Closed"
        assert result["requires_review"] is False
        assert result["review_reason"] is None
        assert "2-pass agreement" in result["evidence"]
        assert "stable hedge" not in result["evidence"]
        assert result["pass1_status"] == "Likely Closed"
        assert result["pass2_status"] == "Likely Closed"
        assert result["verifier_ran"] is True

    def test_agreement_below_closure_floor_stays_flagged(self) -> None:
        """Likely Closed at 72% confirmed by 2nd pass at 78% — both still
        below the 80% outreach-autotrust floor. Keep flagged for review."""
        pass1 = _make_result(status="Likely Closed", confidence="72")
        pass2 = _make_result(status="Likely Closed", confidence="78")
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["status"] == "Likely Closed"
        assert result["requires_review"] is True
        assert "2-pass agreement on 'Likely Closed'" in result["review_reason"]
        assert result["confidence"] == "78"  # took higher

    def test_agreement_on_uncertain_stays_flagged(self) -> None:
        """Both passes saying 'Uncertain' is stable hedge, not confirmation —
        Uncertain is always review-flagged regardless of agreement."""
        pass1 = _make_result(status="Uncertain", confidence="55")
        pass2 = _make_result(status="Uncertain", confidence="65")
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["status"] == "Uncertain"
        assert result["requires_review"] is True
        assert "stable hedge" in result["evidence"]

    def test_agreement_on_active_high_confidence_promotes(self) -> None:
        pass1 = _make_result(status="Active", confidence="90")
        pass2 = _make_result(status="Active", confidence="95")
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["status"] == "Active"
        assert result["requires_review"] is False

    def test_agreement_takes_higher_confidence(self) -> None:
        pass1 = _make_result(status="Likely Closed", confidence="82")
        pass2 = _make_result(status="Likely Closed", confidence="88")
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["confidence"] == "88"

    def test_agreement_sums_cost(self) -> None:
        pass1 = _make_result(status="Active", confidence="90", cost=0.008)
        pass2 = _make_result(status="Active", confidence="92", cost=0.007)
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["cost_usd"] == pytest.approx(0.015)


# ── Disagreement: pass 2 contradicts pass 1 ───────────────────────────────────


class TestPass2Disagreement:
    def test_disagreement_keeps_review_flagged(self) -> None:
        pass1 = _make_result(status="Likely Closed", confidence="72")
        pass2 = _make_result(status="Active", confidence="85")
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["requires_review"] is True
        assert "Pass 1: Likely Closed" in result["review_reason"]
        assert "Pass 2: Active" in result["review_reason"]
        assert "verdicts disagree" in result["review_reason"]

    def test_disagreement_keeps_pass1_status_as_primary(self) -> None:
        """Pass 1 stays the primary verdict on disagreement — pass 2 is the
        contradicting evidence, not a replacement."""
        pass1 = _make_result(status="Likely Closed", confidence="72")
        pass2 = _make_result(status="Uncertain", confidence="55")
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["status"] == "Likely Closed"
        assert result["confidence"] == "72"
        assert result["pass2_status"] == "Uncertain"

    def test_disagreement_evidence_shows_both(self) -> None:
        pass1 = _make_result(
            status="Likely Closed", confidence="72",
            evidence="Pass 1 ev: dead domain",
        )
        pass2 = _make_result(
            status="Active", confidence="95",
            evidence="Pass 2 ev: live website",
        )
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert "2-pass disagreement" in result["evidence"]
        assert "Pass 1: Likely Closed" in result["evidence"]
        assert "Pass 2: Active" in result["evidence"]


# ── Pass 2 error handling ─────────────────────────────────────────────────────


class TestPass2Error:
    def test_pass2_error_falls_back_to_pass1(self) -> None:
        """If pass 2 fails, return pass 1 with a note. Don't lose the pass 1 verdict."""
        pass1 = _make_result(status="Likely Closed", confidence="72")
        pass2 = _make_result(error="2nd pass timeout", cost=0.005)
        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]):
            result = check_business_with_verification(
                "fake_key", "Foo", "", "", ""
            )
        assert result["status"] == "Likely Closed"
        assert result["requires_review"] is True
        assert "2nd pass failed" in result["evidence"]
        # Cost should sum — both calls were made
        assert result["cost_usd"] == pytest.approx(0.015)


# ── Cache bypass on pass 2 ────────────────────────────────────────────────────


class TestPass2BypassesCache:
    def test_pass2_called_with_no_cache(self) -> None:
        """Pass 2 must bypass the cache — using a cached result defeats the point."""
        pass1 = _make_result(status="Uncertain", confidence="55")
        pass2 = _make_result(status="Uncertain", confidence="55")
        fake_cache = object()  # sentinel; we just check it's not passed to pass 2

        with patch.object(check_module, "check_business", side_effect=[pass1, pass2]) as mock:
            check_business_with_verification(
                "fake_key", "Foo", "", "", "", cache=fake_cache
            )

        # First call uses the provided cache
        assert mock.call_args_list[0].kwargs.get("cache") is fake_cache
        # Second call must not use the cache
        assert mock.call_args_list[1].kwargs.get("cache") is None
