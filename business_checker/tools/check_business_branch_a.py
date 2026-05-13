"""Branch A1 (and A2) gather → Sonnet adjudicator path.

Branch A1 inherits v11's gather pipeline verbatim — same toggles, same
Perplexity call, same FB recency lookup, same website scrape — and replaces
the final-verdict source with the Sonnet adjudicator.

What changes vs. v11:
- The Haiku audit judge is NOT invoked.
- Perplexity's prose verdict is carried into the evidence dict but does not
  pass through as the verdict.
- The deterministic marketplace-residue post-processor stays OFF (v11 had it
  off too); the residue rule lives in the adjudicator's prompt.

What stays the same:
- FB recency ON (`use_facebook_recency=True`).
- IG fallback OFF.
- Metadata OFF.
- Rule scorer ON.
- verify_flagged ON.

Branch A2 adds exactly one retrieval change on top of A1: Firecrawl scrapes
the top 3 Perplexity citations and includes the text in the evidence dict.
That's gated by `enable_citation_scraping=True`.

Plan reference: docs/2026-05-13-iter14-search-vs-reasoning-spike.md
§Phase 2.a1 and §Phase 2.a2.
"""

from __future__ import annotations

import logging
from typing import Iterable

from tools.adjudicator import AdjudicationResult, adjudicate
from tools.check_business import (
    _is_aggregator_url,
    _is_owned_storefront,
    _is_third_party_marketplace,
    check_business,
)
from tools.check_facebook_recency import FacebookSignal as FbSignalRaw
from tools.check_facebook_recency import check_facebook_recency
from tools.evidence_schema import (
    BusinessEvidence,
    BusinessMetadata,
    CitationHit,
    CitationType,
    FacebookSignal,
    ScrapeResult,
)
from tools.scrape_website import scrape_website

logger = logging.getLogger(__name__)


def classify_citation(url: str) -> CitationType:
    """Apply the existing v11 helpers to bucket a citation URL.

    Order matters: own_storefront beats marketplace (a business's own Etsy
    shop should NOT be downgraded to "marketplace" just because etsy.com
    is in the marketplace list).
    """
    if not url:
        return CitationType.OTHER
    if _is_owned_storefront(url):
        return CitationType.OWN_STOREFRONT
    if _is_third_party_marketplace(url):
        return CitationType.MARKETPLACE
    if _is_aggregator_url(url):
        return CitationType.AGGREGATOR
    lower = url.lower()
    if any(s in lower for s in ("facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com")):
        return CitationType.SOCIAL
    if any(s in lower for s in ("yelp.com", "yellowpages.com", "bbb.org", "manta.com", "mapquest.com")):
        return CitationType.DIRECTORY
    return CitationType.OTHER


def _adapt_fb_signal(raw: FbSignalRaw) -> FacebookSignal | None:
    """Convert the v11 FacebookSignal dataclass to the adjudicator's schema."""
    if raw is None:
        return None
    if raw.skipped or raw.error is not None or not raw.found:
        return FacebookSignal(
            page_url=raw.fb_url,
            last_post_date=raw.last_post_date,
            days_since_last_post=None,
            is_recent=False,
            posts_count=raw.posts_seen,
            error=raw.error or raw.skip_reason,
        )
    staleness = raw.staleness_days()
    bucket = raw.staleness_bucket()
    return FacebookSignal(
        page_url=raw.fb_url,
        last_post_date=raw.last_post_date,
        days_since_last_post=staleness,
        is_recent=(bucket == "recent"),
        posts_count=raw.posts_seen,
        error=None,
    )


def _adapt_scrape(website: str, scraped: dict) -> ScrapeResult:
    """Convert `scrape_website()` dict output to the adjudicator's `ScrapeResult`."""
    reachable = bool(scraped.get("success") and not scraped.get("is_slop"))
    text = scraped.get("text") if reachable else None
    status_code = scraped.get("status_code")
    error = scraped.get("note") if not reachable else None
    return ScrapeResult(
        reachable=reachable,
        status_code=status_code if isinstance(status_code, int) else None,
        text=text,
        error=error,
    )


def _build_citation_hits(
    urls: Iterable[str],
    enable_scraping: bool,
    scrape_budget: int = 3,
) -> tuple[tuple[CitationHit, ...], float]:
    """Build CitationHit list from raw URLs, optionally scraping the top N.

    Returns (hits, scrape_cost). When `enable_scraping=False`, every hit has
    `scraped_text=None` — that's Branch A1. When True, the first `scrape_budget`
    hits get their text via Firecrawl — that's Branch A2.
    """
    hits: list[CitationHit] = []
    total_scrape_cost = 0.0
    for i, url in enumerate(urls):
        ctype = classify_citation(url)
        scraped_text: str | None = None
        if enable_scraping and i < scrape_budget:
            try:
                page = scrape_website(url)
                total_scrape_cost += float(page.get("scrape_cost", 0.0) or 0.0)
                if page.get("success") and not page.get("is_slop"):
                    text = (page.get("text") or "").strip()
                    if text:
                        scraped_text = text[:600]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Citation scrape failed for %s: %s", url, exc)
        hits.append(CitationHit(
            url=url,
            title=None,
            snippet=None,
            scraped_text=scraped_text,
            citation_type=ctype,
        ))
    return tuple(hits), total_scrape_cost


def gather_branch_a_evidence(
    perplexity_api_key: str,
    name: str,
    website: str,
    city: str,
    state: str,
    enable_citation_scraping: bool = False,
    metadata: BusinessMetadata | None = None,
    pipeline_fingerprint: str = "",
) -> tuple[BusinessEvidence, dict]:
    """Run the v11 gather pipeline and package the raw signals as `BusinessEvidence`.

    Inherits v11's toggle set verbatim (FB on, IG off, metadata off — even
    if a metadata is passed in, A1 honors v11's `use_metadata=False`; we
    accept the arg for API symmetry but do not pass it through).

    Returns:
        (evidence, costs_dict) — costs_dict has `perplexity_cost`,
        `fb_cost`, `scrape_cost`, `citation_scrape_cost`.
    """
    # Layer 0: scrape the business's own website. This is what v11 does too.
    own_scrape_raw = scrape_website(website) if website else {
        "success": False, "is_slop": False, "text": None, "note": "no website listed",
        "scrape_cost": 0.0, "status_code": None,
    }
    own_scrape = _adapt_scrape(website, own_scrape_raw)
    scrape_cost = float(own_scrape_raw.get("scrape_cost", 0.0) or 0.0)

    # Layer 1: FB recency — structured signal.
    fb_raw = check_facebook_recency(name=name, city=city, state=state, website=website)
    fb_signal = _adapt_fb_signal(fb_raw)
    fb_cost = float(getattr(fb_raw, "cost_usd", 0.0) or 0.0)

    # Layer 2: Perplexity prose + citations. We run the existing check_business
    # with v11 toggles to get its citations and prose verdict. Note: this
    # re-runs the scrape + FB internally (it's how check_business is wired).
    # Acceptable double-pay for the A1 spike — keeps the gather code path
    # identical to v11 byte-for-byte. Optimization comes in iter 15.
    pplx_result = check_business(
        api_key=perplexity_api_key,
        name=name,
        website=website,
        city=city,
        state=state,
        cache=None,
        use_rule_scorer=True,
        use_facebook_recency=True,
        use_instagram_fallback=False,
        use_marketplace_residue=False,  # A1 inherits v11 toggle verbatim
        metadata=None,                  # A1 inherits v11: metadata off
        pipeline_fingerprint=pipeline_fingerprint,
    )
    perplexity_prose = pplx_result.get("evidence") or None
    citation_urls = pplx_result.get("citations") or []
    perplexity_cost = float(pplx_result.get("cost_usd", 0.0) or 0.0)

    citation_hits, citation_scrape_cost = _build_citation_hits(
        citation_urls,
        enable_scraping=enable_citation_scraping,
    )

    evidence = BusinessEvidence(
        name=name,
        website=website or None,
        city=city,
        state=state,
        metadata=None,  # A1 honors v11 use_metadata=False
        own_website_scrape=own_scrape,
        citation_hits=citation_hits,
        facebook_signal=fb_signal,
        instagram_signal=None,
        perplexity_prose=perplexity_prose,
    )
    costs = {
        "perplexity_cost": perplexity_cost,
        "fb_cost": fb_cost,
        "scrape_cost": scrape_cost,
        "citation_scrape_cost": citation_scrape_cost,
    }
    return evidence, costs


def check_business_branch_a(
    perplexity_api_key: str,
    anthropic_api_key: str,
    name: str,
    website: str,
    city: str,
    state: str,
    enable_citation_scraping: bool = False,
    metadata: BusinessMetadata | None = None,
    pipeline_fingerprint: str = "",
) -> dict:
    """End-to-end Branch A1 (or A2 with `enable_citation_scraping=True`) row.

    Returns the same shape `check_business()` returns today so the eval
    rerunner does not need to special-case Branch A output.
    """
    evidence, costs = gather_branch_a_evidence(
        perplexity_api_key=perplexity_api_key,
        name=name,
        website=website,
        city=city,
        state=state,
        enable_citation_scraping=enable_citation_scraping,
        metadata=metadata,
        pipeline_fingerprint=pipeline_fingerprint,
    )
    verdict: AdjudicationResult = adjudicate(
        evidence=evidence,
        api_key=anthropic_api_key,
    )
    total_cost = sum(costs.values())
    return {
        "status": verdict.status,
        "confidence": str(verdict.confidence),
        "evidence": verdict.evidence,
        "citations": [hit.url for hit in evidence.citation_hits],
        "cost_usd": total_cost,
        "error": None,
        "requires_review": verdict.requires_review,
        "review_reason": verdict.review_reason,
    }
