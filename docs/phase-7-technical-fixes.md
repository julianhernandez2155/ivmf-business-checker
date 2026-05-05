# IVMF Business Checker — Technical Fix List
## Based on: bmosg_v1_baseline (69.0% agreement, n=58)
## Analyst: Claude Sonnet 4.6 | Date: 2026-04-28

---

## Executive Summary — Top 5 Fixes (Ranked by Impact ÷ Effort)

| Rank | Fix | Impact (rows) | Effort | Confidence |
|------|-----|---------------|--------|------------|
| 1 | **F1: Pattern-B Decisiveness Overhaul** | 9 disagreements | S | High |
| 2 | **F2: Hijacked-Domain Mandatory Social Check** | 1 disagreement + regression prevention on similar rows | XS | High |
| 3 | **F3: Etsy /people/ vs /shop/ URL Guard** | 1 disagreement (but high-confidence false Active — worst error type) | XS | High |
| 4 | **F4: NWP/Likely-Closed Boundary + Post-processing Override Fix** | 2 disagreements + fixes over-aggressive post-processing | S | High |
| 5 | **F5: Marketplace Redirect Handling (Amazon/Etsy shop links)** | 2 disagreements | XS | High |

**Realistic projection:** Applying F1–F5 resolves 14–15 of 18 disagreements → ~93% agreement on this eval set. Real-world improvement expected at 85–90% given unseen data variation.

---

## Full Ranked Fix List

---

### F1: Pattern-B Decisiveness Overhaul

**Failure mode addressed:** Pattern-B-hesitancy — AI hedges to Uncertain when evidence clearly supports Likely Closed.

**Disagreement rows resolved:** 31 (King's Coffee), 163 (Dashfire Beards), 177 (Peachy Keen Perfume), 286 (Sword & Plough), 380 (A Simple Organizing), 470 (TTG Properties), 538 (Spectra Cargo), 680 (Bundook), plus partial improvement on 193 (Alpha Outpost — see F2)

**Specific code change:**

In `/Users/Julian/workspace/ivmf/code/ivmf-business-checker/business_checker/tools/check_business.py`, replace lines 139–144 (the "STALE RECORDS WITH NO CORROBORATION" section) with the following expanded block. Insert it ABOVE the existing `SQUATTED / HIJACKED DOMAINS` section:

```
PATTERN B — WHEN TO COMMIT TO "Likely Closed" (not "Uncertain"):

"Uncertain" requires at least ONE positive recency signal: a social post, marketplace listing, or press coverage from 2024 or later that is SPECIFICALLY about this business. If you cannot cite one, do not use Uncertain.

When you have ALL of the following, commit to "Likely Closed" at 65–80% confidence:
  (a) The website is non-functional: 404, DNS failure, domain-for-sale parking page, empty Wix/Weebly/Square/Squarespace placeholder with no business-specific content, or "coming soon / opening soon" page with no evidence the site ever launched
  (b) No Google Business Profile showing as open, or Maps shows "Permanently closed"
  (c) No Facebook or Instagram post from 2024 or later specifically from this business
  (d) No current marketplace storefront with in-stock products (for product businesses)
  (e) The only results are: state incorporation records, old directory listings (ZoomInfo, Manta, FMCSA, Infogroup, OpenFOS, BBB with no recent reviews), or press/media articles from before 2023

If (a)–(e) all apply → "Likely Closed" at 65–75%. This is Pattern B. Do NOT hedge to "Uncertain".

"Coming soon" / "Opening soon" sites: If the site has been in "coming soon" status with no launch evidence and no active social presence showing the business operating, and the business appeared in a directory 12+ months ago, it almost certainly never launched. Classify as "Likely Closed".

Regulatory records that do NOT count as activity evidence:
  • FMCSA DOT numbers (never expire, inactive carriers keep them)
  • State LLC / incorporation records (entities stay registered for years after closure)
  • SBA certifications (expire on a schedule, not based on activity)
  • Old directory auto-generated listings (Manta, ZoomInfo, OpenFOS)
  These records confirm the entity once existed. They say nothing about whether it is operating today.
```

**Where it goes:** `check_business.py`, replacing lines 143–145 (the "STALE RECORDS WITH NO CORROBORATION" block) and extending from there. The existing text at lines 143–145 reads:
```
STALE RECORDS WITH NO CORROBORATION:
- If the only evidence you can find is a state incorporation record or a basic directory listing (Manta, OpenFOS, Infogroup, etc.) with no activity after 2021, and no social media, no maps, no press, no owner activity — that is NOT enough to call a business "Uncertain". Call it "Likely Closed" (multiple stale signals with nothing recent = closure pattern).
- Old incorporation records alone are not evidence of current operation.
```
Replace those 3 lines with the PATTERN B block above. This is a drop-in replacement — same structural position in the prompt, significantly more explicit decision logic.

**Risk of regression:** Low-to-moderate. The risk is over-triggering on businesses that are genuinely Uncertain — specifically, businesses where the labeler found a 2024 social post but the AI couldn't find it (missed-channel cases like row 583 Achieve New Heights). The fix correctly excludes those because condition (c) requires no 2024+ posts; if the post exists but the AI missed it, condition (c) is still satisfied from the AI's perspective, which is the same error that already exists. Net: this fix doesn't make missed-channel errors worse. However, the fix could incorrectly tip borderline businesses (e.g., one with a March 2023 Instagram post) from Uncertain to Likely Closed, since 2023 does not meet the "2024 or later" bar. Watch for this in the re-run.

**Effort:** S (30 minutes — prompt text replacement + re-run verification)

**Confidence in fix working:** High. The AI's prompt already has a weaker version of this rule that it fails to apply consistently. Making the rule explicit and enumerated with a named pattern ("Pattern B") should reduce AI hedging. All 9 rows in this bucket follow the same evidence profile: dead domain + stale directories only.

---

### F2: Hijacked-Domain Mandatory Social Check

**Failure mode addressed:** Hijacked-domain — AI stopped at Uncertain after finding a spam/squatted domain instead of continuing to social media where a definitive closure announcement existed.

**Disagreement rows resolved:** 193 (Alpha Outpost — "Our store is permanently closed!" pinned on Instagram)

**Specific code change:**

In `check_business.py`, find the existing `SQUATTED / HIJACKED DOMAINS` section (lines 139–142):

```
SQUATTED / HIJACKED DOMAINS:
- If a domain now hosts gambling, adult content, spam, generic blog content, or a parking page clearly unrelated to the original business — treat it as a dead domain. It counts as one closure signal.
- Squatted domain + no social media activity + no Google Maps listing + no other channel hits = "Likely Closed". Do NOT call this "Uncertain" just because you cannot find an explicit closure announcement.
```

Replace with:

```
SQUATTED / HIJACKED DOMAINS:
- If a domain now hosts gambling, adult content, spam, generic blog content, or a parking page clearly unrelated to the original business — treat it as a dead domain. It counts as one closure signal.
- MANDATORY: When you detect a hijacked or squatted domain, you MUST check Instagram and Facebook before issuing any verdict. This is non-negotiable. Businesses frequently post closure announcements on social media when their domain lapses. Look for pinned posts saying "we are closed", "permanently closed", "our store is closed", or similar.
- If you find a social closure announcement → "Likely Closed" (strong signal, 85–95%).
- Squatted domain + checked social and found no posts since 2023 + no Google Maps listing + no other channel hits = "Likely Closed" at 70–80%. Do NOT call this "Uncertain".
- Squatted domain + found active 2024+ social posts = investigate further (may be Uncertain if status unclear, or Active if business is clearly operating through social alone).
```

**Where it goes:** `check_business.py`, the `SQUATTED / HIJACKED DOMAINS` section, approximately lines 139–142.

**Risk of regression:** Very low. The change adds a mandatory investigation step, not a new verdict rule. The only way this creates a regression is if checking social media surfaces misleading content (e.g., a hijacked Instagram). That edge case is so rare it's not worth suppressing the fix. Rows that were previously correct on hijacked-domain cases stay correct — the mandatory social check either confirms what the AI already found or adds new signal.

**Effort:** XS (15 minutes)

**Confidence in fix working:** High. Row 193 is a clear case where the AI stopped short of a definitive channel. The pinned Instagram post "Our store is permanently closed!" is exactly the kind of signal the prompt should mandate checking for.

---

### F3: Etsy /people/ vs /shop/ URL Guard

**Failure mode addressed:** Marketplace-handling — AI cited `etsy.com/people/X` (a user favorites profile) as evidence of an active shop, scoring Active at 95% confidence.

**Disagreement rows resolved:** 271 (Princess Leahs Designs — AI cited profile page, not shop)

**Specific code change:**

In `check_business.py`, find the existing `CHANNEL 7 — MARKETPLACES` section (lines 115–119) and add the following paragraph at the end:

```
MARKETPLACE URL PATTERNS — know the difference:
  • etsy.com/shop/X → this is a storefront. Valid evidence of business presence.
  • etsy.com/people/X → this is a USER PROFILE showing favorited items from OTHER sellers. NOT a storefront. Do not cite this as evidence of an active business.
  • etsy.com/market/X → this is a category/search results page. NOT a specific business's shop.
  • amazon.com/stores/X or amazon.com/s?rh=p_4:X → brand storefront or seller search. Valid if products are in stock.
  • amazon.com/sp?seller=X or amazon.com/gp/aag/main?seller=X → seller profile. Valid if reviews are recent.
  When you have an Etsy /people/ URL, search for the corresponding /shop/ URL by replacing "people" with "shop" in the path, or search Etsy directly for the business name to find their actual shop. If no shop is found, treat as missing evidence.
```

**Where it goes:** `check_business.py`, end of `CHANNEL 7 — MARKETPLACES` section, after line 119 (after "Products listed as unavailable or removed = weak closure signal.").

**Risk of regression:** Minimal. This rule is precise and structural — it targets a specific URL pattern that is definitionally not a business storefront. No existing correctly-classified row could be harmed by this unless it also has an Etsy /people/ URL (none in the dataset). The rule to search for /shop/ as a fallback may surface additional evidence that changes Uncertain → Active for some rows, which would be correct behavior.

**Effort:** XS (10 minutes)

**Confidence in fix working:** High. The URL pattern distinction is objective and unambiguous. The AI's error was not inferential — it was accepting a wrong URL type as valid evidence. A structural rule eliminates this class of error entirely.

---

### F4: NWP/Likely-Closed Boundary Clarification + Post-Processing Override Fix

**Failure mode addressed:**
- (4a) Prompt: AI conflates No Web Presence with Likely Closed when the business has a dead domain but no search results — should be NWP.
- (4b) Post-processing: The override at `check_business.py:332–336` converts any AI-produced NWP to Likely Closed whenever `scrape_domain_dead=True`. This is too aggressive — it fires even when the AI correctly identified NWP because the domain is dead AND there are no search results. This misfires on rows 125 (Emotion On Walls) and 88 (SerenaTea).

**Disagreement rows resolved:** 125 (Emotion On Walls — AI said Likely Closed, Julian said NWP), 88 (SerenaTea — AI said Uncertain, Julian said NWP)

**Specific code change — Part A (Prompt):**

In `check_business.py`, find the existing `NO WEB PRESENCE — use it precisely` section (lines 150–154) and replace it:

**Current text:**
```
NO WEB PRESENCE — use it precisely:
- Only use "No Web Presence" if you found NOTHING specific to this business across all 8 channels — not even an old directory listing, not even an owner social profile.
- If you found any result that specifically names this business (even an old one), use "Uncertain" or "Likely Closed" instead.
- A personal Whitepages or RocketReach profile for an individual is NOT a business web presence.
```

**Replace with:**
```
NO WEB PRESENCE — use it precisely:
- Use "No Web Presence" ONLY when: the domain is dead (or no website was listed), AND all 8 channels returned zero results specifically about this business — not even an old directory listing, not even a social profile, not even a press mention with this business name.
- "No Web Presence" is NOT Likely Closed. It means the business is unverifiable — there is simply nothing to evaluate.
- If ANY search returned a result specifically naming this business (old directory listing, social profile, news mention), use "Likely Closed" (stale signals) or "Uncertain" (some activity found) instead.
- Generic placeholder pages (Wix, Weebly, Square "coming soon" templates with zero business-specific content, no products, no owner name, no contact info specific to this business) are NOT a web presence. If this is the only thing you found and search returns nothing → "No Web Presence".
- A personal Whitepages or RocketReach profile for an individual is NOT a business web presence.
- When in doubt between NWP and Likely Closed: if you can cite at least one result that specifically names this business, it is Likely Closed. If you cannot cite any result about this business specifically, it is NWP.
```

**Specific code change — Part B (Post-processing override):**

In `check_business.py`, find lines 332–341:

```python
evidence = parsed.evidence
if status == "No Web Presence" and website:
    if scrape_domain_dead:
        status     = "Likely Closed"
        confidence = max(confidence, 70)
        evidence   = f"[Domain confirmed dead via direct check] {evidence}"
    else:
        status     = "Uncertain"
        confidence = max(confidence, 40)
        if not scrape_gave_signal:
            evidence = f"[URL on file but could not confirm content — flagged for review] {evidence}"
```

Replace with:

```python
evidence = parsed.evidence
if status == "No Web Presence" and website:
    if scrape_domain_dead and scrape_gave_signal:
        # Scraper confirmed dead domain AND Perplexity said NWP.
        # Only upgrade to Likely Closed if the AI also found at least some
        # search results (citations list is non-empty) — meaning the business
        # appeared somewhere on the web. If Perplexity found nothing AND
        # the domain is dead, NWP is the correct call. Don't override it.
        if citations:
            # AI found something via search but still said NWP — likely
            # a conservative AI call on a genuinely closed business.
            status     = "Likely Closed"
            confidence = max(confidence, 70)
            evidence   = f"[Domain confirmed dead via direct check] {evidence}"
        else:
            # AI found nothing AND domain is dead → NWP is correct, keep it.
            # Add a note for human review since the URL was on file.
            evidence   = f"[Domain dead, no search results found — NWP confirmed] {evidence}"
    elif not scrape_gave_signal:
        # No URL signal at all (URL present but scraper couldn't connect)
        status     = "Uncertain"
        confidence = max(confidence, 40)
        evidence   = f"[URL on file but could not confirm content — flagged for review] {evidence}"
```

**Where it goes:**
- Part A: `check_business.py` lines 150–154 (NWP section of SYSTEM_PROMPT)
- Part B: `check_business.py` lines 332–341 (post-processing block)

**Risk of regression:**
- Part A (prompt): Low. The NWP prompt now has a clear decision rule. Risk is prompting the AI to use NWP too broadly on cases where a stale result actually exists. Mitigation: the "if you can cite ANY result → Likely Closed" rule keeps the bar high for NWP.
- Part B (post-processing): Moderate. The current override at line 333 fires on every NWP+dead-domain case and was converting NWP → Likely Closed even for rows like 125 and 88 where NWP was correct. The new logic only upgrades when citations are non-empty. **Regression to check:** rows where the AI correctly said NWP but with non-empty citations (a case where it found some business info but still said NWP — the current override would correctly upgrade those, and the new logic preserves that behavior). Rows where AI said NWP with empty citations now stay NWP instead of becoming Likely Closed — this is the desired behavior for rows 125 and 88.

**Effort:** S (45 minutes for both changes + verification)

**Confidence in fix working:** High for Part B (it's deterministic code logic, not AI behavior). Medium-high for Part A (the prompt is more explicit, but the AI's NWP vs. Likely Closed confusion may persist on edge cases).

---

### F5: Marketplace Redirect and Single-Channel Business Handling

**Failure mode addressed:** Single-channel-business and marketplace-redirect — AI failed to follow Amazon redirect links from a website (row 114), and failed to treat a Facebook-URL-as-website as a primary channel (row 556).

**Disagreement rows resolved:** 114 (Disgruntled Decks — products redirect to Amazon, AI said no e-commerce), 556 (Spicers Nicer Massage — listed website IS a Facebook page, AI found no recent dates)

**Specific code change:**

In `check_business.py`, find the `FAST PATH` section (starting around line 56) and add the following to the list of "Qualifies as Active" criteria:

```
       • Product pages on the business's website redirect to an active Amazon listing, active Etsy shop listing, or other marketplace with current stock — many veteran businesses use their website as a portfolio and the marketplace as the actual storefront. Follow the commerce link.
       • The listed "website" URL is itself a Facebook, Instagram, or LinkedIn page (i.e., the URL contains facebook.com, instagram.com, or linkedin.com) — evaluate it as the PRIMARY channel. If the most recent post or update is within 12 months and shows business activity (services, products, events, updates), this is Active.
```

Also add to `CHANNEL 3 — FACEBOOK` (lines 93–96), at the end of that section:

```
  • IMPORTANT: If the listed website URL in the dataset IS a Facebook page URL, evaluate that page as the primary evidence source, not as a social media supplement. The absence of a separate domain website is not a negative signal — this is a Facebook-native business.
  • When viewing a Facebook business page, check the "Posts" tab for recency, not just whether a page exists.
```

**Where it goes:**
- FAST PATH addition: `check_business.py` after line 65 (after "informational site for a business that clearly sells in person" bullet)
- CHANNEL 3 addition: after line 96 (after "No page found = note it and continue.")

**Risk of regression:** Low. The Amazon redirect rule only fires when product links on the website redirect to a marketplace — that's a specific, observable behavior. The false-positive risk is a site that links to Amazon for an unrelated product, but that's a very unlikely scenario in a veteran-business context. The Facebook-as-website rule is additive and specific: it only changes behavior when the literal URL in the dataset contains `facebook.com`. No existing correctly-classified row has a Facebook URL as its listed website (all active rows with strong Facebook signals had separate domain websites).

**Effort:** XS (20 minutes)

**Confidence in fix working:** High for the Disgruntled Decks (row 114) pattern — the prompt explicitly tells the AI to follow commerce redirect links. Medium for the Spicers Nicer (row 556) pattern — the AI's failure appears to be in recognizing recent post dates on Facebook, which may be a Perplexity retrieval limitation more than a prompt issue. The prompt change is correct but may not fully resolve row 556 if Perplexity's Facebook indexing is stale.

---

### F6: Fast Path Recency Tightening + Social Override for Single-Source Active

**Failure mode addressed:** URL-misinterpretation — AI scored Active at 100% confidence (row 85, Reflections of Service) on a website that explicitly says it's accepting only limited orders, and whose last social media post was July 2020.

**Disagreement rows resolved:** 85 (Reflections of Service)

**Specific code change:**

In `check_business.py`, find the `FAST PATH` section. The current criteria include:
```
       • A service business with a contact form, phone number, or booking link and real service descriptions
```

Replace that bullet with:
```
       • A service business with a contact form, phone number, or booking link and real service descriptions — BUT: if the site explicitly states it is NOT accepting new orders, has limited availability, or is in hiatus, it does NOT qualify for the Fast Path. Proceed to Full Investigation.
```

Also add a new Fast Path disqualifier:
```
  Does NOT qualify — proceed to Full Investigation:
       ...
       • The website explicitly states limitations on accepting new work (e.g., "not accepting new orders," "limited availability," "currently not taking clients")
       • Website content is present but ALL content and dates are from 2021 or earlier AND there is no copyright year from 2022+ in the footer
```

And tighten the confidence rubric at lines 159–160:
```
  Active 95–100: Multiple channels confirm current operation with recent dates (2024–2026).
  Active 80–94:  One channel clearly confirms active operation, recency somewhat unclear.
  Active 60–79:  Single weak or indirect Active signal (old directory listing with one recent review).
```
The rubric is already reasonable. The issue is the AI self-assigned 100 on a single-channel weak signal. Add to the rubric:
```
  NEVER assign Active 90+ based solely on website content if:
    - No social media recency has been verified, AND
    - The site contains no dated content from 2024 or later (blog post, review, copyright year)
  Without at least one of these, cap Active confidence at 79.
```

**Where it goes:** `check_business.py`, FAST PATH section (around lines 57–72) and CONFIDENCE SCORE RUBRIC (lines 157–172).

**Risk of regression:** Low-moderate. The tightening of "service business with contact info" could cause regressions on legitimate service businesses that have good websites with real descriptions but no dated content. The rubric cap (Active 79 without dated content or social verification) is the riskier change — some Active businesses may not have explicitly dated content on the website, but the AI infers from context that they're active. Monitor rows 94 (Mobile Cigar Lounge — no footer copyright), 562 (Back Office Administrators) on re-run.

**Effort:** S (30 minutes)

**Confidence in fix working:** Medium-high. The "not accepting new orders" language detection is reliable. The rubric confidence cap reduces false Active cases at high confidence, which directly addresses the 90–100 band false Active failures. But this is an AI rubric instruction, not deterministic code — the AI may still self-assign 90+ in some cases.

---

### F7: LLC/Inc Suffix Stripping on Social Media Search Retry

**Failure mode addressed:** Missed-channel — AI searched "Achieve New Heights LLC San Antonio Texas" on LinkedIn, found nothing, and concluded no social presence. Julian searched "Achieve New Heights" and found posts from 1 month ago.

**Disagreement rows resolved:** 583 (Achieve New Heights LLC) — partial improvement. Also potentially helps rows 258 (L'aube Boutique) and others where social channels were missed.

**Specific code change:**

In `check_business.py`, find `CHANNEL 5 — LINKEDIN` (lines 104–108) and add:

```
  SEARCH VARIANT RULE: LinkedIn and Facebook frequently fail to return results when searching with city/state modifiers or legal suffixes. If "[BUSINESS NAME] [LOCATION]" returns no results:
    1. Retry with "[BUSINESS NAME]" alone (no city/state)
    2. If the business name includes LLC, Inc, Corp, Ltd, Co., or similar suffixes, also retry without the suffix
    3. If the business name is an acronym or abbreviation, search both the acronym and any spelled-out version you can infer
  Finding the social profile on a retry counts as finding the social profile.
```

Apply the same variant rule to `CHANNEL 3 — FACEBOOK` and `CHANNEL 4 — INSTAGRAM`.

**Where it goes:** `check_business.py`, Channels 3, 4, and 5 in FULL INVESTIGATION (lines 93–108).

**Risk of regression:** Low. This is an additive instruction — the AI should already be searching broadly, and this makes the search strategy explicit. The only regression risk is the AI finding a wrong business with a similar name after stripping the suffix (e.g., "Achieve New Heights" matching a different "Achieve New Heights" business in another city). Mitigated by the existing instruction to "only use evidence specifically about THIS business." No known regressions in the dataset from this change.

**Effort:** S (25 minutes — three channel sections, similar text each)

**Confidence in fix working:** Medium. This is a Perplexity-side behavior — the prompt instructs the AI to retry, but Perplexity's actual search behavior may or may not respect this. Julian's manual retries worked because he personally typed the query; Perplexity's agent may not perform discrete retry steps. This fix is directionally correct but may have lower implementation fidelity than prompt changes that affect verdict logic rather than search strategy.

---

### F8: Footer Copyright Year Extraction (Scraper Enhancement)

**Failure mode addressed:** Scraper does not extract or surface the footer copyright year — a signal Julian uses heavily in rows 132, 219, 223 and which would have been decisive in row 85 (Reflections of Service) if the scraper returned it.

**Disagreement rows resolved:** Indirect — would have raised confidence on Active calls and potentially prevented the fast-path false Active on row 85 if the copyright year was old/absent.

**Specific code change:**

In `/Users/Julian/workspace/ivmf/code/ivmf-business-checker/business_checker/tools/scrape_website.py`, modify the `_scrape_direct` function. After extracting `text` via BeautifulSoup (currently line 222–224), add:

```python
# Extract footer copyright year as a high-value recency signal
copyright_year = None
try:
    # Search for copyright year patterns in full HTML before stripping
    copyright_match = re.search(
        r'[©&copy;Cc]\s*(?:opyright\s+)?(\d{4})',
        resp.text,
        re.IGNORECASE
    )
    if copyright_match:
        copyright_year = int(copyright_match.group(1))
        # Validate plausibility — ignore years outside 2000–2030
        if not (2000 <= copyright_year <= 2030):
            copyright_year = None
except Exception:
    copyright_year = None
```

Then modify `_classify_text` to accept and pass through `copyright_year`, and modify `scrape_website` to include `copyright_year` in its returned dict.

Modify `scrape_section` construction in `check_business.py` (around line 225–232) to include copyright year when available:

```python
if scraped["success"] and not scraped["is_slop"] and scraped["text"]:
    copyright_note = ""
    if scraped.get("copyright_year"):
        copyright_note = f"\nFooter copyright year detected: {scraped['copyright_year']}."
    scrape_section = (
        f"\nDIRECT WEBSITE CONTENT (retrieved from {website}):\n"
        f"---\n{scraped['text']}{copyright_note}\n---\n"
        "Use this content alongside your search to evaluate whether the site "
        "shows a real, currently operating business.\n"
    )
```

**Where it goes:**
- `scrape_website.py`: `_scrape_direct` function (around line 221), `_classify_text` signature and return dict, `scrape_website` return dict
- `check_business.py`: `scrape_section` construction block (around line 225–232)
- Note: would also need to apply to `_scrape_firecrawl` path for Firecrawl users — same copyright regex, applied to the markdown text before stripping

**Risk of regression:** Low for Active calls (more copyright signal = higher confidence on genuinely active sites). Moderate risk for cases where a stale-looking site has a recent copyright year injected by a CMS (WordPress and Shopify auto-update `©` years). This could prevent correct Likely Closed calls on sites with automated copyright year updates and no real content changes. However, the SYSTEM_PROMPT already treats copyright year as one signal among many — a single recent copyright year alone is not sufficient for Active via Fast Path (it requires "substantive content"). The signal provides uplift, not override authority.

**Effort:** M (1–1.5 hours — code changes across two files, need to thread `copyright_year` through the dict chain, write tests)

**Confidence in fix working:** High for correctly-active sites (the year is accurate and informative). Medium for closure detection improvement — it requires the AI to act differently when the copyright year is old or absent, which depends on how it weighs the absence of the year vs. the presence of other signals.

---

### F9: Basket and Beads Kenya — Scraper Slop Detection Investigation

**Failure mode addressed:** Scraper-error — scraper returned a parking/coming-soon page for a live Shopify store (row 685). AI used this wrong signal to score Uncertain 55%.

**Disagreement rows resolved:** 685 (Basket and Beads Kenya)

**Root cause analysis:** Three hypotheses:
1. **Transient cache hit:** Shopify or a CDN edge served a temporary placeholder to the scraper's `requests.get()` call (Cloudflare bot challenge, maintenance page, etc.). This is a timing/infrastructure issue, not a code bug.
2. **Redirect to different URL:** The listed URL may redirect through a temporary landing page that looks like "coming soon" before the full Shopify store loads. The `_scrape_direct` function follows redirects (`allow_redirects=True`) but only captures the final redirect content. If the chain has a step that looks like "coming soon," it would match `_SLOP_MARKERS`.
3. **Firecrawl returned a stale snapshot:** If `FIRECRAWL_API_KEY` is set, Firecrawl may have a cached version of the site from a period when it was in a pre-launch state.

**Specific code change:**

Add a verification step in `_scrape_direct` to detect Shopify-powered sites that the slop detector might misclassify:

In `scrape_website.py`, modify `_classify_text` to add a Shopify-specific exemption:

```python
def _classify_text(text: str, scrape_cost: float) -> dict:
    if len(text) < 40:
        return {
            "success": True, "is_slop": True, "text": "",
            "note": "Page has almost no text content — likely a parking or placeholder page.",
            "scrape_cost": scrape_cost,
        }

    text_lower = text.lower()

    # Shopify and known e-commerce platform markers — if these are present
    # alongside "coming soon", the site may be Shopify-gated, not truly dead.
    # Do not classify as slop if strong e-commerce platform markers are present.
    ecommerce_markers = ["powered by shopify", "shopify.com", "add to cart", "checkout"]
    has_ecommerce = any(m in text_lower for m in ecommerce_markers)

    for marker in _SLOP_MARKERS:
        if marker in text_lower:
            if has_ecommerce and marker == "coming soon":
                # "Coming soon" on a Shopify site may be a password-protected
                # storefront, not a dead site. Pass content through for AI to evaluate.
                return {
                    "success": True, "is_slop": False, "text": text[:MAX_TEXT],
                    "note": "Possible Shopify password-protected page — not classified as slop.",
                    "scrape_cost": scrape_cost,
                }
            return {
                "success": True, "is_slop": True, "text": "",
                "note": f"Parking/placeholder page detected (found: '{marker}').",
                "scrape_cost": scrape_cost,
            }
    ...
```

Also add a diagnostic: when `scrape_domain_dead=True` and the AI's verdict is Uncertain (not Likely Closed), flag the result for human review — this is the signature pattern of a scraper false positive.

**Where it goes:** `scrape_website.py`, `_classify_text` function (lines 132–163)

**Risk of regression:** Moderate. The Shopify exemption for "coming soon" could cause false non-slop classification for genuinely launched-but-dead Shopify stores that happen to have "powered by shopify" in cached footer content alongside "coming soon" in the main content. To mitigate: scope the exemption narrowly — only bypass slop if BOTH `powered by shopify` AND `add to cart` (or `checkout`) are present, not just one marker.

**Effort:** S (30–45 minutes)

**Confidence in fix working:** Medium. If the root cause is hypothesis 1 (transient CDN cache), no code change will help — it's infrastructure noise. If hypothesis 2 or 3, the Shopify exemption reduces false positives. Recommend first re-running row 685 to see if the scraper error is reproducible. If it's not reproducible, deprioritize this fix.

---

## Do Not Pursue

### DN1: Owner LinkedIn employment end-date lookup

**Rationale:** This requires searching by owner name (e.g., "Andrew Weaver Force Multiplier Talent") to find LinkedIn and then parsing employment end dates. Perplexity may not reliably surface this, and even if it does, the signal is already captured by the existing CHANNEL 5 (owner/founder search) and CHANNEL 6. Adding a specific "check employment end dates" rule adds complexity without reliable returns. Julian uses this technique manually but it's not automatable at scale with Perplexity's current capabilities. The cases it would address (rows 410, 91, 578) are all already correctly classified as Likely Closed or Uncertain. No accuracy gain expected.

### DN2: Self-critique / second-pass loop for low-confidence results

**Rationale:** A second Perplexity call for confidence < 60 rows doubles cost for those rows (~22% of the dataset based on calibration data) and introduces latency. More importantly, the low-confidence rows are primarily Pattern-B cases that will be fixed by F1 (the decisiveness prompt change) — the AI won't need a second chance if the first prompt is correct. If F1 works, the 50–69 confidence band (currently 0–36% accuracy) should move to Likely Closed correctly. If F1 fails, a second call is still unlikely to help because the evidence gap is in what Perplexity can find, not in how many chances the AI gets to analyze it. Not worth the cost.

### DN3: Row 314 (A Guide to Improvised Weaponry) — celebrity portfolio site handling

**Rationale:** This is a confirmed dataset quality issue. The record is a veteran TV personality's portfolio site (Terry Schappert), not an operating business. Adding a prompt rule for "portfolio sites that also sell merchandise" would be so niche that it would likely cause regressions on legitimate businesses with similar thin-content profiles. Julian acknowledges this is a special case not previously encountered. The correct fix is dataset filtering upstream — flag records where the "business" is an individual author's book or a personal brand site rather than a company offering services/products.

### DN4: Visual quality assessment

**Rationale:** The AI has no vision capability and cannot assess "colorful, lively" website quality as Julian does. This is a structural limitation. Adding language to the prompt about "visually active" websites would be meaningless. The signal Julian uses (visual quality) is a proxy for investment level — which is partially captured by other signals the AI CAN assess (modern Shopify/WooCommerce e-commerce, high product count, dated content). Do not pursue.

### DN5: YouTube promotional content date verification

**Rationale:** Row 349 (Devil Dog Brew) was correctly classified as Active. Julian's YouTube check was confirmatory, not decisive. The AI already correctly scored it 95. Perplexity does index YouTube sometimes but not reliably. Adding a mandatory YouTube check to CHANNEL 7 would add noise without meaningful accuracy gain. The one case where this mattered was already correctly resolved.

---

## Uncertainty / Unknowns — Verify Before Shipping

### U1: Is row 685 (Basket and Beads Kenya) scraper error reproducible?
Run `scrape_website("https://basketsandbeadskenya.com")` (or the exact URL from the dataset) in isolation and check if it returns parking-page content or the actual Shopify store. If the current run returns the real site, the error was transient and F9 is lower priority. If it reproducibly returns slop, F9 is essential.

### U2: Does F1 (Pattern-B decisiveness) cause regressions on borderline Uncertain rows?
The 70–79 confidence band currently has 84% agreement on Likely Closed. Row 583 (Achieve New Heights) is the key regression risk: AI said Likely Closed (75) but Julian said Uncertain because of missed LinkedIn/Facebook posts. F1 should not make this worse (the AI already committed to Likely Closed there), but the new "must cite 2024+ social post to use Uncertain" rule could push other genuinely-Uncertain rows (that haven't had social found yet) incorrectly to Likely Closed. Need to re-run the full 60-row set, not just the 18 disagreements, to catch this.

### U3: Does the post-processing override fix (F4 Part B) change any currently-correct results?
The current override at line 333 fires on all NWP+dead-domain cases and converts them to Likely Closed. Rows in the eval set where `scrape_domain_dead=True` and the AI said NWP: only rows 125 and 88 are known from the labeler analysis. But there may be others in the full 60-row set where the current override was doing the right thing (converting a wrong NWP to a correct Likely Closed). The new logic only preserves the upgrade when `citations` is non-empty — verify this matches observed behavior on those rows.

### U4: Does F6 (confidence cap for Active without dated content) harm correctly-Active rows with no footer dates?
Row 94 (Mobile Cigar Lounge) has no footer copyright year (Julian noted this explicitly). It was correctly scored Active at 95. The proposed cap ("never assign Active 90+ without dated content or verified social recency") would need verification: did the AI cite Instagram recency for row 94? If yes, the cap does not fire. If the AI cited only website content, the cap would lower confidence to 79 — still Active, just lower confidence. Not a label regression, but a confidence regression worth tracking.

### U5: Perplexity search retry behavior — does the AI actually execute multi-step retries?
F7 (suffix stripping) instructs the AI to retry searches with modified queries. Perplexity Sonar's architecture may not support discrete multi-step query retries within a single call — it runs a search and synthesizes, not a back-and-forth search loop. If the AI cannot actually perform a retry with a different query string, F7 has no effect. Validate by running a known missed-channel case (row 583) and checking the evidence field for signs the AI tried both "Achieve New Heights LLC" and "Achieve New Heights" as separate search attempts.

### U6: Does the Etsy /people/ rule (F3) surface correct /shop/ results via Perplexity search?
The fix instructs the AI to "replace 'people' with 'shop' in the path" — but Perplexity searches by query, it doesn't directly fetch URLs. Whether this instruction translates to Perplexity actually fetching `etsy.com/shop/PrincessLeahDesigns` depends on whether Perplexity's search engine returns that URL. A safer implementation might be to add a post-processing Python step that rewrites Etsy /people/ URLs in the dataset to /shop/ URLs before passing them to the scraper. This would be a deterministic fix rather than a prompt-based one.

---

## Implementation Order Recommendation

Run in this sequence to minimize risk and maximize signal from each re-run:

1. **F3 + F2** (XS effort, high confidence, no regression risk) — apply first, re-run only rows 193 and 271
2. **F1** (S effort, highest impact) — apply, re-run all 18 disagreement rows
3. **F4 Part B** (post-processing code change — deterministic, testable) — apply, re-run full 60-row set
4. **F4 Part A + F5** (prompt additions, medium risk) — apply together, re-run full 60-row set
5. **F6** (higher risk, tighten confidence rubric) — apply after F1–F5 are validated
6. **F7** (lowest confidence, Perplexity-dependent) — apply last, verify with known missed-channel rows
7. **F8** (M effort, infrastructure change) — separate engineering sprint
8. **F9** (pending U1 verification) — only if row 685 error is reproducible

**Estimated total cost to re-run:** ~$0.20 for the 18 disagreement rows, ~$0.50 for the full 60-row set. Run the 18-row targeted re-run first to validate F1 before committing to the full re-run.
