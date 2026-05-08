"""Tests for aggregator detection and triage logic in tools.check_business.

These cover the deterministic post-processing rules added 2026-05-08 to
address Pattern B hesitancy without prompt changes:
  - Aggregator-only citation detection (drives Uncertain → Likely Closed override)
  - Triage flag (requires_review + review_reason)
"""

from __future__ import annotations

import pytest

from tools.check_business import (
    _all_citations_are_aggregators,
    _citation_host_path,
    _compute_triage,
    _is_aggregator_url,
)


# ── _is_aggregator_url ────────────────────────────────────────────────────────


class TestIsAggregatorUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.zoominfo.com/c/foo/123",
            "https://manta.com/c/abc",
            "https://www.rocketreach.co/people/x",
            "https://experience.com/business/y",
            "https://safer.fmcsa.dot.gov/query?x=1",
            "https://otrucking.com/carrier/x",
            "https://www.indeed.com/cmp/some-company",
            "https://thcanearby.com/shop/x",
            "https://fedlinks.com/listing/x",
            "https://www.dnb.com/business-directory/x",
            "https://www.bizapedia.com/al/some-llc.html",
        ],
    )
    def test_known_aggregators_match(self, url: str) -> None:
        assert _is_aggregator_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.facebook.com/foobar",
            "https://www.instagram.com/foo/",
            "https://maps.google.com/?cid=123",
            "https://www.google.com/maps/place/x",
            "https://www.linkedin.com/in/owner",
            "https://www.linkedin.com/company/foo",
            "https://www.nytimes.com/2024/article",
            "https://shop.example.com/products/x",
            "https://www.etsy.com/shop/realstore",
            "https://www.amazon.com/stores/foo",
            "https://www.yelp.com/biz/some-real-business",  # Yelp deliberately excluded
        ],
    )
    def test_real_signals_do_not_match(self, url: str) -> None:
        assert _is_aggregator_url(url) is False

    def test_empty_string(self) -> None:
        assert _is_aggregator_url("") is False

    def test_malformed_url(self) -> None:
        # Should not raise; treat as non-aggregator.
        assert _is_aggregator_url("not a url") is False


# ── _citation_host_path ───────────────────────────────────────────────────────


class TestCitationHostPath:
    def test_strips_www(self) -> None:
        assert _citation_host_path("https://www.example.com/path").startswith(
            "example.com"
        )

    def test_lowercases(self) -> None:
        assert _citation_host_path("https://EXAMPLE.com/Foo").startswith(
            "example.com"
        )

    def test_handles_empty(self) -> None:
        assert _citation_host_path("") == ""


# ── _all_citations_are_aggregators ────────────────────────────────────────────


class TestAllCitationsAreAggregators:
    def test_empty_list_returns_false(self) -> None:
        # No citations means we can't conclude aggregator-only — must not fire.
        assert _all_citations_are_aggregators([]) is False

    def test_all_aggregators_returns_true(self) -> None:
        cites = [
            "https://www.zoominfo.com/c/x",
            "https://safer.fmcsa.dot.gov/query?x=1",
            "https://www.indeed.com/cmp/foo",
        ]
        assert _all_citations_are_aggregators(cites) is True

    def test_one_facebook_blocks_override(self) -> None:
        cites = [
            "https://www.zoominfo.com/c/x",
            "https://www.facebook.com/business",
        ]
        assert _all_citations_are_aggregators(cites) is False

    def test_one_press_blocks_override(self) -> None:
        cites = [
            "https://www.manta.com/c/x",
            "https://sustainablebrands.com/read/article",
        ]
        assert _all_citations_are_aggregators(cites) is False

    def test_one_maps_blocks_override(self) -> None:
        cites = [
            "https://www.zoominfo.com/c/x",
            "https://maps.google.com/?cid=123",
        ]
        assert _all_citations_are_aggregators(cites) is False

    def test_self_citation_filtered_out(self) -> None:
        # Business's own dead domain shouldn't count as a non-aggregator citation.
        cites = [
            "https://example.com/contact",  # self
            "https://www.zoominfo.com/c/x",  # aggregator
        ]
        assert (
            _all_citations_are_aggregators(cites, own_website="https://example.com")
            is True
        )

    def test_only_self_citation_returns_false(self) -> None:
        # If filtering self leaves no external citations, override must not fire.
        cites = ["https://example.com/contact"]
        assert (
            _all_citations_are_aggregators(cites, own_website="https://example.com")
            is False
        )

    def test_self_filter_handles_www_prefix(self) -> None:
        cites = [
            "https://www.example.com/contact",
            "https://www.zoominfo.com/c/x",
        ]
        assert (
            _all_citations_are_aggregators(cites, own_website="https://example.com")
            is True
        )


# ── _compute_triage ───────────────────────────────────────────────────────────


class TestComputeTriage:
    def test_active_high_confidence_auto_trusted(self) -> None:
        review, reason = _compute_triage("Active", 95)
        assert review is False
        assert reason is None

    def test_active_at_floor_auto_trusted(self) -> None:
        review, reason = _compute_triage("Active", 80)
        assert review is False

    def test_active_below_floor_flagged(self) -> None:
        review, reason = _compute_triage("Active", 65)
        assert review is True
        assert "below auto-trust floor" in reason

    def test_uncertain_always_flagged(self) -> None:
        review, reason = _compute_triage("Uncertain", 95)
        assert review is True
        assert "low historical precision" in reason

    def test_no_web_presence_always_flagged(self) -> None:
        review, reason = _compute_triage("No Web Presence", 90)
        assert review is True
        assert "low historical precision" in reason

    def test_likely_closed_high_confidence_auto_trusted(self) -> None:
        review, reason = _compute_triage("Likely Closed", 90)
        assert review is False

    def test_likely_closed_below_closure_floor_flagged(self) -> None:
        review, reason = _compute_triage("Likely Closed", 75)
        assert review is True
        assert "confirm before outreach" in reason

    def test_likely_closed_at_70_flagged_not_below_floor(self) -> None:
        # At 70, low-confidence floor doesn't fire but closure-autotrust does.
        review, reason = _compute_triage("Likely Closed", 70)
        assert review is True
        assert "confirm before outreach" in reason

    def test_likely_closed_below_low_floor_flagged_with_floor_reason(self) -> None:
        # Below 70, low-confidence floor triggers first — that's the more
        # urgent message to surface.
        review, reason = _compute_triage("Likely Closed", 65)
        assert review is True
        assert "below auto-trust floor" in reason
