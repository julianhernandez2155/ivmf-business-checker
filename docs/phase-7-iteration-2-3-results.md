# Phase 7 — Iterations 2 & 3 Results

**Date:** 2026-05-08
**Baseline:** 69.0% agreement (40/58 scoreable rows)

---

## Iteration Summary

| Iteration | Agreement | Delta | Resolved | Regressed | Net |
|-----------|-----------|-------|----------|-----------|-----|
| Baseline  | 69.0% | — | — | — | — |
| Iter 1 (F1–F5) | 62.1% | -6.9 pp | 5 | 9 | -4 |
| Iter 2 (F2–F5, no F1) | 60.3% | -8.6 pp | 4 | 9 | -5 |
| Iter 3 (F2–F5 + aggregator blacklist + Etsy stock check) | 55.2% | -13.8 pp | 2 | 10 | -8 |

**Current prompt state:** bdd6036 (F2/F3/F4/F5 only, no aggregator list, no Etsy stock check — same as iter 2)

---

## What Worked (Stable Across Iterations)

F2, F3, and F5 consistently resolved 3–4 rows without introducing regressions:

| Row | Business | Fix | Result |
|-----|----------|-----|--------|
| 271 | Princess Leah's Designs | F3 (Etsy /people/ guard) | Uncertain ✓ |
| 685 | Basket and Beads Kenya | F5 (website/social evaluation) | Active ✓ |
| 114 | Disgruntled Decks | F5 (marketplace redirect) | Active ✓ |
| 556 | Spicers Nicer Massage | F5 (Facebook-native business) | Active ✓ |

---

## Root Cause Analysis

### Why Every Iteration Regressed

The **Pattern B hesitancy** cluster (9 rows: 31, 163, 177, 286, 380, 193, 538, 470, 680) has been wrong in every iteration. These are cases where:
- Julian labeled **Likely Closed**
- AI consistently returns **Uncertain** or **Active**
- The evidence the AI finds: state directories, ZoomInfo, FMCSA, experience.com, RocketReach, Manta, CannabisShop-type aggregators

Every attempt to fix this via prompt engineering created a new class of regression:
- **F1** (Pattern B explicit conditions list): Made AI call Active on directory listings → 9 regressions
- **Aggregator blacklist** (Iter 3): Made AI discount all aggregator data → pushed Uncertain→Likely Closed in wrong cases (rows 97, 176, 451)
- **F4 NWP tightening**: Pushed some Uncertain rows into No Web Presence (rows 624, 388, 451)

### The Core Tension

The AI uses directory aggregators (ZoomInfo, Manta, experience.com, RocketReach, THCaNearby) as an Uncertain hedge signal: "I found SOMETHING, so I won't commit to Likely Closed." This is a reasonable default heuristic. The fix attempts broke this hedge in different directions:

- Tell the AI directories support Active → over-calls Active
- Tell the AI directories are worthless → over-calls Likely Closed  
- Tell the AI to be more decisive → breaks calibrated Uncertain calls it was getting right

---

## Prompt Engineering Limit Reached

After 3 iterations and ~$1.50 in eval costs, prompt-only approaches have not improved on baseline. The stable wrong rows (Pattern B hesitancy cluster) require a different approach.

### Three Paths Forward

**Option 1 — Post-processing override (code-side)**
Add a post-processing rule in `check_business.py` that converts Uncertain→Likely Closed when:
- Domain confirmed dead (`scrape_domain_dead=True`)
- Citations are only from a known aggregator list (can regex-match URLs)
- No social/maps/press citations present

Risk: This is the same logic that caused NWP→Likely Closed issues in F4. Needs careful scoping.

**Option 2 — Few-shot examples in the prompt**
Add 3–4 concrete before/after examples directly in the system prompt showing the Pattern B cases. Example-based learning is more robust than rule-based for this type of judgment call.
- Show: "Here is a Likely Closed case (stale directories + dead domain + no social)" with actual evidence strings
- Cost: ~100–200 tokens added to every call (~$0.05/run increase on 60-row evals)

**Option 3 — Accept the ceiling and ship**
The 9 Pattern B rows may represent genuine ambiguity. Julian labeled them Likely Closed; the AI calls them Uncertain. Both are defensible. A more conservative AI (Uncertain) catches fewer false closures at the cost of more follow-up work.

At 69% agreement, the system is already useful. The cost of additional iteration vs. the marginal gain is questionable.

---

## Recommendation

**Option 2 (few-shot examples) as next iteration.** Before running it:
1. Write 3 concrete examples drawn from the disagreement rows
2. Run a Codex review of the few-shot examples to check for unintended edge cases
3. Cost: one eval run (~$0.50)

**Current action:** Keep prompt at bdd6036 (F2/F3/F4/F5). Do not ship F1 or the aggregator blacklist.

---

## Calibration Note

Baseline calibration was excellent: 90-100% band = 90% accurate. After all iterations, the 90-100% band degraded to 66–67%. This is a signal that the prompt changes made the AI over-confident rather than better-calibrated. The few-shot approach may help restore this.
