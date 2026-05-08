# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_5_predictions.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 30/58 = 51.7% | **-17.2 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 1 | Was wrong before, now correct |
| Regressed | 11 | Was correct before, now wrong |
| Unchanged (correct) | 29 | Correct in both |
| Unchanged (wrong) | 17 | Wrong in both |
| **Net delta** | **-10** | resolved − regressed |

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
| Active          |       19 |               1 |           2 |                 0 |
| Likely Closed   |       11 |               9 |           3 |                 1 |
| Uncertain       |        4 |               3 |           2 |                 1 |
| No Web Presence |        0 |               2 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 3 | 33% |
| 60-69 | 5 | 0% | 1 | 0% |
| 70-79 | 19 | 84% | 12 | 50% |
| 80-89 | 3 | 67% | 10 | 30% |
| 90-100 | 20 | 90% | 32 | 62% |

## Resolved rows (baseline wrong → iteration correct)


### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _https://basketsandbeadskenya.org and https://basketsandbeadskenya.com load with real content describing fair trade baskets, beads, and bags by Kenyan artisans, current contact info for founder Eldonna Lewis Fernandez in Irvine CA including phone and email, and mentions of products sold in Southern C_

## Regressed rows (baseline correct → iteration wrong)


### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (92%) ✗
- Iteration evidence: _Website dead (DNS failure), but Experience.com listing shows Overtons Grading LLC in Ridgeville SC with current business hours (Thu/Fri 7AM-5PM, Sat 7AM-1PM) and phone (843) 312-2149 as of 2026._

### Row 413 — Granted Advocacy Partners, Inc. (GAP, Inc.)
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Website standingap.com returns 404 error, but standingap.com/board-of-directors page lists Lisa Francis as current CEO and Founder of Granted Advocacy Partners, Inc., and Charity Navigator profile confirms it as a charitable organization headquartered in Southlake, TX with EIN 82-3291226._

### Row 95 — Travel Halo
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _RocketReach profile lists Michael Vahey as currently Manager, Inventor, Entrepreneur at Travel Halo (Williamsburg, VA) as of 2026; ZoomInfo shows active company profile with phone (757) 565-4375 and address._

### Row 161 — CHAT Nature's Skin & Hair Co LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (78%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Website https://chatshco.com is a non-functional parking page, but products from CHAT Nature's Skin & Hair Co (Nature's Natural™) are listed for sale with free delivery over $100 on https://www.chatto.com/natures-natural-1/ as of 2026._

### Row 410 — FORCE MULTIPLIER TALENT
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Website https://forcemultipliertalent.com DNS failure (dead domain); no specific matches for 'FORCE MULTIPLIER TALENT' in Mccordsville IN across search results, only unrelated 'Force Multiplier' entities like getforcemultiplier.ai (active AI services) and Indeed page for Force Multiplier Solutions i_

### Row 91 — Stars & Stripes Gifts LV
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Uncertain** (70%) ✗
- Iteration evidence: _Website is a non-functional parking page; Gudsy.org lists Help R Heroes Corp (aka Stars and Stripes Gifts LV) as active 501(c)(3) nonprofit as of Dec 2023 with no newer or closure info; no active listings, social media, Google Maps, or other recent channels found._

### Row 624 — Casa Los Juanes
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (75%) ✗
- Iteration evidence: _Airbnb listing at https://airbnb.com/rooms/36275724 shows only generic search page with no business-specific content; searches for 'Casa Los Juanes' Saint Augustine Florida yield no matching business results, only unrelated historic sites and generic St. Augustine listings._

### Row 97 — Tripoli Gift Company
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (50%) ✓
- Iteration AI: **Likely Closed** (78%) ✗
- Iteration evidence: _Website domain tripoligiftcompany.com does not load or is inaccessible (404/dead); business was confirmed operating in 2023 per VA.gov military directory listing owner Joe Winslow as former Marine; no current social media presence found (Facebook, Instagram); no Google Maps listing; no recent activi_

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **Likely Closed** (85%) ✗
- Iteration evidence: _Domain cirrusts.com lists IT services and a Jacksonville, FL address unrelated to 'Secretariat Strategie LLC' in Fort Lauderdale—indicates domain hijacking or squatting. Search results return only 'Secretariat Advisors LLC' / 'Secretariat' international consulting firm (different entity, headquarter_

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Multiple directory listings including THCaNearby with 10 reviews and 5.0 rating describing it as a reliable Indianapolis shop, AiLOQ noting veteran-owned status and premium hemp products, and CannabisShop.com listing store details and hours, all without closure indicators._

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Etsy shop CRSpices has customer reviews with recent activity implied by page 6 existence, listed as active on Syracuse University IVMF veteran-owned business directory (current as of 2026 access)._

## Still-disagreement rows (wrong in both)


### Row 271 — Princess Leahs Designs
- Your label: **Uncertain**
- Baseline AI: **Active** (95%)
- Iteration AI: **Active** (95%)

### Row 85 — Reflections of Service
- Your label: **Uncertain**
- Baseline AI: **Active** (100%)
- Iteration AI: **Active** (95%)

### Row 583 — Achieve New Heights, LLC
- Your label: **Uncertain**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (75%)

### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **Likely Closed** (85%)

### Row 125 — Emotion On Walls
- Your label: **No Web Presence**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (80%)

### Row 31 — King’s Coffee, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 470 — TTG Properties
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Uncertain** (62%)

### Row 193 — Alpha Outpost
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)

### Row 163 — Dashfire Beards
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (92%)

### Row 286 — Sword & Plough
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (92%)

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
- Iteration AI: **Uncertain** (72%)

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Likely Closed** (85%)

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)