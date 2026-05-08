# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_3_predictions.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 32/58 = 55.2% | **-13.8 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 2 | Was wrong before, now correct |
| Regressed | 10 | Was correct before, now wrong |
| Unchanged (correct) | 30 | Correct in both |
| Unchanged (wrong) | 16 | Wrong in both |
| **Net delta** | **-8** | resolved − regressed |

## Baseline confusion matrix (rows = your label, cols = AI)

| truth           |   Active |   Likely Closed |   Uncertain |   No Web Presence |
|:----------------|---------:|----------------:|------------:|------------------:|
| Active          |       18 |               1 |           3 |                 0 |
| Likely Closed   |        0 |              15 |           9 |                 0 |
| Uncertain       |        2 |               1 |           7 |                 0 |
| No Web Presence |        0 |               1 |           1 |                 0 |

## Iteration confusion matrix (rows = your label, cols = AI)

| truth           |   Active |   Likely Closed |   Uncertain |   No Web Presence |
|:----------------|---------:|----------------:|------------:|------------------:|
| Active          |       18 |               0 |           3 |                 1 |
| Likely Closed   |        9 |              11 |           2 |                 2 |
| Uncertain       |        2 |               4 |           3 |                 1 |
| No Web Presence |        1 |               1 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 2 | 0% |
| 60-69 | 5 | 0% | 4 | 25% |
| 70-79 | 19 | 84% | 17 | 59% |
| 80-89 | 3 | 67% | 6 | 50% |
| 90-100 | 20 | 90% | 29 | 62% |

## Resolved rows (baseline wrong → iteration correct)


### Row 271 — Princess Leahs Designs
- Your label: **Uncertain**
- Baseline AI: **Active** (95%)
- Iteration AI: **Uncertain** (75%) ✓
- Iteration evidence: _[URL on file but could not confirm content — flagged for review] Listed Etsy URL is /people/PrincessLeahDesigns (user profile, not storefront); Etsy searches for 'Princess Leahs Designs' return only generic Princess Leia market/search pages from unrelated sellers, no specific shop, social media, Goo_

### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (92%) ✓
- Iteration evidence: _basketsandbeadskenya.org loads with substantive content describing fair trade artisan products, founder/operator contact information (Eldonna Lewis Fernandez, eldonna@basketsandbeadskenya.com, 310-591-9803), and current operations. Basketsandbeadskenya.com contact page shows active business address _

## Regressed rows (baseline correct → iteration wrong)


### Row 562 — Back Office Administrations LLC
- Your label: **Active**
- Baseline AI: **Active** (95%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Listed website https://backofficeadministrators.com not provided and appears dead/missing (no content in search results); FedLinks directory profile for Back Office Administrators, LLC in Fredericksburg, VA exists but no activity date; no recent social media, Google Maps, or other channel hits found_

### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Uncertain** (65%) ✗
- Iteration evidence: _Website overtonsgrading.com inaccessible (DNS failure); experience.com listing shows business hours through Saturday but no review dates; Syracuse IVMF directory mentions owner Keith Overton with no activity recency._

### Row 413 — Granted Advocacy Partners, Inc. (GAP, Inc.)
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _standingap.com returns 404 error but standingap.com/board-of-directors page loads with current content naming Lisa Francis as CEO and Founder of Granted Advocacy Partners, Inc., confirming active operation as of 2026._

### Row 161 — CHAT Nature's Skin & Hair Co LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (78%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Website https://chatshco.com loads with real products like Refine Cleanser priced at $24.99 and copyright 2026; Chatto.com hosts active Nature's Natural skin & hair product collections matching business name._

### Row 126 — Enchanted Rose Floral
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (72%) ✓
- Iteration AI: **Uncertain** (65%) ✗
- Iteration evidence: _Listed website shows 'Opening Soon' password-protected page with no products or services; search results reveal other florists but no active social media, Google Maps, or recent listings specifically for 'Enchanted Rose Floral' in Grand Junction, CO._

### Row 624 — Casa Los Juanes
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (75%) ✗
- Iteration evidence: _Listed Airbnb URL shows generic search page with no business-specific content; searches for 'Casa Los Juanes' Saint Augustine Florida yield no matching business listings, social media, Google Maps, or recent activity on any channel, only unrelated historical sites._

### Row 97 — Tripoli Gift Company
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (50%) ✓
- Iteration AI: **Likely Closed** (85%) ✗
- Iteration evidence: _Website tripoligiftcompany.com appears dead (no content provided, only referenced in old directories); most recent specific mentions in IVMF directory and VA News article from pre-2023 with broken link; no active social media, Google Maps, or marketplace listings found for Tripoli Gift Company in Lu_

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **Likely Closed** (75%) ✗
- Iteration evidence: _Domain cirrusts.com appears to be a generic IT services template with no business-specific content or dates; the search returned results for 'Secretariat' (a different consulting firm) and 'Secretariat Strategie LLC' (appearing only on job boards), but no active presence, social media, Google Maps l_

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Likely Closed** (75%) ✗
- Iteration evidence: _[Domain confirmed dead via direct check] Website is a parking/placeholder page; all search results from disallowed data aggregators (Manta, THCaNearby, CannabisShop, ZoomInfo, AiLOQ) with no dates, no social media profiles, Google Maps, marketplaces, or owner activity found after thorough channel ch_

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Etsy storefront at https://etsy.com/shop/CRSpices is the listed primary website qualifying as active commerce presence per FAST PATH rules for marketplace storefronts._

## Still-disagreement rows (wrong in both)


### Row 85 — Reflections of Service
- Your label: **Uncertain**
- Baseline AI: **Active** (100%)
- Iteration AI: **Active** (95%)

### Row 583 — Achieve New Heights, LLC
- Your label: **Uncertain**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (78%)

### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **No Web Presence** (85%)

### Row 125 — Emotion On Walls
- Your label: **No Web Presence**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (75%)

### Row 31 — King’s Coffee, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 470 — TTG Properties
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **No Web Presence** (75%)

### Row 193 — Alpha Outpost
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (92%)

### Row 163 — Dashfire Beards
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 286 — Sword & Plough
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)

### Row 680 — Bundook
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **No Web Presence** (75%)

### Row 114 — Disgruntled Decks
- Your label: **Active**
- Baseline AI: **Uncertain** (50%)
- Iteration AI: **Uncertain** (50%)

### Row 177 — Peachy Keen Perfume
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)

### Row 380 — A Simple Organizing & Moving Company, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 556 — Spicers Nicer Massage Therapy
- Your label: **Active**
- Baseline AI: **Uncertain** (60%)
- Iteration AI: **Uncertain** (65%)

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Active** (95%)

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (85%)