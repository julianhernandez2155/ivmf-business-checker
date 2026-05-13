"""Golden tests for the iter-14 Sonnet adjudicator.

The plan calls for ~10 golden-evidence inputs → expected verdicts across
the four statuses plus residue-only, dead-site + active-FB, and NWP edge
cases. These tests are mocked at the Anthropic SDK boundary — they do NOT
make live API calls. The role of the golden tests is to:

1. Lock the prompt + parser contract (schema parse, error fallback).
2. Verify the adjudicator emits the expected verdict for unambiguous inputs.
3. Catch over-skepticism (the iter-12 Haiku failure mode: returning Uncertain
   on rows with a clear Active or Likely Closed signal).

Live-API integration tests live in a separate `tests/integration/` tree
and are gated behind an explicit `RUN_LIVE_ADJUDICATOR=1` env var so they
don't burn budget during routine pytest runs.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch
import sys

import pytest

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent.parent))

from tools.adjudicator import (  # noqa: E402
    MODEL_ID,
    AdjudicationResult,
    adjudicate,
    parse_response,
    serialize_evidence,
)
from tools.evidence_schema import (  # noqa: E402
    BusinessEvidence,
    BusinessMetadata,
    CitationHit,
    CitationType,
    FacebookSignal,
    ScrapeResult,
)


# ── Test fixtures: builders for canonical evidence shapes ────────────────────


def _evidence(
    *,
    name: str = "Acme Veteran Co",
    website: str | None = "https://acmeveteranco.com",
    site_reachable: bool = True,
    site_text: str | None = "Welcome to Acme. We sell veteran-owned hot sauce.",
    citations: tuple[CitationHit, ...] = (),
    fb: FacebookSignal | None = None,
    perplexity_prose: str | None = None,
    metadata: BusinessMetadata | None = None,
) -> BusinessEvidence:
    return BusinessEvidence(
        name=name,
        website=website,
        city="Syracuse",
        state="NY",
        metadata=metadata,
        own_website_scrape=ScrapeResult(
            reachable=site_reachable,
            status_code=200 if site_reachable else None,
            text=site_text,
            error=None if site_reachable else "DNS failure",
        ),
        citation_hits=citations,
        facebook_signal=fb,
    )


def _citation(url: str, ctype: CitationType, snippet: str = "") -> CitationHit:
    return CitationHit(
        url=url,
        title=None,
        snippet=snippet,
        scraped_text=None,
        citation_type=ctype,
    )


# ── parse_response unit tests (no SDK calls) ─────────────────────────────────


class TestParseResponse:
    def test_clean_json_active(self):
        result = parse_response(json.dumps({
            "status": "Active",
            "confidence": 95,
            "evidence": "Website live; FB posted yesterday.",
            "requires_review": False,
            "review_reason": None,
        }))
        assert result.status == "Active"
        assert result.confidence == 95
        assert result.requires_review is False

    def test_code_fenced_json_is_unwrapped(self):
        fenced = (
            "```json\n"
            + json.dumps({
                "status": "Likely Closed",
                "confidence": 85,
                "evidence": "All citations marketplace residue.",
                "requires_review": False,
            })
            + "\n```"
        )
        result = parse_response(fenced)
        assert result.status == "Likely Closed"
        assert result.confidence == 85

    def test_invalid_json_falls_back_to_uncertain(self):
        result = parse_response("not even json")
        assert result.status == "Uncertain"
        assert result.confidence == 0
        assert result.requires_review is True
        assert result.review_reason == "schema_failure"

    def test_invalid_status_falls_back_to_uncertain(self):
        result = parse_response(json.dumps({
            "status": "Maybe Active",
            "confidence": 50,
            "evidence": "ambiguous",
            "requires_review": False,
        }))
        assert result.status == "Uncertain"
        assert result.review_reason == "invalid_status"

    def test_out_of_range_confidence_fails_schema(self):
        result = parse_response(json.dumps({
            "status": "Active",
            "confidence": 150,
            "evidence": "x",
            "requires_review": False,
        }))
        assert result.status == "Uncertain"
        assert result.review_reason == "schema_failure"


# ── serialize_evidence: dataclass → JSON string ──────────────────────────────


class TestSerializeEvidence:
    def test_omits_no_field_and_handles_enum(self):
        ev = _evidence(
            citations=(
                _citation("https://etsy.com/shop/acme", CitationType.OWN_STOREFRONT),
            ),
            fb=FacebookSignal(
                page_url="https://facebook.com/acme",
                last_post_date=date(2026, 5, 11),
                days_since_last_post=2,
                is_recent=True,
                posts_count=10,
            ),
        )
        payload = serialize_evidence(ev)
        data = json.loads(payload)
        assert data["name"] == "Acme Veteran Co"
        # Enum serialized as its string value.
        assert data["citation_hits"][0]["citation_type"] == "own_storefront"
        # Date serialized to ISO string.
        assert data["facebook_signal"]["last_post_date"] == "2026-05-11"


# ── Adjudicate end-to-end with mocked SDK ────────────────────────────────────


def _mock_anthropic_with_response(response_text: str):
    """Return a patcher that injects a fake Anthropic client returning `response_text`."""
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = response_text
    fake_response = MagicMock()
    fake_response.content = [fake_block]

    fake_messages = MagicMock()
    fake_messages.create.return_value = fake_response

    fake_client = MagicMock()
    fake_client.messages = fake_messages

    fake_anthropic_module = MagicMock()
    fake_anthropic_module.Anthropic.return_value = fake_client

    return fake_anthropic_module


def _patch_adjudicator_sdk(response_text: str) -> Iterator[MagicMock]:
    """Context manager-style fixture replacing the lazily-imported anthropic module."""
    fake_module = _mock_anthropic_with_response(response_text)
    return patch.dict("sys.modules", {"anthropic": fake_module})


class TestAdjudicateGoldens:
    """One row per row of the plan's "10 fixtures across the four statuses + edge cases" requirement."""

    def _mocked_call(self, ev: BusinessEvidence, response_payload: dict) -> AdjudicationResult:
        with _patch_adjudicator_sdk(json.dumps(response_payload)):
            return adjudicate(ev, api_key="test-key")

    def test_live_website_with_products_is_active(self):
        ev = _evidence(
            site_text="We sell custom hot sauce. Buy 12oz bottles online. Cart available.",
            citations=(_citation("https://example.com/news", CitationType.PRESS,
                                  snippet="2025 feature on local veteran-owned business"),),
            fb=FacebookSignal(
                page_url="https://facebook.com/acme",
                last_post_date=date(2026, 5, 10),
                days_since_last_post=3,
                is_recent=True,
                posts_count=20,
            ),
        )
        result = self._mocked_call(ev, {
            "status": "Active", "confidence": 96,
            "evidence": "Live website with products; FB recent 3 days ago.",
            "requires_review": False, "review_reason": None,
        })
        assert result.status == "Active"
        assert result.confidence >= 90

    def test_dead_site_plus_recent_fb_is_active(self):
        # iter-11 win case: website dead but FB shows recent activity → Active.
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(),
            fb=FacebookSignal(
                page_url="https://facebook.com/acme",
                last_post_date=date(2026, 5, 12),
                days_since_last_post=1,
                is_recent=True,
                posts_count=15,
            ),
        )
        result = self._mocked_call(ev, {
            "status": "Active", "confidence": 88,
            "evidence": "Website down but FB posted yesterday — operating via social.",
            "requires_review": False,
        })
        assert result.status == "Active"

    def test_all_residue_citations_is_likely_closed(self):
        # The residue rule the plan moved into prompt-encoded guidance:
        # dead site + all-marketplace-or-aggregator + no recent FB = closure.
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(
                _citation("https://mammoth-nation.com/products/acme", CitationType.MARKETPLACE),
                _citation("https://amazon.com/s?k=acme", CitationType.MARKETPLACE),
                _citation("https://zoominfo.com/c/acme/12345", CitationType.AGGREGATOR),
            ),
            fb=None,
        )
        result = self._mocked_call(ev, {
            "status": "Likely Closed", "confidence": 88,
            "evidence": "Dead website; 3 citations all marketplace/aggregator residue; no FB.",
            "requires_review": False,
        })
        assert result.status == "Likely Closed"

    def test_explicit_google_maps_closure_is_likely_closed(self):
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(
                _citation(
                    "https://google.com/maps?q=acme",
                    CitationType.DIRECTORY,
                    snippet="Permanently closed — last reviewed 2024",
                ),
            ),
            fb=None,
        )
        result = self._mocked_call(ev, {
            "status": "Likely Closed", "confidence": 95,
            "evidence": "Google Maps shows 'Permanently closed.'",
            "requires_review": False,
        })
        assert result.status == "Likely Closed"

    def test_only_old_directory_listing_is_uncertain(self):
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(
                _citation(
                    "https://yellowpages.com/syracuse-ny/acme",
                    CitationType.DIRECTORY,
                    snippet="Listed 2018, no recent reviews",
                ),
            ),
            fb=None,
        )
        result = self._mocked_call(ev, {
            "status": "Uncertain", "confidence": 40,
            "evidence": "Old directory listing only; no recent activity.",
            "requires_review": True,
            "review_reason": "low_confidence",
        })
        assert result.status == "Uncertain"
        assert result.requires_review is True

    def test_no_evidence_anywhere_is_nwp(self):
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(),
            fb=None,
        )
        result = self._mocked_call(ev, {
            "status": "No Web Presence", "confidence": 60,
            "evidence": "Nothing found in any channel.",
            "requires_review": True,
            "review_reason": "nwp_last_resort",
        })
        assert result.status == "No Web Presence"
        assert result.requires_review is True

    def test_disagreement_between_perplexity_prose_and_signals_flagged(self):
        # Perplexity prose says "closed" but Facebook is recent → adjudicator
        # should call Active (per prompt: structured evidence wins) and flag review.
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(),
            fb=FacebookSignal(
                page_url="https://facebook.com/acme",
                last_post_date=date(2026, 5, 11),
                days_since_last_post=2,
                is_recent=True,
                posts_count=8,
            ),
            perplexity_prose="The business appears to have closed in 2023.",
        )
        result = self._mocked_call(ev, {
            "status": "Active", "confidence": 75,
            "evidence": "FB posted 2 days ago; Perplexity prose disagrees.",
            "requires_review": True,
            "review_reason": "signals_disagree",
        })
        assert result.status == "Active"
        assert result.requires_review is True

    def test_own_storefront_only_flagged_for_review(self):
        # Plan rule: if the only Active signal is an own_storefront citation,
        # could be inventory liquidation → flag for human.
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(
                _citation("https://etsy.com/shop/acme", CitationType.OWN_STOREFRONT,
                          snippet="Active shop, 5 products"),
            ),
            fb=None,
        )
        result = self._mocked_call(ev, {
            "status": "Active", "confidence": 65,
            "evidence": "Etsy shop active with 5 products; no other recent signals.",
            "requires_review": True,
            "review_reason": "only_own_storefront",
        })
        assert result.status == "Active"
        assert result.requires_review is True

    def test_squatted_domain_with_no_other_signal_is_likely_closed(self):
        ev = _evidence(
            site_reachable=True,
            site_text="Buy CBD gummies and online casino bonuses!",
            citations=(),
            fb=None,
        )
        result = self._mocked_call(ev, {
            "status": "Likely Closed", "confidence": 75,
            "evidence": "Domain squatted (unrelated CBD/gambling content); no other channels.",
            "requires_review": False,
        })
        assert result.status == "Likely Closed"

    def test_press_citation_2024_plus_is_active_even_without_site(self):
        ev = _evidence(
            site_reachable=False, site_text=None,
            citations=(
                _citation(
                    "https://syracuse.com/local-vet-owned-acme-expands",
                    CitationType.PRESS,
                    snippet="2025-09-04: Acme Veteran Co. expanded into wholesale.",
                ),
            ),
            fb=None,
        )
        result = self._mocked_call(ev, {
            "status": "Active", "confidence": 85,
            "evidence": "2025 press coverage about expansion; website down is incidental.",
            "requires_review": False,
        })
        assert result.status == "Active"


# ── Sanity: MODEL_ID pinned and prompt loads ─────────────────────────────────


class TestModuleContract:
    def test_model_id_is_pinned_sonnet_4x(self):
        # Phase 1 step 1: pinned via resolve_model.py on 2026-05-13.
        assert MODEL_ID.startswith("claude-sonnet-4-")

    def test_system_prompt_loads(self):
        from tools.adjudicator import _load_system_prompt
        body = _load_system_prompt()
        assert "adjudicator" in body.lower()
        assert "Active" in body and "Likely Closed" in body
