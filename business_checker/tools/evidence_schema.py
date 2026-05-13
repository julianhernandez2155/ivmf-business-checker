"""Shared evidence schema for iter-14 spike branches (A1/A2/B).

The architectural rule (iter 14): the **gather** layer produces structured
evidence; the **adjudication** layer decides the verdict from that evidence.
Both branches populate the same shape so any decisive-accuracy delta between
branches is attributable to retrieval, not reasoning.

Frozen dataclasses are used for inputs (immutability prevents accidental
mutation between gather and adjudicate calls). Pydantic is used separately
for the adjudicator's LLM output schema (see `tools/adjudicator.py`).

Plan reference: docs/2026-05-13-iter14-search-vs-reasoning-spike.md
§The architectural rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class CitationType(str, Enum):
    """How the adjudicator should treat each citation hit.

    Classification is done by the gather layer (Branch A1/A2 reuses the
    existing helpers in `tools/check_business`; Branch B applies them to
    Exa results). The adjudicator's prompt knows what each type means —
    citations are CLASSIFIED, not filtered. A citation set that is
    all-marketplace is a closure signal the adjudicator can weigh.
    """

    OWN_STOREFRONT = "own_storefront"      # business's own etsy/shopify/etc.
    MARKETPLACE = "marketplace"             # third-party resell/dropship
    AGGREGATOR = "aggregator"               # zoominfo, dnb, etc. — stale records
    DIRECTORY = "directory"                 # yelp, yellowpages, etc.
    SOCIAL = "social"                       # facebook, instagram, linkedin
    PRESS = "press"                         # local news, magazines
    OTHER = "other"                         # uncategorized — adjudicator decides


@dataclass(frozen=True)
class CitationHit:
    """One search-result hit attached to a business.

    `scraped_text` is None for Branch A1 (citations-but-no-scrape) and
    populated for Branch A2 + B (citations + Firecrawl scrape, max 600
    chars). `relevance_score` is Exa-only (Perplexity does not emit one).
    """

    url: str
    title: str | None
    snippet: str | None
    scraped_text: str | None
    citation_type: CitationType
    relevance_score: float | None = None


@dataclass(frozen=True)
class ScrapeResult:
    """Result of scraping the business's own listed website.

    Mirrors the shape `tools/scrape_website.scrape_website()` returns today
    so the adapter from current code into the evidence schema is trivial.
    """

    reachable: bool
    status_code: int | None
    text: str | None
    error: str | None = None


@dataclass(frozen=True)
class FacebookSignal:
    """Result of Apify Facebook recency check.

    Mirrors the shape `tools/check_facebook_recency.check_facebook_recency()`
    emits. `is_recent` is the headline boolean the adjudicator uses; the
    other fields are for explanation in the prompt.
    """

    page_url: str | None
    last_post_date: date | None
    days_since_last_post: int | None
    is_recent: bool
    posts_count: int | None
    error: str | None = None


@dataclass(frozen=True)
class InstagramSignal:
    """Result of Apify Instagram recency check.

    Always `None` in iter-14 branches per Codex finding #3 (no IG bundling).
    Defined here for forward compatibility with iter-15 IG-on experiments.
    """

    profile_url: str | None
    last_post_date: date | None
    days_since_last_post: int | None
    is_recent: bool
    error: str | None = None


@dataclass(frozen=True)
class BusinessMetadata:
    """Optional metadata about the business (owner, dates, category).

    Mirrors `tools/business_metadata.BusinessMetadata` and stays None
    when `config.use_metadata` is False (v11 default).
    """

    owner_name: str | None = None
    category: str | None = None
    description: str | None = None
    date_added: date | None = None
    date_verified: date | None = None


@dataclass(frozen=True)
class BusinessEvidence:
    """Complete structured evidence passed to the adjudicator.

    The adjudicator cannot tell A1, A2, or B apart from the schema alone —
    branches differ only in *which fields are populated* (e.g.,
    `citation_hits[i].scraped_text` is None in A1, populated in A2/B) and
    *which search backend produced the citations*.
    """

    name: str
    website: str | None
    city: str
    state: str
    metadata: BusinessMetadata | None
    own_website_scrape: ScrapeResult
    citation_hits: tuple[CitationHit, ...] = field(default_factory=tuple)
    facebook_signal: FacebookSignal | None = None
    instagram_signal: InstagramSignal | None = None
    # Perplexity's prose verdict, if Branch A1/A2 captured it. Branch B is
    # None (no Perplexity in the gather layer). The adjudicator's prompt
    # treats this as ONE signal among many — it does NOT pass through as
    # the verdict.
    perplexity_prose: str | None = None
