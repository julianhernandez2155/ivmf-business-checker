# Phase 7 — Iteration 1 Plan

**Date:** 2026-05-05
**Backup tag:** `phase-7-pre-iteration-1` (pushed to GitHub)
**Approval:** Julian approved single-wave application of F1–F5 with the "entity existence vs. operational signal" nuance on F1.

## Objectives

1. Apply 5 surgical fixes to `tools/check_business.py` to address the 14 prompt-fixable disagreements identified in `docs/phase-7-disagreement-analysis.md`.
2. Re-run the full 60-row eval sample with the updated AI to measure both improvement and regressions.
3. Run Codex review #3 as a second-opinion gate before declaring iteration complete.

## What's in scope

- **F1 — Pattern-B Decisiveness** (with entity-existence nuance)
- **F2 — Hijacked-Domain Mandatory Social Check**
- **F3 — Etsy /people/ vs /shop/ URL Guard**
- **F4 — NWP Boundary + Post-processing Override Fix** (prompt + Python code)
- **F5 — Marketplace Redirect + Single-Channel Facebook**

## What's deferred (with rationale)

- **F6 — Active confidence cap without dated content.** Defer. Risks regression on legitimately-active rows that lack footer dates (e.g., row 94 Mobile Cigar Lounge). Revisit in iteration 2 if F1 doesn't move the false-Active rate.
- **F7 — LLC/Inc suffix stripping on social retries.** Defer. Uncertain whether Perplexity Sonar actually executes discrete query retries within a single call. Implementation fidelity unknown.
- **F8 — Footer copyright year extraction in scraper.** Defer. F1's prompt edit instructs the AI to look for "© [year]" patterns in scraped text — captures 80% of the value with 0% of the code-change risk.
- **F9 — Scraper Shopify exemption.** Conditional defer. Will only apply if row 685 reproduces the parking-page misclassification.

## Order of execution

1. **Pre-flight** — pytest baseline (confirm 111 tests pass before any change)
2. **Prompt edits** — F1, F2, F3, F5 to `tools/check_business.py` SYSTEM_PROMPT
3. **Code edits** — F4 Part A (prompt) + F4 Part B (Python override at line 332)
4. **Test gate** — `python3 -m pytest -q` must pass 111/111 before re-run
5. **Standalone smoke** — `python3 -m tools.check_business` against Target → confirm Active 100%
6. **Disagreement subset re-run** — re-run only the 18 disagreement rows (~$0.13, 2 min) to validate fixes work directionally before spending on full re-run
7. **Triage subset results** — if subset shows ≥10/18 fixes resolved cleanly, proceed; if <10, stop and re-investigate
8. **Full 60-row re-run** — `python3 run_checker.py --input ../data/BMOSG_All_Businesses.xlsx --workers 3 --limit 60` BUT first delete the existing checkpoint to force fresh runs (otherwise cache returns the old verdicts)
9. **Score against existing labels** — `python3 -m eval.score --labeled <updated-CSV> --out-dir eval/reports/bmosg_v1_iteration_1`
10. **Generate comparison report** — produces `docs/phase-7-iteration-1-results.md` with row-by-row before/after, regressions identified, agreement delta
11. **Codex review #3** — static-review prompt, save output to `docs/codex-review-3-iteration-1.md`
12. **Triage Codex feedback** — apply only if it catches a real issue I missed
13. **Tag** — `phase-7-iteration-1-complete`, push to GitHub

## Detailed change spec

### F1 — Pattern-B Decisiveness Overhaul

**File:** `business_checker/tools/check_business.py`
**Replaces:** Lines 143–145 (current "STALE RECORDS WITH NO CORROBORATION" block)
**With:**

```
PATTERN B — WHEN TO COMMIT TO "Likely Closed" (not "Uncertain"):

"Uncertain" requires at least ONE positive recency signal: a social post, marketplace listing, current Google Business Profile activity, or press coverage from 2024 or later that is SPECIFICALLY about this business. If you cannot cite one, do not use Uncertain — commit to a more decisive verdict.

When you have ALL of the following, commit to "Likely Closed" at 65–80% confidence:
  (a) The website is non-functional: 404, DNS failure, domain-for-sale parking page, empty Wix/Weebly/Square/Squarespace placeholder with no business-specific content, or "coming soon / opening soon" page with no evidence the site ever launched.
  (b) No Google Business Profile showing as open with reviews from 2024 or later, or Maps shows "Permanently closed".
  (c) No Facebook or Instagram post from 2024 or later specifically from this business.
  (d) No current marketplace storefront with in-stock products (for product businesses).
  (e) The only results are: state incorporation records, old directory listings (ZoomInfo, Manta, FMCSA, Infogroup, OpenFOS, BBB without recent reviews), or press/media articles from before 2023.

If (a)–(e) all apply → "Likely Closed" at 65–75%. This is Pattern B. Do NOT hedge to "Uncertain".

ENTITY EXISTENCE vs. OPERATIONAL STATUS — important distinction:
- Directory listings (Manta, ZoomInfo, OpenFOS, Infogroup), state LLC/incorporation records, FMCSA DOT numbers, SBA certifications, and similar registry entries CONFIRM that the business EXISTED as a legal entity. They are valuable evidence that this is a real business (not a name collision or ghost record), and they remain useful as supporting evidence.
- HOWEVER: these signals do NOT, by themselves, confirm CURRENT OPERATION. FMCSA DOT numbers persist for defunct carriers indefinitely. State LLC records stay registered for years after closure. SBA certifications expire on a schedule, not based on activity. Auto-scraped directory listings (Manta, ZoomInfo) capture historical state.
- Use them this way: when paired with at least one recency signal from another channel (2024+ social post, current marketplace listing, recent press, owner actively promoting), they strengthen an Active or Uncertain verdict. When alone, with no corroborating recency from any other channel, they are NOT sufficient to hedge to Uncertain over Likely Closed.
- Rule of thumb: directory + regulatory listings answer "did this exist?" — they do not answer "is this operating today?" For the latter, find recency from social, maps, marketplace, or press.

"Coming soon" / "Opening soon" sites: If the site has been in "coming soon" status for 12+ months with no launch evidence and no active social presence, and the business appeared in a directory 12+ months ago, it almost certainly never launched. Classify as "Likely Closed".

Footer copyright year: When scraped page text contains "© [year]" or "Copyright [year]" near the footer, treat the year as a recency signal:
- Year is current year (2025–2026) AND substantive page content exists → supports Active.
- Year is 2023 or older AND no other recent signals → supports Likely Closed.
- Year is missing entirely → neutral; rely on other signals.
```

**Risk:** Low-moderate. Could push borderline rows where you found a 2023 social post (which doesn't meet "2024 or later") incorrectly into Likely Closed. Mitigated by the full 60-row re-run catching regressions.

---

### F2 — Hijacked-Domain Mandatory Social Check

**File:** `business_checker/tools/check_business.py`
**Replaces:** Lines 139–141 (current "SQUATTED / HIJACKED DOMAINS" section)
**With:**

```
SQUATTED / HIJACKED DOMAINS:
- If a domain now hosts gambling, adult content, spam, generic blog content, or a parking page clearly unrelated to the original business — treat it as a dead domain. It counts as one closure signal.
- MANDATORY: When you detect a hijacked or squatted domain, you MUST check Instagram and Facebook before issuing any verdict. This is non-negotiable. Businesses frequently post closure announcements on social media when their domain lapses. Look for pinned posts saying "we are closed", "permanently closed", "our store is closed", "thank you for X years", or similar.
- If you find a social closure announcement → "Likely Closed" at 85–95% confidence (this is the strongest possible closure signal short of a death certificate).
- Squatted domain + social channels checked + no posts since 2023 + no Google Maps listing + no other channel hits = "Likely Closed" at 70–80%. Do NOT call this "Uncertain".
- Squatted domain + active 2024+ social posts = investigate further (may be Uncertain if status unclear, or Active if business is clearly operating through social alone — see "single-channel businesses" below).
```

**Risk:** Very low. Adds a mandatory step, doesn't change verdict logic.

---

### F3 — Etsy /people/ vs /shop/ URL Guard

**File:** `business_checker/tools/check_business.py`
**Adds at:** End of CHANNEL 7 — MARKETPLACES section (after line 119)
**Insert text:**

```

MARKETPLACE URL PATTERNS — know the difference between profile pages and storefronts:
  • etsy.com/shop/X → this IS a storefront. Valid evidence of business presence.
  • etsy.com/people/X → this is a USER PROFILE showing favorited items from OTHER sellers. NOT a storefront. Do not cite this as evidence of an active business.
  • etsy.com/market/X → this is a category/search results page. NOT a specific business's shop.
  • amazon.com/stores/X → brand storefront. Valid if products are in stock.
  • amazon.com/sp?seller=X or amazon.com/gp/aag/main?seller=X → seller profile page. Valid if reviews are recent.
  • amazon.com/profile/X → user profile, NOT a seller storefront.

When you encounter an Etsy /people/ URL: search Etsy directly for the business name to find their actual /shop/ URL. If no shop exists, treat the people-page URL as missing evidence — do not score Active solely on a profile page.

When following a "Shop" link on a business website that redirects to a marketplace: the marketplace listing IS commerce evidence. Many veteran businesses use their website as a portfolio and the marketplace as the actual storefront. Follow the redirect.
```

**Risk:** Minimal. Purely structural URL distinctions. Cannot harm any currently-correct row that doesn't have an Etsy /people/ URL (none in the dataset).

---

### F4 — NWP Boundary Clarification + Post-processing Override Fix

#### Part A: Prompt edit

**File:** `business_checker/tools/check_business.py`
**Replaces:** Lines 150–154 (current "NO WEB PRESENCE — use it precisely" section)
**With:**

```
NO WEB PRESENCE — use it precisely:
- Use "No Web Presence" ONLY when: the domain is dead (or no website was listed) AND all 8 channels returned zero results specifically about this business — not even an old directory listing, not even a social profile, not even a press mention with this business name.
- "No Web Presence" is NOT the same as "Likely Closed". NWP means the business is unverifiable — there is simply nothing online to evaluate. The business may be closed, may operate offline, may never have had a presence.
- If ANY search returned a result specifically naming this business (old directory listing, dormant social profile, news mention, founder LinkedIn referencing the business), use "Likely Closed" (stale signals support closure) or "Uncertain" (some recent activity exists) instead.
- Generic placeholder pages (Wix, Weebly, Square "coming soon" templates with zero business-specific content, no products, no owner name, no contact info specific to this business) are NOT a web presence. If this is the only thing you found and search returns nothing for this business → "No Web Presence".
- A personal Whitepages or RocketReach profile for an INDIVIDUAL is NOT a business web presence.
- When in doubt between NWP and Likely Closed: if you can cite at least one result that specifically names this business, it is Likely Closed. If you cannot cite any result about this business specifically, it is NWP.
```

#### Part B: Python code change

**File:** `business_checker/tools/check_business.py`
**Replaces:** Lines 332–341 (the current post-processing override)
**With:**

```python
            evidence = parsed.evidence
            if status == "No Web Presence" and website:
                if scrape_domain_dead and scrape_gave_signal:
                    # Scraper confirmed dead domain AND Perplexity said NWP.
                    # Only upgrade to Likely Closed if the AI also found at
                    # least some search results (citations non-empty) — meaning
                    # the business appeared somewhere on the web. If Perplexity
                    # found nothing AND the domain is dead, NWP is the correct
                    # call. Don't override it.
                    if citations:
                        # AI found something via search but still said NWP.
                        # Likely a conservative call on a genuinely closed business.
                        status     = "Likely Closed"
                        confidence = max(confidence, 70)
                        evidence   = f"[Domain confirmed dead via direct check] {evidence}"
                    else:
                        # AI found nothing AND domain is dead → NWP is correct.
                        # Add a note for human review since the URL was on file.
                        evidence   = f"[Domain dead, no search results found — NWP confirmed] {evidence}"
                elif not scrape_gave_signal:
                    # No URL signal at all (URL present but scraper couldn't connect).
                    status     = "Uncertain"
                    confidence = max(confidence, 40)
                    evidence   = f"[URL on file but could not confirm content — flagged for review] {evidence}"
```

**Risk:** Moderate. The current override fires aggressively. The new logic preserves correct upgrades while preventing misfires on rows 125, 88. Need to verify on full 60-row re-run that no previously-correct override is broken.

---

### F5 — Marketplace Redirect + Single-Channel Facebook

**File:** `business_checker/tools/check_business.py`

#### Part A: FAST PATH addition

**Adds at:** End of "Qualifies as Active" bullet list (after line 65)
**Insert text:**

```
       • Product pages on the business's website redirect to an active Amazon listing, active Etsy /shop/ URL, or other marketplace with current stock — many veteran businesses use their website as a portfolio and the marketplace as the actual storefront. Follow the commerce link before judging.
       • The listed "website" URL is itself a Facebook, Instagram, or LinkedIn page (i.e., the URL contains facebook.com, instagram.com, or linkedin.com) — evaluate it as the PRIMARY channel, not a social-media supplement. If the most recent post or update is within 12 months and shows business activity, this is Active.
```

#### Part B: CHANNEL 3 (Facebook) addition

**Adds at:** End of CHANNEL 3 section (after line 96)
**Insert text:**

```
  • IMPORTANT: If the listed website URL in the dataset IS a Facebook page URL, evaluate that page as the primary evidence source, not as a social media supplement. The absence of a separate domain website is not a negative signal — this is a Facebook-native business.
  • When viewing a Facebook business page, check the "Posts" tab specifically for recent activity dates, not just whether the page exists. A page with no posts in 2 years is a different signal from a page with a post 4 days ago.
```

**Risk:** Low. Specific, observable behavior. Won't fire incorrectly on unrelated cases.

---

## Full re-run command

```bash
cd /Users/Julian/workspace/ivmf/code/ivmf-business-checker/business_checker

# 1. Verify standalone test
python3 -m tools.check_business

# 2. Run pytest
python3 -m pytest -q

# 3. Force fresh run (cache invalidation): use --no-cache flag
#    OR: temporarily move the cache DB out of the way
mv cache/results.db cache/results.db.iteration-0-backup

# 4. Run on the BMOSG file with the same input
python3 run_checker.py --input ../data/BMOSG_All_Businesses.xlsx --workers 3 2>&1 | tee Runs/iteration_1_run.log

# Estimated: 709 rows × $0.0073 ≈ $5.20 (fresh run, no cache hits since we
# moved the cache aside).

# Wait — actually we only need to re-run the 60 sample rows, not all 709.
# Better approach: targeted re-run script that hits only the 60 specific
# row_indices in the eval sample.
```

**Decision:** I'll write a small targeted re-run helper in `eval/rerun_sample.py` that reads the eval sample, looks up the 60 row_indices in the input xlsx, calls `check_business` on each with `cache=None`, and writes results to a new checkpoint format. Cost: 60 × $0.0073 ≈ $0.44. Time: ~3 min at 3 workers.

## Comparison methodology

After the re-run produces new predictions, I'll generate a side-by-side comparison report:

For each of the 60 rows:
- Original AI verdict (from `bmosg_v1_predictions_2026-04-30.csv`)
- New AI verdict (from iteration 1 re-run)
- Your label (from `bmosg_v1_eval_sample.csv`)
- Agreement-with-Julian: original vs. new
- Classification: improved / regressed / unchanged-correct / unchanged-wrong

Aggregate stats:
- Original agreement: 40/58 = 69.0%
- Iteration 1 agreement: ?/58 = ?%
- Resolved (was disagreement, now agrees): count
- Regressed (was correct, now disagrees): count
- Net delta: improvement count − regression count

If net delta > 0 and no class-specific catastrophic regression (e.g., all Active rows now Uncertain), iteration ships.

## Codex review #3

After all changes are in and the re-run is complete:

```bash
codex exec --skip-git-repo-check "STATIC REVIEW ONLY — do not attempt to execute any python or shell scripts to verify behavior. The repo at /Users/Julian/workspace/ivmf/code/ivmf-business-checker has Bash sandbox restrictions; running scripts will fail and waste time.

Read these files:
- business_checker/tools/check_business.py (the AI prompt — focus on lines 49-200, the SYSTEM_PROMPT, especially the new Pattern B section, hijacked domains section, NWP section, marketplace section)
- business_checker/tools/check_business.py post-processing block around lines 332-355
- docs/phase-7-iteration-1-plan.md (this plan)
- docs/phase-7-iteration-1-results.md (the comparison report from this iteration)

Then answer:
1. Did the prompt edits introduce any internal contradictions or rules that conflict with each other?
2. Does the new Pattern B section work correctly with the existing FAST PATH section, or does it create competing decision paths?
3. Does the F4 Part B Python change correctly preserve the existing 'scrape_domain_dead but no scrape_gave_signal' branch?
4. Are there any edge cases the prompt edits don't address but should?
5. Any wording in the prompt that's ambiguous and could lead to inconsistent AI behavior?
6. Pre-leadership-handoff sanity check: anything in this iteration that would embarrass the project under stakeholder scrutiny?

Be concise. Numbered responses, one paragraph each maximum. No code edits. No commands."
```

Save output to `docs/codex-review-3-iteration-1.md`.

## Verification gates (must pass before declaring complete)

- [ ] All 5 fixes applied to `tools/check_business.py`
- [ ] `pytest` passes 111/111
- [ ] Standalone `python3 -m tools.check_business` returns Active for Target with high confidence
- [ ] Targeted 60-row re-run completes without errors
- [ ] Comparison report shows net positive delta (more resolutions than regressions)
- [ ] No catastrophic class-specific regression (e.g., precision on Active dropping below 80%)
- [ ] Codex review #3 captured to `docs/codex-review-3-iteration-1.md`
- [ ] Codex review identifies no critical issues (P0 blockers)

## Tags and commits

Each major step gets its own commit:
1. `chore(eval): backup pre-iteration-1 state` (already done via tag)
2. `feat(prompt): apply F2/F3/F5 — additive marketplace + hijacked-domain rules`
3. `feat(prompt): apply F1 — Pattern B decisiveness with entity-existence nuance`
4. `feat(eval): apply F4 — NWP boundary + post-processing override fix`
5. `data(eval): iteration 1 re-run of 60-row sample`
6. `docs(eval): iteration 1 comparison report + Codex review #3`

Final tag: `phase-7-iteration-1-complete`

## Estimated time

- Plan + edits: ~30 min
- Re-run: ~5 min
- Comparison + report: ~30 min
- Codex review: ~10 min (with sandbox-safe prompt)
- Final triage + commits: ~20 min
- **Total: ~90–100 min of orchestrator time, plus API spend ~$0.50**
