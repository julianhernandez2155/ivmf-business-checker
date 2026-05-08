# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_6_verified.csv`
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
| Active          |       20 |               0 |           1 |                 1 |
| Likely Closed   |       12 |               7 |           5 |                 0 |
| Uncertain       |        4 |               2 |           4 |                 0 |
| No Web Presence |        1 |               1 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 6 | 33% |
| 60-69 | 5 | 0% | 1 | 0% |
| 70-79 | 19 | 84% | 5 | 80% |
| 80-89 | 3 | 67% | 14 | 36% |
| 90-100 | 20 | 90% | 32 | 62% |

## Resolved rows (baseline wrong → iteration correct)


### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (92%) ✓
- Iteration evidence: _Website basketsandbeadskenya.org loads with current business description, founder contact (Eldonna Lewis Fernandez, 310-591-9803), and Irvine CA address (5325 Alton Pkwy #C-426). Basketsandbeadskenya.com (alternate domain) also displays active e-commerce storefront with fair trade products, contact _

### Row 114 — Disgruntled Decks
- Your label: **Active**
- Baseline AI: **Uncertain** (50%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _Website https://disgruntleddecks.com loads with detailed product descriptions for military-themed card game, FAQs, and direct links to purchase on Amazon._

## Regressed rows (baseline correct → iteration wrong)


### Row 87 — Saltwater & Sand
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _[2-pass disagreement — Pass 1: Uncertain, Pass 2: Likely Closed] Website returns 404 error; only evidence found is a San Antonio, TX nonprofit 'Saltwater Sand & Sunsets' with active IRS 501(c)(3) status since February 2024, but no matches for 'Saltwater & Sand' in Pismo Beach, CA across Google, Maps_

### Row 192 — 365 Self-Defense
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Uncertain** (50%) ✗
- Iteration evidence: _[2-pass disagreement — Pass 1: Uncertain, Pass 2: Likely Closed] Website is a non-functional parking/placeholder page; no additional evidence from Google search, Google Maps, Facebook, Instagram, LinkedIn, or other channels confirming recent activity post-2021._

### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Website overtonsgrading.com is down (DNS failure), but active listings on experience.com with current business hours (Thu/Fri 7AM-5PM, Sat 7AM-1PM) and phone (843-312-2149), plus Syracuse University IVMF veteran services directory entry for Overton's Grading LLC owned by Keith Overton._

### Row 413 — Granted Advocacy Partners, Inc. (GAP, Inc.)
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Website standingap.com returns 404 error, but Charity Navigator profile active for Granted Advocacy Partners Inc. (EIN 82-3291226) with current small nonprofit status, and standingap.com board page lists Lisa Francis as current CEO and Founder of Granted Advocacy Partners, Inc._

### Row 95 — Travel Halo
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _RocketReach profile lists Michael Vahey currently as Manager, Inventor, Entrepreneur at Travel Halo (no date but active as of 2026 search), with ZoomInfo showing address and phone; website is dead parking page but owner association confirms ongoing operation._

### Row 161 — CHAT Nature's Skin & Hair Co LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (78%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Website https://chatshco.com loads with real products like Refine Cleanser priced at $24.99, featured products section, and copyright year © 2026 in the footer._

### Row 126 — Enchanted Rose Floral
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Country Elegance Florist (likely same as Enchanted Rose Floral) listed as participant in Petal It Forward 2025 per SAF document, confirming operation in Grand Junction, CO as of 2025._

### Row 91 — Stars & Stripes Gifts LV
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Gudsy.org lists Help R Heroes Corp (aka Stars and Stripes Gifts LV) as an active 501(c)(3) charitable organization with unconditional exemption and deductible donations as of Dec 2023._

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **Likely Closed** (85%) ✗
- Iteration evidence: _Website at cirrusts.com shows generic IT services template content with Jacksonville, FL address (not Fort Lauderdale registration location), no business-specific details, no dates, no contact form, and no evidence of real operations. Search results show 'Secretariat Strategie LLC' appears only as a_

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Multiple directory listings including THCaNearby with 5.0 rating and reviews describing it as a reliable Indianapolis shop, CannabisShop.com with store details and hours, Manta, ZoomInfo, and AiLOQ all confirming operations at 3440 North Shadeland Avenue with product descriptions, no closure signals_

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Etsy shop at https://etsy.com/shop/CRSpices listed as the business website with real products for sale; supported by recent Eventeny activity for Tropical Spice LLC (Oshkosh, WI) joined in 2024 with event participation._

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
- Iteration AI: **Likely Closed** (85%)

### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **No Web Presence** (80%)

### Row 125 — Emotion On Walls
- Your label: **No Web Presence**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (85%)

### Row 31 — King’s Coffee, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 470 — TTG Properties
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Uncertain** (55%)

### Row 193 — Alpha Outpost
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (87%)

### Row 163 — Dashfire Beards
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 286 — Sword & Plough
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Uncertain** (50%)

### Row 680 — Bundook
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Uncertain** (65%)

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
- Iteration AI: **Uncertain** (78%)

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Active** (95%)

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)