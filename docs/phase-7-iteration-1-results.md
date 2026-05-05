# Phase 7 — Iteration 1 Results

**Date:** 2026-05-05
**Outcome:** ❌ **Iteration regressed. Net delta: -4 (resolved 5, regressed 9).**
**Headline:** 69.0% → **62.1%** (-6.9 pp)
**Wilson 95% CI:** 49.0% – 73.5% (n=58)
**Status:** Do NOT ship. Revert or fix forward.

## What happened

The 5 fixes (F1–F5) were applied as planned. The full 60-row re-run completed in ~2 minutes for $0.53. **The result was net-negative.** Specifically:

| Class | Count | Notes |
|---|---|---|
| Resolved (was wrong → now right) | 5 | F2 + F3 + F5 worked as designed |
| Regressed (was right → now wrong) | 9 | F1's "entity existence" framing backfired |
| Unchanged (correct in both) | 31 | |
| Unchanged (wrong in both) | 13 | F1 didn't help on Pattern B cases either |

## Diagnosis: F1 backfired in two specific ways

### Failure mode 1: AI over-corrected toward Active

The new prompt told the AI: "Directory listings (Manta, ZoomInfo, OpenFOS, etc.) are valuable supporting evidence when paired with recency from another channel."

The AI interpreted this much more permissively than intended. **It is now treating ANY directory listing + ANY website as enough to support Active**, even when the website is dead or stale.

Concrete regressions:
- **Row 535 (Overton's Grading):** `Likely Closed 85% ✓ → Active 95% ✗`. AI cited an `experience.com` directory listing with phone/hours as evidence of current operation.
- **Row 413 (Granted Advocacy Partners):** `Likely Closed 85% ✓ → Active 95% ✗`. AI cited LinkedIn-style company page with "Lisa Francis as current CEO" — but the website returns 404.
- **Row 31 (King's Coffee):** `Uncertain 55% → Active 95% ✗ (you said Likely Closed)`. AI now confidently active.
- **Row 163 (Dashfire Beards):** `Uncertain 55% → Active 92% ✗ (you said Likely Closed)`.
- **Row 286 (Sword & Plough):** `Uncertain 65% → Active 95% ✗`.
- **Row 680 (Bundook):** `Uncertain 55% → Active 95% ✗`.
- **Row 177 (Peachy Keen Perfume):** `Uncertain 65% → Active 92% ✗`.
- **Row 624 (Casa Los Juanes):** `Uncertain 55% ✓ → Active 88% ✗`. AI now treats Airbnb listings as Active businesses.
- **Row 451 (Secretariat Strategie):** `Uncertain 75% ✓ → Active 85% ✗`.
- **Row 602 (Griggsgear.com):** `Uncertain 72% ✓ → Active 95% ✗`.
- **Row 111 (CRSpices):** `Uncertain 72% ✓ → Active 92% ✗`.

### Failure mode 2: Pattern B fires on the wrong cases

The new "Pattern B" rule was designed to push borderline cases toward Likely Closed when evidence supports it. Instead, it's firing on cases that should stay Uncertain:

- **Row 97 (Tripoli Gift Company):** `Uncertain 50% ✓ → Likely Closed 75% ✗`. You labeled Uncertain because the founder rebranded; AI now confidently Likely Closed.
- **Row 176 (Norwood Natural's CBD):** `Uncertain 55% ✓ → Likely Closed 72% ✗`. You noted "Last update on their facebook was Feb 2025... google maps says their store is open" — there ARE positive signals.
- **Row 388 (Business Served):** `Uncertain 55% ✓ → No Web Presence 85% ✗`. AI escalated from Uncertain to NWP, ignoring that you found enough to call Uncertain.

## Calibration also degraded

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc | Delta |
|---|---|---|---|---|---|
| 50-59 | 11 | 36% | 0 | — | (band emptied) |
| 60-69 | 5 | 0% | 2 | 0% | flat |
| 70-79 | 19 | 84% | 13 | 54% | **-30 pp** |
| 80-89 | 3 | 67% | 11 | 73% | +6 pp |
| 90-100 | 20 | 90% | 32 | 66% | **-24 pp** |

The 90-100 band — previously the AI's most reliable — now contains 32 predictions (up from 20) and accuracy dropped from 90% to 66%. **The AI is over-confident on the new prompt.**

## What worked

| Row | Baseline | Iteration | Result | Why |
|---|---|---|---|---|
| 685 (Basket and Beads) | Uncertain 55% | Active 95% | ✓ | Scraper apparently picked up the live site this run |
| 193 (Alpha Outpost) | Uncertain 65% | Likely Closed 72% | ✓ | F2 mandatory social check found the closure announcement |
| 380 (A Simple Organizing) | Uncertain 55% | Likely Closed 90% | ✓ | F1 worked on this one — DOT# alone not enough |
| 538 (Spectra Cargo) | Uncertain 65% | Likely Closed 75% | ✓ | F1 worked here too |
| 556 (Spicers Nicer) | Uncertain 60% | Active 95% | ✓ | F5 single-channel Facebook rule worked |

**5 of the 14 expected resolutions actually landed.** F2, F3, F5 mostly worked. F1 is the problem.

## Root cause hypothesis

The "ENTITY EXISTENCE vs. OPERATIONAL STATUS" subsection I added (per Julian's feedback that we shouldn't dismiss directory listings entirely) **gave the AI permission to use them as positive evidence too freely.** The intended reading was "these are existence proofs, not operation proofs." The AI's reading appears to be "these are valid Active signals when combined with anything else."

The current prompt has competing instructions:
- "If (a)-(e) all apply → Likely Closed at 65-75%" — pushes toward Closed
- "Use them this way: when paired with at least one recency signal from another channel, they strengthen an Active or Uncertain verdict" — pushes toward Active

**The AI is preferentially applying the second rule.** When it sees a directory listing + a website that loads at all, it's calling Active even when the website is a parking page.

## What to do

Three options, ranked by my recommendation:

### Option A: Revert and propose iteration 2 with smaller scope (RECOMMENDED)

1. `git revert 6434612` — back to baseline 69%.
2. Re-apply only the fixes that worked: **F2 (hijacked-domain), F3 (Etsy URL guard), F5 (marketplace + Facebook-as-website)**.
3. Skip F1 entirely for now — it's too easy to misinterpret. Pattern-B-hesitancy is a real failure but the prompt fix isn't right yet.
4. Skip F4 — it didn't move the needle on the 2 NWP rows.

Expected iteration 2 result: 69% baseline + maybe +4 from F2/F3/F5 = **~75% agreement.** Modest but real progress with no regressions.

### Option B: Fix-forward with F1 v2

Replace the F1 prompt section entirely. Remove the "ENTITY EXISTENCE" subsection. Make the rule one-directional: "Directory listings + dead website + no 2024+ recency = Likely Closed. They do NOT support Active unless paired with a 2024+ social post or current Google Business Profile."

Risk: another iteration cycle, another $0.53 in API spend, no guarantee F1 v2 won't have its own pathology.

### Option C: Accept the regression, ship iteration 1

Not recommended. The regression is real, the calibration degraded, and the leadership packet would have to defend a 62% number.

## Recommendation

**Option A.** Revert, re-apply F2/F3/F5 only, re-run, expect ~75% with no regressions. Document F1 as a "next-iteration target requiring more careful prompt design."

The Codex review #3 step from the original plan is now even more important — Codex will catch the contradictions in F1 that I missed when authoring it.

## Files produced

- `eval/datasets/bmosg_v1_iteration_1_predictions.csv` — full 60-row re-run output
- `eval/reports/iteration_1_comparison/report.md` — detailed per-row comparison
- `eval/reports/iteration_1_comparison/baseline_confusion.csv`
- `eval/reports/iteration_1_comparison/iteration_confusion.csv`
- `eval/reports/iteration_1_comparison/per_row_comparison.csv`
- `business_checker/eval/rerun_sample.py` — re-run helper (kept for future iterations)
- `business_checker/eval/compare_iterations.py` — comparison helper (kept)

## Next step

**Pause before action.** Julian to choose Option A, B, or C. I'll execute whichever path he picks.
