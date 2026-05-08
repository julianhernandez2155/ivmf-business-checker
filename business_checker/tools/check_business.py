"""
Business operational status checker — core API tool.

Calls the Perplexity Sonar API to research a single business and return
a structured verdict: Active, Likely Closed, Uncertain, or No Web Presence.

Can be run standalone for testing (must use -m form so the tools package
imports correctly):
    python -m tools.check_business
"""

import json
import os
import time
from typing import Literal
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, ValidationError

from tools.scrape_website import normalize_url, scrape_website


# ── Perplexity API config ─────────────────────────────────────────────────────

API_URL = "https://api.perplexity.ai/chat/completions"
MODEL   = "sonar"
MAX_RETRIES = 4

# Pricing loaded from .env — update PERPLEXITY_COST_* there if rates change
_COST_PER_REQUEST   = float(os.getenv("PERPLEXITY_COST_PER_REQUEST",   "0.005"))
_COST_PER_1M_TOKENS = float(os.getenv("PERPLEXITY_COST_PER_1M_TOKENS", "1.00"))


def _calculate_cost(usage: dict) -> float:
    """Compute cost for one API call from the usage block Perplexity returns."""
    tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    return _COST_PER_REQUEST + (tokens * _COST_PER_1M_TOKENS / 1_000_000)


# ── Aggregator detection (Pattern B post-processing) ──────────────────────────
#
# Data aggregators auto-scrape business records and persist them indefinitely
# after a business closes. When the AI's only citations are aggregator URLs and
# the business's domain is dead, hedging to "Uncertain" is wrong — it should
# commit to "Likely Closed". This list is matched on hostname + path-prefix.

AGGREGATOR_DOMAINS: tuple[str, ...] = (
    # B2B contact / firmographic aggregators
    "zoominfo.com", "manta.com", "rocketreach.co", "experience.com",
    "infogroup.com", "openfos.com", "ailoq.com", "salary.com",
    "dnb.com", "bizapedia.com", "buzzfile.com", "corporationwiki.com",
    "opencorporates.com", "yellowpages.com",
    # Trucking / DOT carriers
    "fmcsa.dot.gov", "safer.fmcsa.dot.gov", "otrucking.com",
    "greatguysmove.com",
    # Vertical / niche directories surfacing in Pattern B disagreements
    "thcanearby.com", "cannabisshop", "swfinstitute.org",
    "fedlinks.com", "eventeny.com", "alignusapp.com",
    # Hiring boards (record-of-existence only)
    "indeed.com/cmp", "glassdoor.com/Overview",
    # Generic state / archive crawlers
    "bizstanding.com", "chamberofcommerce.com",
)

# Override only fires when AI hedged below this confidence — never overrides a
# confident Uncertain (which is rare but should be respected).
AGGREGATOR_OVERRIDE_MAX_CONFIDENCE = 70


def _citation_host_path(url: str) -> str:
    """Return lowercased 'host/path' for substring matching against aggregators."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return f"{host}{parsed.path}".lower()
    except Exception:
        return url.lower()


def _is_aggregator_url(url: str) -> bool:
    """True if the URL matches a known data-aggregator host or path prefix."""
    target = _citation_host_path(url)
    if not target:
        return False
    return any(marker in target for marker in AGGREGATOR_DOMAINS)


def _all_citations_are_aggregators(
    citations: list[str], own_website: str = ""
) -> bool:
    """True iff every non-self citation matches an aggregator and at least
    one such citation exists.

    Self-citations (the business's own dead domain) are filtered out before
    evaluation — a citation list of just the dead website is not evidence
    of aggregator-only presence.
    """
    own_host = ""
    if own_website:
        try:
            own_host = (urlparse(own_website).hostname or "").lower()
            if own_host.startswith("www."):
                own_host = own_host[4:]
        except Exception:
            own_host = ""

    external = []
    for url in citations:
        host = _citation_host_path(url).split("/", 1)[0]
        if own_host and host == own_host:
            continue  # skip self-citations
        external.append(url)

    if not external:
        return False
    return all(_is_aggregator_url(u) for u in external)


# ── Triage flag (production calibration thresholds) ───────────────────────────
#
# Thresholds derived from bmosg_v1 baseline calibration (n=58 scoreable):
#   90–100% confidence band: 90% agreement (auto-trust)
#   80–89% band:              67% agreement (auto-trust if status == Active)
#   70–79% band:              84% agreement (mixed; review minority classes)
#   60–69% band:               0% agreement (always review)
#   50–59% band:              36% agreement (always review)
# Plus: "Uncertain" precision was 35%, "No Web Presence" was 0% — always review.

TRIAGE_LOW_CONFIDENCE_FLOOR    = 70
TRIAGE_CLOSURE_AUTOTRUST_FLOOR = 80
TRIAGE_ALWAYS_REVIEW_STATUSES  = frozenset({"Uncertain", "No Web Presence"})


def _compute_triage(status: str, confidence: int) -> tuple[bool, str | None]:
    """Decide whether a verdict should be flagged for human review.

    Returns (requires_review, review_reason).
    """
    if status in TRIAGE_ALWAYS_REVIEW_STATUSES:
        return True, f"Status '{status}' has low historical precision; verify manually."
    if confidence < TRIAGE_LOW_CONFIDENCE_FLOOR:
        return True, (
            f"Confidence {confidence}% below auto-trust floor "
            f"({TRIAGE_LOW_CONFIDENCE_FLOOR}%)."
        )
    if status == "Likely Closed" and confidence < TRIAGE_CLOSURE_AUTOTRUST_FLOOR:
        return True, (
            f"'Likely Closed' below {TRIAGE_CLOSURE_AUTOTRUST_FLOOR}% — "
            f"confirm before outreach."
        )
    return False, None


# ── Structured output schema ──────────────────────────────────────────────────

class BusinessStatus(BaseModel):
    status:     Literal["Active", "Likely Closed", "Uncertain", "No Web Presence"]
    confidence: int    # 0–100
    evidence:   str    # one sentence citing source and date if available


# ── System prompt (static — same for every business, eligible for caching) ────

SYSTEM_PROMPT = """You are a research analyst verifying whether a specific business is still actively operating. Think like a thorough investigator — not just someone running a quick search.

---

FAST PATH — use this if the website content provided shows a real, currently operating business. Ask yourself: does this look like a live business, or does it look abandoned?

  Qualifies as Active (any of these):
       • Real products or services described with specific details (flavors, pricing, sizing, service descriptions) — does NOT require a shopping cart or online checkout
       • A restaurant, caterer, or food vendor with a current menu and contact info
       • A service business with a contact form, phone number, or booking link and real service descriptions
       • A portfolio, gallery, or event schedule showing recent work or upcoming dates
       • Blog or news posts from 2023 or later
       • Copyright year 2023–2026 in the footer alongside substantive content
       • An informational site for a business that clearly sells in person, at markets, or through distributors — not every business sells online, and that is fine

  Does NOT qualify — proceed to Full Investigation:
       • Website loads but all content and dates are from 2021 or earlier
       • "Coming soon," "under construction," or "we're rebuilding the site" message
       • Only a contact page or generic About page with no real products or services described
       • Placeholder or template text (no real business-specific content)
       • The site is vague enough that you cannot tell what this business actually sells or does

If the website qualifies → return Active immediately. Do NOT search further. Do NOT override this with state LLC registry status, Secretary of State filings, or other administrative records — a business can operate under a different entity or as a sole proprietorship even if the original LLC is administratively inactive. The live website with real content is the definitive signal.

---

FULL INVESTIGATION — required if the website was dead, missing, a parking page, a 404, or a DNS failure.

A dead website does NOT mean a closed business. Many small businesses let their website lapse while remaining fully operational through social media, Google Maps, farmer's markets, or word of mouth. You must work through ALL of the following channels before drawing any conclusion. Do not stop early.

CHANNEL 1 — GOOGLE SEARCH
Run all of these queries:
  • "[BUSINESS NAME]" [LOCATION]
  • "[BUSINESS NAME]" [relevant industry term — e.g., "catering", "sauce", "jerky", "consulting"]
Look for: Google Business Profile (open or closed?), Yelp listing, BBB entry, press coverage, or any directory entry specifically about this business. Note the most recent date you find.

CHANNEL 2 — GOOGLE MAPS
Search Google Maps for "[BUSINESS NAME]" near [LOCATION].
  • "Permanently closed" on Google Maps = strong closure signal.
  • Open listing with reviews from 2023–2026 = strong Active signal.
  • No listing at all = neutral. Normal for online-only, home-based, or mobile businesses. Do not treat absence as closure.

CHANNEL 3 — FACEBOOK
Search Facebook for a business page named "[BUSINESS NAME]".
  • Posts or customer interactions from 2023–2026 = Active.
  • Page exists but last post is 2021 or earlier = Uncertain signal.
  • No page found = note it and continue.

CHANNEL 4 — INSTAGRAM
Search Instagram for "[BUSINESS NAME]".
  • Recent posts or stories (2023–2026) = Active signal.
  • Account exists but inactive since 2021 or earlier = Uncertain.
  • Not found = note it and continue.

CHANNEL 5 — LINKEDIN
Search LinkedIn for the company "[BUSINESS NAME]" and for its owner/founder.
  • Active company page or owner currently listing this as their business = positive signal.
  • Owner's LinkedIn shows they moved on to a different business = possible closure signal.

CHANNEL 6 — OWNER / OPERATOR SEARCH
If you find or know the owner's name from any search above:
  • Search: [owner name] + "[BUSINESS NAME]"
  • Look for recent interviews, podcast features, news articles, or social posts where they reference the business.
  • An owner actively promoting the business in 2023–2026 = strong Active signal.

CHANNEL 7 — MARKETPLACES (for product-based businesses)
Search Amazon, Etsy, specialty food retailers, or other relevant platforms for "[BUSINESS NAME]" products.
  • Products listed and in stock = Active signal.
  • Products listed as unavailable or removed = weak closure signal.

CHANNEL 8 — INDUSTRY DIRECTORIES & MARKETPLACES
Search BBB (bbb.org), Yelp, industry-specific directories, or trade association member lists for "[BUSINESS NAME]".
  • Active listing with recent activity = supportive Active signal.

---

STATUS DEFINITIONS:
- Active: Clear evidence of current operation found on any channel. Examples: website with real content, open Google Maps with recent reviews, active Facebook or Instagram, products available for purchase, owner actively promoting the business.
- Likely Closed: Multiple independent closure signals after a thorough search — e.g., dead website PLUS Google Maps "permanently closed" PLUS no social media activity PLUS no other presence found. OR one unambiguous signal (the business's own page announces closure, Google Maps explicitly says "permanently closed").
- Uncertain: You found this business on at least one channel but cannot confirm it is currently operating — last activity was 2020–2022, signals are mixed, or the owner's status is unclear.
- No Web Presence: After completing ALL channels above, you found absolutely nothing specific to this business anywhere. This is a last resort — only use it after a genuinely thorough search.

CRITICAL RULES:
- A dead website alone is NOT sufficient to call a business closed. You must check all channels.
- Do NOT stop investigating after a negative signal. Each negative finding should push you to search harder.
- Only use evidence that is specifically about THIS business. Ignore articles or results that merely mention the name in passing.
- Results from before 2022 are not reliable evidence of current operating status.
- "Likely Closed" requires multiple signals, not just one. "No Web Presence" requires every channel to come up empty.

SQUATTED / HIJACKED DOMAINS:
- If a domain now hosts gambling, adult content, spam, generic blog content, or a parking page clearly unrelated to the original business — treat it as a dead domain. It counts as one closure signal.
- Squatted domain + no social media activity + no Google Maps listing + no other channel hits = "Likely Closed". Do NOT call this "Uncertain" just because you cannot find an explicit closure announcement.

STALE RECORDS WITH NO CORROBORATION:
- If the only evidence you can find is a state incorporation record or a basic directory listing (Manta, OpenFOS, Infogroup, etc.) with no activity after 2021, and no social media, no maps, no press, no owner activity — that is NOT enough to call a business "Uncertain". Call it "Likely Closed" (multiple stale signals with nothing recent = closure pattern).
- Old incorporation records alone are not evidence of current operation.

EMPTY WEBSITE BUILDERS (Square, Weebly, Wix placeholders):
- A generic landing page on Square, Weebly, or Wix with no business-specific content (no products, no services, no contact info specific to this business) is NOT a real web presence. Treat it the same as a dead domain.

NO WEB PRESENCE — use it precisely:
- Only use "No Web Presence" if you found NOTHING specific to this business across all 8 channels — not even an old directory listing, not even an owner social profile.
- If you found any result that specifically names this business (even an old one), use "Uncertain" or "Likely Closed" instead.
- A personal Whitepages or RocketReach profile for an individual is NOT a business web presence.

---

CONFIDENCE SCORE RUBRIC (use this — do not assign arbitrary numbers):

  Active 95–100: Multiple channels confirm current operation with recent dates (2024–2026).
  Active 80–94:  One channel clearly confirms active operation, recency somewhat unclear.
  Active 60–79:  Single weak or indirect Active signal (old directory listing with one recent review).

  Likely Closed 90–100: Multiple independent channels all point to closure after thorough search.
  Likely Closed 70–89:  Strong closure evidence on 2+ channels, not all channels fully checked.

  Uncertain 60–80: Found the business on at least one real channel but last confirmed activity was 2020–2022, or signals conflict across channels.
  Uncertain 40–59: Very thin evidence — found only a name match in an old directory with no corroboration. If you are here and found nothing after 2020, consider Likely Closed instead.

  No Web Presence 75–90: All 8 channels thoroughly searched and returned nothing.
  No Web Presence 50–74: Search was limited due to a very generic name or ambiguous location.

If you would score your chosen status below 50%, reconsider — a different status likely fits better.

Respond with the status, confidence score, and a one-sentence evidence summary naming the specific source and its recency (e.g., "website dead, Google Maps permanently closed January 2025, Facebook inactive since 2020" or "website loads with active e-commerce, products in cart as of 2026")."""


# ── Main function ─────────────────────────────────────────────────────────────

def check_business(
    api_key: str,
    name: str,
    website: str,
    city: str,
    state: str,
    max_retries: int = MAX_RETRIES,
    cache=None,
) -> dict:
    """
    Research a business and return its operational status.

    Returns a dict with keys:
        status     — "Active" | "Likely Closed" | "Uncertain" | "No Web Presence"
        confidence — integer 0–100
        evidence   — one-sentence summary citing source(s)
        citations  — list of URLs Perplexity found (may be empty)
        cost_usd   — 0.0 for cache hits, API cost otherwise
        error      — set to an error message if the call failed, else None
        _cached    — True if result came from cache (key present only on hits)

    Args:
        cache: Optional ResultCache instance. When provided, checks for a
               cached result before calling the API and saves successful
               results after the call.
    """
    website      = normalize_url(website)

    # Cache lookup — skip API call if we have a fresh result
    if cache is not None:
        cached = cache.get(name, city, state)
        if cached is not None:
            return cached
    location     = ", ".join(filter(None, [city, state]))
    website_note = f"Their listed website is: {website}" if website else "No website listed."

    # Scrape the website directly so Perplexity has real page content to reason
    # about, rather than relying purely on search for sites it can't index well.
    scrape_section       = ""
    scrape_gave_signal   = False  # True when scrape produced actionable info
    scrape_domain_dead   = False  # True when scrape confirmed the domain/site is gone
    scrape_cost          = 0.0   # API cost for Firecrawl (0.0 for direct HTTP or no URL)
    if website:
        scraped = scrape_website(website)
        scrape_cost = scraped.get("scrape_cost", 0.0)
        if scraped["success"] and not scraped["is_slop"] and scraped["text"]:
            # Real content retrieved — give Perplexity the page text
            scrape_section = (
                f"\nDIRECT WEBSITE CONTENT (retrieved from {website}):\n"
                f"---\n{scraped['text']}\n---\n"
                "Use this content alongside your search to evaluate whether the site "
                "shows a real, currently operating business.\n"
            )
            scrape_gave_signal = True
        elif scraped["success"] and scraped["is_slop"]:
            # Parking/placeholder/spam-squatted page — domain has lapsed or been taken over
            note_text = scraped["note"]
            if any(kw in note_text.lower() for kw in ["gambling", "togel", "casino", "slot", "porn", "adult", "spam"]):
                domain_note = "The domain has been taken over by a spam or gambling site — the business lost control of it."
            else:
                domain_note = "The business may have let this domain lapse."
            scrape_section = (
                f"\nNOTE: Direct retrieval of {website} returned a parking, placeholder, or spam-squatted page "
                f"({note_text}) — {domain_note} "
                "Treat the website as non-functional. You MUST check all social media channels (Facebook, Instagram, "
                "LinkedIn) before drawing any conclusion — many businesses with dead domains still operate actively "
                "through social media alone.\n"
            )
            scrape_gave_signal = True
            scrape_domain_dead = True
        elif not scraped["success"] and scraped["note"]:
            note = scraped["note"]
            if "404" in note:
                scrape_section = (
                    f"\nNOTE: Direct access to {website} returned a 404 error — "
                    "the website content no longer exists at this URL. This is a "
                    "meaningful closure signal. Factor it into your assessment.\n"
                )
                scrape_gave_signal = True
                scrape_domain_dead = True
            elif any(kw in note.lower() for kw in ["dns", "name or service", "nodename", "connection", "refused", "timed out"]):
                scrape_section = (
                    f"\nNOTE: Direct access to {website} failed with a DNS or "
                    "connection error — the domain may no longer exist or has expired. "
                    "This is a strong closure signal. Factor it into your assessment.\n"
                )
                scrape_gave_signal = True
                scrape_domain_dead = True
            # Generic failures (SSL issues, blocked, etc.) — no signal, let Perplexity search normally.

    business_prompt = (
        f'Business name: "{name}"\n'
        f"Location on file: {location}\n"
        f"{website_note}{scrape_section}\n"
        "LOCATION NOTE: The location above is where this business is registered or based, "
        "not necessarily where it operates. Many veteran-owned businesses sell nationally, "
        "work online, or are home-based. Never require the city or state to appear on the "
        "website or social media — it often won't."
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": business_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": BusinessStatus.model_json_schema()},
        },
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)

            # Rate limited — wait and retry
            if response.status_code == 429:
                wait = 30 * (attempt + 1)
                time.sleep(wait)
                continue

            # Server error (5xx) — transient, worth retrying
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(15 * (attempt + 1))
                    continue
                return _error_result(f"HTTP {response.status_code}: {response.text[:120]}")

            # Other non-200 (4xx etc.) — don't retry
            if response.status_code != 200:
                return _error_result(f"HTTP {response.status_code}: {response.text[:120]}")

            data      = response.json()
            content   = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            cost      = _calculate_cost(data.get("usage", {})) + scrape_cost

            parsed = BusinessStatus.model_validate_json(content)

            status     = parsed.status
            confidence = parsed.confidence

            # Post-process No Web Presence based on what the scraper found.
            # Decision matrix:
            #   - Scrape confirmed dead domain + Perplexity found search results
            #     (citations non-empty) → upgrade to Likely Closed (the business
            #     existed somewhere but is now off the web)
            #   - Scrape confirmed dead domain + Perplexity found NOTHING
            #     (citations empty) → keep NWP, the AI's verdict is correct;
            #     this is genuinely unverifiable
            #   - Scrape had real content but Perplexity said NWP → Uncertain
            #     (mismatch worth flagging for human review)
            #   - Scrape had no signal at all → Uncertain (couldn't confirm,
            #     flag for review)
            evidence = parsed.evidence
            if status == "No Web Presence" and website:
                if scrape_domain_dead and scrape_gave_signal:
                    if citations:
                        # AI found search results but said NWP — likely a
                        # conservative AI call on a genuinely closed business.
                        status     = "Likely Closed"
                        confidence = max(confidence, 70)
                        evidence   = f"[Domain confirmed dead via direct check] {evidence}"
                    else:
                        # AI found nothing AND domain is dead → NWP is correct.
                        # Keep it; flag for human review since URL was on file.
                        evidence = f"[Domain dead, no search results found — NWP confirmed] {evidence}"
                elif not scrape_gave_signal:
                    # No URL signal at all (URL present but scraper couldn't connect).
                    status     = "Uncertain"
                    confidence = max(confidence, 40)
                    evidence   = f"[URL on file but could not confirm content — flagged for review] {evidence}"

            # Aggregator-only Uncertain → Likely Closed override.
            # Fires only when AI hedged Uncertain on a dead-domain business
            # whose entire web footprint is data-broker / DOT / static directory
            # listings — record-of-existence with no proof of current activity.
            # Self-citations (the business's own dead domain) are filtered out
            # so they don't block the override.
            if (
                status == "Uncertain"
                and scrape_domain_dead
                and confidence < AGGREGATOR_OVERRIDE_MAX_CONFIDENCE
                and _all_citations_are_aggregators(citations, own_website=website)
            ):
                status     = "Likely Closed"
                confidence = max(confidence, 70)
                evidence   = (
                    "[Dead domain + only aggregator/directory citations — "
                    "no social, maps, or press signal found] " + evidence
                )

            if citations:
                sources = ", ".join(citations[:3])  # cap at 3 URLs
                evidence = f"{evidence} | Sources: {sources}"

            requires_review, review_reason = _compute_triage(status, confidence)

            result = {
                "status":          status,
                "confidence":      str(confidence),  # stored as string — checkpoint.py and callers expect "0"–"100"
                "evidence":        evidence,
                "citations":       citations,
                "cost_usd":        cost,
                "error":           None,
                "requires_review": requires_review,
                "review_reason":   review_reason,
            }

            if cache is not None:
                cache.put(name, city, state, result)

            return result

        except (ValidationError, json.JSONDecodeError) as e:
            # Structured output parse failed — return Uncertain, don't retry
            return _error_result(f"Parse error: {str(e)[:120]}", scrape_cost)

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            return _error_result("Request timed out after max retries.", scrape_cost)

        except requests.exceptions.RequestException as e:
            return _error_result(f"Request error: {str(e)[:120]}", scrape_cost)

        except Exception as e:
            return _error_result(f"Unexpected error: {str(e)[:120]}", scrape_cost)

    return _error_result("Failed after max retries.", scrape_cost)


def _error_result(message: str, scrape_cost: float = 0.0) -> dict:
    return {
        "status":          "Uncertain",
        "confidence":      "0",
        "evidence":        message,
        "citations":       [],
        "cost_usd":        scrape_cost,
        "error":           message,
        "requires_review": True,
        "review_reason":   "API error — manual investigation required.",
    }


# ── Multi-pass verification ───────────────────────────────────────────────────

def check_business_3pass(
    api_key: str,
    name: str,
    website: str,
    city: str,
    state: str,
    max_retries: int = MAX_RETRIES,
    cache=None,
) -> dict:
    """Run check_business 3 times and use majority-vote stability as the
    confidence signal.

    Auto-trust requires:
      - all 3 passes return the same status (stable across runs), AND
      - verdict passes triage (Active or Likely Closed ≥ 80%)

    On disagreement, the most common verdict is reported but flagged for
    human review. All 3 verdicts are recorded in the result dict.

    The 1st pass uses the supplied cache (for resumability); passes 2 and 3
    bypass the cache to force fresh searches.

    Cost: 3x single-pass. Use for high-stakes batches.
    """
    pass1 = check_business(
        api_key, name, website, city, state, max_retries=max_retries, cache=cache
    )
    if pass1.get("error") is not None:
        return pass1

    pass2 = check_business(
        api_key, name, website, city, state, max_retries=max_retries, cache=None
    )
    pass3 = check_business(
        api_key, name, website, city, state, max_retries=max_retries, cache=None
    )

    # Collect statuses, ignoring failed passes (treat as no-vote)
    votes = []
    for p in (pass1, pass2, pass3):
        if p.get("error") is None:
            votes.append(p["status"])

    if not votes:
        return pass1  # all 3 failed — return whatever pass 1 said

    # Majority vote (Counter is in collections; use simple counting for clarity)
    vote_counts: dict[str, int] = {}
    for v in votes:
        vote_counts[v] = vote_counts.get(v, 0) + 1
    majority_status = max(vote_counts, key=lambda k: vote_counts[k])
    majority_count = vote_counts[majority_status]
    all_agree = majority_count == len(votes) == 3

    # Take highest confidence among the runs that voted for the majority status
    matching_confs = []
    for p in (pass1, pass2, pass3):
        if p.get("error") is None and p["status"] == majority_status:
            try:
                matching_confs.append(int(p["confidence"]))
            except (ValueError, TypeError):
                pass
    chosen_conf = max(matching_confs) if matching_confs else int(pass1.get("confidence", 0))

    total_cost = sum(p.get("cost_usd", 0.0) for p in (pass1, pass2, pass3))
    citations = pass1.get("citations", [])  # use pass 1's citations as primary

    # Decide review status
    triage_review, triage_reason = _compute_triage(majority_status, chosen_conf)
    if not all_agree:
        # Any disagreement → flag for review regardless of triage
        requires_review = True
        review_reason = (
            f"3-pass disagreement: {pass1['status']}/{pass2['status']}/{pass3['status']}. "
            f"Majority: {majority_status} ({majority_count}/3)."
        )
        evidence_prefix = (
            f"[3-pass disagreement — Pass 1: {pass1['status']}, "
            f"Pass 2: {pass2['status']}, Pass 3: {pass3['status']}] "
        )
    elif triage_review:
        # All 3 agreed but on a status that always needs review (Uncertain, NWP)
        requires_review = True
        review_reason = (
            f"3-pass agreement on '{majority_status}', but verdict still requires review: "
            + (triage_reason or "")
        )
        evidence_prefix = f"[3-pass agreement on {majority_status} — stable hedge] "
    else:
        # All 3 agreed on an auto-trustable verdict — promote
        requires_review = False
        review_reason = None
        evidence_prefix = f"[3-pass agreement: all runs returned {majority_status}] "

    return {
        "status":          majority_status,
        "confidence":      str(chosen_conf),
        "evidence":        evidence_prefix + pass1.get("evidence", ""),
        "citations":       citations,
        "cost_usd":        total_cost,
        "error":           None,
        "requires_review": requires_review,
        "review_reason":   review_reason,
        "verifier_ran":    True,
        "pass1_status":    pass1["status"],
        "pass2_status":    pass2["status"],
        "pass3_status":    pass3["status"],
        "pass1_confidence": pass1["confidence"],
        "pass2_confidence": pass2["confidence"],
        "pass3_confidence": pass3["confidence"],
    }


# ── Two-pass verification (deferred 2nd pass on flagged results) ──────────────

def check_business_with_verification(
    api_key: str,
    name: str,
    website: str,
    city: str,
    state: str,
    max_retries: int = MAX_RETRIES,
    cache=None,
) -> dict:
    """Run check_business once. If the result is flagged for review, run a
    second pass (cache-bypassed) and merge.

    Merge behavior:
      - If pass 2 status matches pass 1 → upgrade to auto-trusted, evidence
        is annotated with "[2-pass agreement]".
      - If pass 2 status disagrees → keep flagged for human review, evidence
        carries both verdicts side-by-side.
      - The pass 1 + pass 2 costs are summed in cost_usd.
      - Original pass 1 verdict is preserved in pass1_status / pass1_confidence
        so callers can audit what changed.

    The 2nd pass always bypasses the cache (cache=None) to force a fresh
    Perplexity call — using a cached result would defeat the purpose.

    On a typical batch, pass 2 fires on 40–60% of records. Cost increase is
    proportional to that flag rate.
    """
    pass1 = check_business(
        api_key, name, website, city, state, max_retries=max_retries, cache=cache
    )

    # Don't double-check API errors — they need human attention regardless.
    if pass1.get("error") is not None:
        return pass1

    # Don't double-check rows that are already auto-trusted.
    if not pass1.get("requires_review", False):
        return pass1

    # Run pass 2 with cache disabled so we get a genuinely fresh search.
    pass2 = check_business(
        api_key, name, website, city, state, max_retries=max_retries, cache=None
    )

    if pass2.get("error") is not None:
        # Pass 2 failed — keep pass 1 result, note the failure.
        pass1["evidence"] = (
            f"[2nd pass failed: {pass2.get('error', 'unknown')[:80]}] "
            + pass1["evidence"]
        )
        pass1["cost_usd"] = pass1.get("cost_usd", 0.0) + pass2.get("cost_usd", 0.0)
        return pass1

    merged = dict(pass1)
    merged["pass1_status"]     = pass1["status"]
    merged["pass1_confidence"] = pass1["confidence"]
    merged["pass2_status"]     = pass2["status"]
    merged["pass2_confidence"] = pass2["confidence"]
    merged["cost_usd"]         = pass1.get("cost_usd", 0.0) + pass2.get("cost_usd", 0.0)
    merged["verifier_ran"]     = True

    if pass1["status"] == pass2["status"]:
        # Both passes agree on a verdict — but only promote to auto-trusted if
        # the verdict itself is one we can auto-trust. Two passes both saying
        # "Uncertain" or "No Web Presence" is stable hesitancy, NOT confirmation
        # — those statuses always need human review.
        agreed_status = pass1["status"]
        try:
            higher_conf = max(int(pass1["confidence"]), int(pass2["confidence"]))
            merged["confidence"] = str(higher_conf)
        except (ValueError, TypeError):
            higher_conf = int(pass1["confidence"])

        # Re-run triage on the merged verdict + confidence
        new_review, new_reason = _compute_triage(agreed_status, higher_conf)
        merged["requires_review"] = new_review

        if new_review:
            # Verdict is auto-review status (Uncertain/NWP) or below threshold
            # — agreement doesn't override the review requirement.
            merged["review_reason"] = (
                f"2-pass agreement on '{agreed_status}', but verdict still requires review: "
                + (new_reason or "")
            )
            merged["evidence"] = (
                f"[2-pass agreement on {agreed_status} — stable hedge] "
                + pass1["evidence"]
            )
        else:
            # Genuinely promotable: high-confidence Active or Likely Closed,
            # confirmed by a second pass.
            merged["review_reason"] = None
            merged["evidence"] = (
                f"[2-pass agreement: both runs returned {agreed_status}] "
                + pass1["evidence"]
            )
    else:
        # Disagreement — keep flagged but record both verdicts.
        merged["status"]          = pass1["status"]
        merged["confidence"]      = pass1["confidence"]
        merged["requires_review"] = True
        merged["review_reason"]   = (
            f"Pass 1: {pass1['status']} ({pass1['confidence']}%), "
            f"Pass 2: {pass2['status']} ({pass2['confidence']}%) — verdicts disagree."
        )
        merged["evidence"] = (
            f"[2-pass disagreement — Pass 1: {pass1['status']}, Pass 2: {pass2['status']}] "
            f"{pass1['evidence']} || Pass 2 evidence: {pass2['evidence'][:200]}"
        )

    return merged


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv

    # Load .env from the project root (one level up from tools/)
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY not set in .env file.")
        print("Copy .env.example to .env and fill in your key.")
        exit(1)

    # Test with a well-known business that is definitely still open
    print("Testing check_business with a known active business...")
    result = check_business(
        api_key=api_key,
        name="Target",
        website="https://www.target.com",
        city="Minneapolis",
        state="MN",
    )

    print(f"\nStatus:     {result['status']}")
    print(f"Confidence: {result['confidence']}%")
    print(f"Evidence:   {result['evidence']}")
    if result["citations"]:
        print(f"Citations:  {result['citations'][:3]}")
    if result["error"]:
        print(f"Error:      {result['error']}")
