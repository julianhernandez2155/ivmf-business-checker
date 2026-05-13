"""Tests for the iter-14 Branch A1/A2 gather adapters.

These cover the pure adapter functions that translate v11 outputs into the
shared `BusinessEvidence` schema. The end-to-end orchestrator
(`check_business_branch_a`) is mocked at the dependency boundaries.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent.parent))

from tools.check_business_branch_a import (  # noqa: E402
    _adapt_fb_signal,
    _adapt_scrape,
    _build_citation_hits,
    classify_citation,
)
from tools.check_facebook_recency import FacebookSignal as FbRaw  # noqa: E402
from tools.evidence_schema import CitationType  # noqa: E402


class TestClassifyCitation:
    def test_etsy_shop_is_own_storefront(self):
        assert classify_citation("https://etsy.com/shop/acme") == CitationType.OWN_STOREFRONT

    def test_shopify_subdomain_is_own_storefront(self):
        assert classify_citation("https://acme-co.myshopify.com/products/foo") == CitationType.OWN_STOREFRONT

    def test_mammoth_nation_is_marketplace(self):
        assert classify_citation("https://mammothnation.com/products/acme") == CitationType.MARKETPLACE

    def test_zoominfo_is_aggregator(self):
        assert classify_citation("https://zoominfo.com/c/acme/12345") == CitationType.AGGREGATOR

    def test_facebook_is_social(self):
        assert classify_citation("https://facebook.com/acmebusiness") == CitationType.SOCIAL

    def test_yelp_is_directory(self):
        assert classify_citation("https://yelp.com/biz/acme-syracuse") == CitationType.DIRECTORY

    def test_random_press_is_other(self):
        # Press is hard to classify by URL alone — gather layer can't infer,
        # adjudicator reads the snippet/scrape to decide.
        assert classify_citation("https://syracuse.com/local-business-feature") == CitationType.OTHER

    def test_empty_string_is_other(self):
        assert classify_citation("") == CitationType.OTHER


class TestAdaptFbSignal:
    def test_recent_signal_maps_to_is_recent_true(self):
        raw = FbRaw(
            found=True,
            fb_url="https://facebook.com/acme",
            last_post_date=date.today(),  # today → bucket=recent
            posts_seen=5,
            confidence="high",
            cost_usd=0.001,
        )
        adapted = _adapt_fb_signal(raw)
        assert adapted is not None
        assert adapted.is_recent is True
        assert adapted.page_url == "https://facebook.com/acme"
        assert adapted.posts_count == 5

    def test_not_found_maps_to_is_recent_false(self):
        raw = FbRaw(found=False)
        adapted = _adapt_fb_signal(raw)
        assert adapted is not None
        assert adapted.is_recent is False
        assert adapted.page_url is None

    def test_error_is_carried_into_adapted_error(self):
        raw = FbRaw(found=False, error="rate-limit")
        adapted = _adapt_fb_signal(raw)
        assert adapted.error == "rate-limit"

    def test_none_input_returns_none(self):
        assert _adapt_fb_signal(None) is None


class TestAdaptScrape:
    def test_successful_scrape_is_reachable_with_text(self):
        scraped = {"success": True, "is_slop": False, "text": "Welcome to Acme", "status_code": 200, "note": ""}
        adapted = _adapt_scrape("https://acme.com", scraped)
        assert adapted.reachable is True
        assert adapted.text == "Welcome to Acme"
        assert adapted.status_code == 200

    def test_slop_page_is_not_reachable(self):
        scraped = {"success": True, "is_slop": True, "text": "casino bonuses!", "note": "spam content"}
        adapted = _adapt_scrape("https://acme.com", scraped)
        assert adapted.reachable is False
        assert adapted.error == "spam content"

    def test_failed_scrape_carries_error(self):
        scraped = {"success": False, "is_slop": False, "text": None, "note": "404 not found"}
        adapted = _adapt_scrape("https://acme.com", scraped)
        assert adapted.reachable is False
        assert adapted.error == "404 not found"


class TestBuildCitationHits:
    def test_no_scraping_returns_none_text(self):
        urls = ["https://etsy.com/shop/acme", "https://zoominfo.com/c/acme"]
        hits, cost = _build_citation_hits(urls, enable_scraping=False)
        assert len(hits) == 2
        assert all(h.scraped_text is None for h in hits)
        assert cost == 0.0
        assert hits[0].citation_type == CitationType.OWN_STOREFRONT
        assert hits[1].citation_type == CitationType.AGGREGATOR

    def test_scraping_only_first_n_urls(self):
        urls = [f"https://example{i}.com" for i in range(5)]
        # Patch scrape_website used inside the function (resolved at call time
        # via the imported symbol in `tools.check_business_branch_a`).
        with patch("tools.check_business_branch_a.scrape_website") as mock_scrape:
            mock_scrape.return_value = {
                "success": True, "is_slop": False, "text": "fresh body",
                "scrape_cost": 0.01, "status_code": 200, "note": "",
            }
            hits, cost = _build_citation_hits(urls, enable_scraping=True, scrape_budget=3)

        assert mock_scrape.call_count == 3
        assert hits[0].scraped_text == "fresh body"
        assert hits[2].scraped_text == "fresh body"
        assert hits[3].scraped_text is None
        assert hits[4].scraped_text is None
        assert cost == pytest.approx(0.03)

    def test_scraping_truncates_to_600_chars(self):
        long_text = "x" * 2000
        with patch("tools.check_business_branch_a.scrape_website") as mock_scrape:
            mock_scrape.return_value = {
                "success": True, "is_slop": False, "text": long_text,
                "scrape_cost": 0.01, "status_code": 200, "note": "",
            }
            hits, _ = _build_citation_hits(["https://x.com"], enable_scraping=True)
        assert len(hits[0].scraped_text) == 600
