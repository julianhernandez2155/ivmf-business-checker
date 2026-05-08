# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_7_3pass.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 31/58 = 53.4% | **-15.5 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 2 | Was wrong before, now correct |
| Regressed | 11 | Was correct before, now wrong |
| Unchanged (correct) | 29 | Correct in both |
| Unchanged (wrong) | 16 | Wrong in both |
| **Net delta** | **-9** | resolved − regressed |

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
| Active          |       20 |               1 |           1 |                 0 |
| Likely Closed   |       10 |               9 |           3 |                 2 |
| Uncertain       |        5 |               2 |           2 |                 1 |
| No Web Presence |        1 |               1 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 4 | 25% |
| 60-69 | 5 | 0% | 1 | 0% |
| 70-79 | 19 | 84% | 5 | 40% |
| 80-89 | 3 | 67% | 13 | 62% |
| 90-100 | 20 | 90% | 35 | 57% |

## Resolved rows (baseline wrong → iteration correct)


### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _[3-pass agreement: all runs returned Active] https://basketsandbeadskenya.org and https://basketsandbeadskenya.com load with real business content including artisan product descriptions, current contact info for Eldonna Lewis Fernandez in Irvine CA, and subscription prompts as of 2026._

### Row 114 — Disgruntled Decks
- Your label: **Active**
- Baseline AI: **Uncertain** (50%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _[3-pass disagreement — Pass 1: Likely Closed, Pass 2: Active, Pass 3: Active] Website loads with real product description and mission statement, but shop page shows 'Temporarily Out of Stock. Back in Stock...some day' with no restock date—a stale placeholder message. Last press coverage is from 2017_

## Regressed rows (baseline correct → iteration wrong)


### Row 192 — 365 Self-Defense
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **No Web Presence** (75%) ✗
- Iteration evidence: _[3-pass disagreement — Pass 1: No Web Presence, Pass 2: No Web Presence, Pass 3: Likely Closed] [Domain dead, no search results found — NWP confirmed] Website is a parking/placeholder page; no specific results found for '365 Self-Defense' Smyrna Tennessee across Google search, Google Maps, Facebook,_

### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _[3-pass agreement: all runs returned Active] experience.com listing shows current business hours (Thu/Fri 7AM-5PM, Sat 7AM-1PM) and phone (843-312-2149) for Overtons Grading LLC in Ridgeville SC; Syracuse University IVMF veteran services directory lists overtonsgrading.com and owner Keith Overton as_

### Row 413 — Granted Advocacy Partners, Inc. (GAP, Inc.)
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _[3-pass disagreement — Pass 1: Uncertain, Pass 2: Active, Pass 3: Active] Website https://standingap.com returns 404 error. Found one reference: Board of Directors page at standingap.com lists 'Lisa Francis, the CEO and Founder of Granted Advocacy Partners, Inc.' with 25+ years of community advocacy_

### Row 95 — Travel Halo
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _[3-pass disagreement — Pass 1: Active, Pass 2: Active, Pass 3: Uncertain] RocketReach profile lists Michael Vahey currently as Manager, Inventor, Entrepreneur at Travel Halo (no date specified but active listing), with ZoomInfo showing address and phone; website is dead parking page._

### Row 161 — CHAT Nature's Skin & Hair Co LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (78%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _[3-pass disagreement — Pass 1: Uncertain, Pass 2: Active, Pass 3: Active] Website https://chatshco.com is a non-functional parking page; business listed in Treasured Locks natural hair salon directory with Hoover AL address and contact info (naturesherbalhealthandbeauty@gmail.com), but no date on li_

### Row 126 — Enchanted Rose Floral
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (72%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _[3-pass agreement on Uncertain — stable hedge] Website shows 'Opening Soon' password-protected page; ZoomInfo lists Country Elegance Florists at a Grand Junction address with 1-10 employees but no recency; no specific recent activity found for Enchanted Rose Floral across other channels._

### Row 624 — Casa Los Juanes
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (85%) ✗
- Iteration evidence: _[3-pass agreement on No Web Presence — stable hedge] Airbnb listing at https://airbnb.com/rooms/36275724 shows generic placeholder content with no business-specific details; searches for 'Casa Los Juanes' Saint Augustine Florida yield no matching business listings, social media, Google Maps, or rece_

### Row 97 — Tripoli Gift Company
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (50%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _[3-pass disagreement — Pass 1: Uncertain, Pass 2: Active, Pass 3: Active] Website tripoligiftcompany.com referenced in VA News article and IVMF directory (no date specified, links provided); no direct access to site content, no recent social media, Maps, or marketplace activity found in search resul_

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **Likely Closed** (85%) ✗
- Iteration evidence: _[3-pass disagreement — Pass 1: No Web Presence, Pass 2: Likely Closed, Pass 3: Likely Closed] Listed website cirrusts.com hosts unrelated IT services business in Jacksonville FL; exhaustive search across Google, Maps, Facebook, Instagram, LinkedIn, and directories found no specific presence, listing_

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _[3-pass agreement: all runs returned Active] Multiple directory listings including THCaNearby with 10 reviews and 5.0 rating describing it as a reliable Indianapolis shop, CannabisShop.com with store details and hours, and AiLOQ.com noting veteran-owned status with premium hemp products, all without_

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _[3-pass agreement: all runs returned Active] Etsy shop CRSpices has customer reviews with sales count of 238 and listing on Syracuse University IVMF veteran-owned business directory, both indicating current operation as of 2026._

## Still-disagreement rows (wrong in both)


### Row 271 — Princess Leahs Designs
- Your label: **Uncertain**
- Baseline AI: **Active** (95%)
- Iteration AI: **Active** (95%)

### Row 85 — Reflections of Service
- Your label: **Uncertain**
- Baseline AI: **Active** (100%)
- Iteration AI: **Active** (98%)

### Row 583 — Achieve New Heights, LLC
- Your label: **Uncertain**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (78%)

### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **Likely Closed** (90%)

### Row 125 — Emotion On Walls
- Your label: **No Web Presence**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (80%)

### Row 31 — King’s Coffee, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Uncertain** (65%)

### Row 470 — TTG Properties
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Uncertain** (55%)

### Row 193 — Alpha Outpost
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)

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
- Iteration AI: **Uncertain** (55%)

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Active** (95%)

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)