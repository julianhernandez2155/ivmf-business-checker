# Phase 7 — Disagreement Analysis (Baseline Pass)

**Date:** 2026-05-04
**Eval baseline:** `eval/reports/bmosg_v1_baseline/report.md`
**Source dataset:** `eval/datasets/bmosg_v1_eval_sample.csv` (60 labeled rows, 58 scoreable)
**Headline:** **69.0% agreement (95% Wilson CI: 56.2%–79.4%)**

## Why the headline number dropped from preliminary 89%

The first 30 rows happened to be alphabetically-early Active businesses (mostly food/CPG with strong online presence). The back half hit harder cases — closures, ambiguous web presences, and edge cases. **This is exactly why we stratified by status** — without it, an alphabetic sample would have looked artificially good.

## What the data actually says

The dominant disagreement pattern is **AI-too-cautious, not AI-too-confident:**

| AI predicted | You labeled | Count | Pattern |
|---|---|---|---|
| Uncertain | Likely Closed | **9** | AI punts on cases where evidence supports closure |
| Uncertain | Active | 3 | AI punts on cases that are actually live |
| Active | Uncertain | 2 | AI mis-cites or over-trusts website content |
| Likely Closed | Active | 1 | AI missed an active social presence |
| Other patterns | various | 3 | Edge cases / labeler corrections |

**12 of 18 disagreements (67%) are the AI saying "Uncertain" when more confident calls were warranted.** This is one fixable failure mode driving most of the gap.

## Calibration is otherwise excellent

| AI confidence | n | Agreement |
|---|---|---|
| 90-100% | 20 | **90%** |
| 80-89% | 3 | 67% |
| 70-79% | 19 | 84% |
| 60-69% | 5 | 0% |
| 50-59% | 11 | 36% |
| <50% | 0 | — |

High-confidence predictions (90+%) are 90% accurate. Low-confidence predictions are unreliable — but the AI correctly *flagged* them as low-confidence. **The system knows when it's guessing.**

## Per-disagreement categorization

Each disagreement classified as: **Prompt-fixable**, **Scraper-fixable**, **Post-processing-fixable**, **Genuinely ambiguous**, or **Labeler-correctable**.

### Disagreement 1 — Princess Leahs Designs (AI: Active 95% / You: Uncertain)
- **Category:** PROMPT-FIXABLE (Etsy URL discrimination)
- **Root cause:** AI accepted `etsy.com/people/X` as evidence of an active shop. That URL pattern is a *user profile* (showing favorites), not a *storefront*. Real shop URLs are `etsy.com/shop/X`.
- **Fix:** Add a rule to the system prompt distinguishing marketplace profile URLs from shop URLs.
- **Caught by:** Julian clicking through and seeing the actual page content.

### Disagreement 2 — Reflections of Service (AI: Active 100% / You: Uncertain)
- **Category:** PROMPT-FIXABLE (lenient recency on contact-only sites)
- **Root cause:** AI treated "service business with contact info + service descriptions" as Active per Fast Path, even though there was no commerce path and last social was 2020.
- **Fix:** Tighten the Fast Path "service business" criterion to require *current commerce evidence* (functional booking, recent social, dated content), not just "describes services." Reinforces 12-month recency.
- **Caught by:** Julian noticed no order path, last FB post 6 years old.

### Disagreement 3 — Achieve New Heights, LLC (AI: Likely Closed 75% / You: Uncertain)
- **Category:** GENUINELY AMBIGUOUS / SCRAPER-MISSED-EVIDENCE
- **Root cause:** AI's search couldn't find the LinkedIn/Facebook activity. When Julian searched without the exact corporate suffix, recent social posts appeared.
- **Fix:** Hard to address — Perplexity's search did try the business name. The issue is corporate-suffix variants (`LLC`, `Inc`, etc.). A rule could say "if no results found, retry without suffix" — but this is a Perplexity-side limitation, not our prompt.
- **Verdict:** Document as known limitation. Add a soft rule to the prompt to "search both with and without LLC/Inc/Corp suffixes."

### Disagreement 4 — A Guide to Improvised Weaponry (AI: Likely Closed 85% / You: Active)
- **Category:** EDGE CASE — labeled item is a book, not a business
- **Root cause:** This dataset record is a *book by a veteran*, not a veteran-owned operating business. The website is the author's portfolio site selling the 2015 book.
- **Fix:** This is a **dataset quality issue**, not an AI issue. The IVMF dataset includes records that aren't really operational businesses. Note in leadership packet as a finding ("dataset hygiene gap — some records are individual products/books rather than businesses").
- **Verdict:** Labeler is right to flag, AI is also defensible. Neither side wrong. Filter these out in production deployment.

### Disagreement 5 — Emotion On Walls (AI: Likely Closed 75% / You: No Web Presence)
- **Category:** PROMPT-FIXABLE (NWP threshold)
- **Root cause:** AI defaulted to Likely Closed Pattern B (dead domain + no other signals). Labeler correctly noted that "no other signals" means *No Web Presence*, not Likely Closed.
- **Fix:** Tighten the prompt to distinguish: "dead domain + no other signals + business name returns nothing in search" → No Web Presence. "Dead domain + business name returns SOMETHING somewhere (even old)" → Likely Closed.
- **Note:** The post-processing override at `check_business.py:331` already converts NWP→Likely Closed when `scrape_domain_dead=True`. **This override is too aggressive** — it should only fire when the AI's NWP decision was based on actual NWP signals, not when it would have correctly been NWP.

### Disagreement 6 — Basket and Beads Kenya (AI: Uncertain 55% / You: Active)
- **Category:** SCRAPER-FIXABLE (false parking-page detection)
- **Root cause:** AI's prompt was told the site was a "parking page / coming soon" — but Julian saw an active Shopify store with cart, products, copyright 2026. Either Firecrawl returned a stale snapshot OR the site was briefly down when scraped.
- **Fix:** Investigate scraper behavior on this specific URL. If reproducible, add to known-flaky list. If transient, accept as scraper noise.

### Disagreement 7 — King's Coffee (AI: Uncertain 55% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (decision rule on stale-but-found pattern)
- **Root cause:** AI found the business in directories with no post-2021 activity, found dead domain. Per labeler's protocol (which now matches the AI's STALE RECORDS rule), this is Likely Closed Pattern B. AI failed to apply its own rule.
- **Fix:** Strengthen the prompt's "STALE RECORDS WITH NO CORROBORATION" section. Make it more decisive: when only stale signals + dead domain found, default to Likely Closed at 65-75% confidence rather than punting to Uncertain.

### Disagreement 8 — TTG Properties (AI: Uncertain 55% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (empty-website-builder rule)
- **Root cause:** AI noted Wix template with no specifics, no contact, no current activity. The prompt says "empty Wix templates = treat as dead domain" but the AI still defaulted to Uncertain.
- **Fix:** Same as #7 — strengthen Pattern B decisiveness. "Empty Wix/Weebly/Square + no other signals = Likely Closed, not Uncertain."

### Disagreement 9 — Alpha Outpost (AI: Uncertain 65% / You: Likely Closed)
- **Category:** PROMPT/SCRAPER-FIXABLE (didn't follow up on Instagram)
- **Root cause:** AI noted spam-hijacked domain + corroborating retailer evidence + needed to check social. The Instagram explicitly said "Our store is permanently closed!" but AI didn't reach that signal. **Most damning case** — there was a clear closure announcement that the AI missed.
- **Fix:** Reinforce in the prompt that hijacked-domain cases MUST check social media before deciding. Currently the prompt says this softly; make it mandatory: "Hijacked/squatted domain → you MUST check Facebook + Instagram before defaulting to Uncertain or Likely Closed."

### Disagreement 10 — Dashfire Beards (AI: Uncertain 55% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (decisiveness on Pattern B)
- **Root cause:** Same as #7 and #8. AI found parking page + only one stale directory entry from before 2022. Per Pattern B rules, that's Likely Closed.
- **Fix:** Same prompt change as #7.

### Disagreement 11 — Sword & Plough (AI: Uncertain 65% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (decisiveness on Pattern B)
- **Root cause:** Dead site + multi-year-old press + last FB post 2022 + no current channel. Pattern B applies. AI hedged.
- **Fix:** Same prompt change as #7.

### Disagreement 12 — Bundook (AI: Uncertain 55% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (decisiveness on "Coming Soon" sites)
- **Root cause:** "Opening soon" page + listed in IVMF dataset 2 years ago + nothing else found = business that never launched. Pattern B applies. AI hedged.
- **Fix:** Strengthen prompt: "Opening soon" / "Coming soon" + no launch evidence over 12+ months + no other signals = Likely Closed.

### Disagreement 13 — Disgruntled Decks (AI: Uncertain 50% / You: Active)
- **Category:** PROMPT-FIXABLE (Amazon-redirect handling)
- **Root cause:** Site has product pages but they redirect to Amazon. AI noted "no e-commerce, no pricing." Labeler clicked through and found active Amazon listings.
- **Fix:** Add to the prompt: "If product links on the website redirect to a marketplace (Amazon/Etsy/Faire), treat the marketplace listing as commerce evidence. Many veteran businesses use the website as a portfolio and the marketplace as the storefront."

### Disagreement 14 — Peachy Keen Perfume (AI: Uncertain 65% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (decisiveness)
- **Root cause:** "Coming soon" parking page + Wix backup site with no dates + last social 2022. Pattern B. AI hedged.
- **Fix:** Same as #7.

### Disagreement 15 — A Simple Organizing & Moving Company (AI: Uncertain 55% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (decisiveness)
- **Root cause:** Parking page + FMCSA carrier profile (active DOT# but no recent activity confirmation) + last social 2 years old. Pattern B applies.
- **Fix:** Same as #7.

### Disagreement 16 — Spicers Nicer Massage Therapy (AI: Uncertain 60% / You: Active)
- **Category:** PROMPT-FIXABLE (single-channel mobile/service businesses)
- **Root cause:** The "website" listed was actually a Facebook page. AI penalized for "no recent dates" but the FB page had a post 4 days before the run. AI didn't read recent post dates correctly.
- **Fix:** Reinforce the existing "single-channel mobile/service businesses" override in the prompt. When the listed website IS a social media URL, evaluate it as the primary channel, not as a missing website. If recent activity (within 12 months) is present on that single channel, label Active.

### Disagreement 17 — SerenaTea,LLC (AI: Uncertain 75% / You: No Web Presence)
- **Category:** SAME AS #5 (NWP misclassification)
- **Root cause:** Wix placeholder + zero specific results = No Web Presence per labeler. AI defaulted to Uncertain.
- **Fix:** Same as #5 — add explicit NWP rule for empty-builder + no-search-results.

### Disagreement 18 — Spectra Cargo & Logistics (AI: Uncertain 65% / You: Likely Closed)
- **Category:** PROMPT-FIXABLE (decisiveness, "for sale" parking pages)
- **Root cause:** Domain explicitly "for sale" parking page + ZoomInfo/Indeed records pre-2022 + no recent activity. Pattern B applies.
- **Fix:** Add to prompt: "Domain explicitly listed for sale by the registrar = strong closure signal, treat as dead domain in Pattern B analysis."

## Summary of categorization

| Category | Count | Examples |
|---|---|---|
| **PROMPT-FIXABLE: AI hedges to Uncertain when Pattern B applies** | 9 | #7,8,10,11,14,15,18 + relevant subset of #2,12 |
| **PROMPT-FIXABLE: NWP not separated from Likely Closed Pattern B** | 2 | #5, #17 |
| **PROMPT-FIXABLE: Marketplace/redirect/single-channel handling** | 3 | #1, #13, #16 |
| **PROMPT-FIXABLE: Lenient recency / single-signal Active** | 1 | #2 |
| **PROMPT-FIXABLE: Hijacked-domain enforcement** | 1 | #9 |
| **SCRAPER-INDUCED** | 1 | #6 |
| **GENUINELY AMBIGUOUS / search limitation** | 1 | #3 |
| **DATASET HYGIENE** | 1 | #4 |

**14 of 18 disagreements are prompt-fixable. One scraper issue. One genuine ambiguity. One dataset issue.**

## Proposed prompt edits (Iteration 1)

Three concrete changes to `tools/check_business.py` SYSTEM_PROMPT:

### Edit A: Pattern B decisiveness (addresses 9 disagreements)

Add a new section above CRITICAL RULES:

```
PATTERN B DECISIVENESS — when to commit to "Likely Closed" instead of "Uncertain":

When you have ALL of:
  - A dead/parking/squatted/empty-builder website (any of: 404, DNS error, "for sale", parking page, empty Wix/Weebly/Square template)
  - No active Google Business Profile or Yelp listing with reviews from 2024 or later
  - No active Facebook/Instagram/LinkedIn posts from 2024 or later
  - No marketplace storefront with current stock for product businesses
  - Only static directory listings (state incorporation, ZoomInfo, FMCSA, Manta, etc.) with no activity dates after 2021

→ commit to "Likely Closed" at 70-80% confidence. Do NOT hedge to "Uncertain" — the absence of recent activity across all channels IS the signal.

Use "Uncertain" only when you have at least one POSITIVE signal of activity (a 2024+ social post, a current marketplace listing, recent press) but it's not enough to confirm Active.
```

### Edit B: Marketplace and single-channel handling (addresses 3 disagreements)

Add to FAST PATH:

```
MARKETPLACE-NATIVE BUSINESSES — additional Active criteria:

  • If the website's product pages link out to Amazon, Etsy, or Faire and those marketplace pages show current stock or recent reviews → Active.
  • If the listed "website" is itself a Facebook/Instagram/LinkedIn URL (not a domain), evaluate that page directly. If the most recent post is within 12 months and shows business activity, this is Active.
  • If the marketplace URL is a USER PROFILE (etsy.com/people/X, amazon.com/profile/X) rather than a SHOP URL (etsy.com/shop/X, amazon.com/seller/X), do NOT treat it as a storefront. Click through to find the actual shop URL or treat as missing evidence.
```

### Edit C: NWP boundary clarification (addresses 2 disagreements)

Update the existing "NO WEB PRESENCE" section:

```
NO WEB PRESENCE — strict boundary with Likely Closed:

  • "No Web Presence" applies when ALL searches return zero results specifically about this business: name + location returns nothing, name alone returns only unrelated namesakes, no directory listings exist.
  • If you find ANY directory listing, social profile (even inactive), or news mention specifically about THIS business, it is NOT No Web Presence — it's "Likely Closed" (if no recent activity) or "Uncertain" (if recent but ambiguous).
  • When the only signal is a dead domain + no search results matching the business name → No Web Presence.
  • When the only signal is a dead domain + at least one stale directory listing matching the business → Likely Closed Pattern B.
```

## Expected impact

If these edits resolve 14 of 18 disagreements (the prompt-fixable ones), the new agreement rate would be:

- 60 total rows
- 2 excluded (UTD)
- 58 scoreable
- Currently 40 agree, 18 disagree
- After fixes: 40 + 14 = 54 agree, 4 disagree
- New agreement rate: **54/58 = 93.1%**

That gets us above the 85% leadership threshold with margin to spare. Realistic expectation: **2-3 disagreements will resist the fix or new ones will appear**, so target ~88-92% post-iteration.

## What to do next

1. **Apply edits A, B, C** to `tools/check_business.py` SYSTEM_PROMPT
2. **Re-run only the 18 disagreement rows** (cheap — ~$0.13)
3. **Re-score** against the same human labels
4. **Verify** agreement improves and **check for regressions** — did the edit hurt any previously-correct rows? Need to also re-run a sample of correct rows to detect this.
5. If improvement holds, commit and proceed to Phase 8 leadership packet.

Estimated effort: 2-3 hours total for prompt edits + re-runs + analysis.
