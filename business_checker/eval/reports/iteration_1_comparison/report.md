# Iteration 1 vs Baseline Comparison

**Baseline:** `eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `eval/datasets/bmosg_v1_iteration_1_predictions.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 36/58 = 62.1% | **-6.9 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 5 | Was wrong before, now correct |
| Regressed | 9 | Was correct before, now wrong |
| Unchanged (correct) | 31 | Correct in both |
| Unchanged (wrong) | 13 | Wrong in both |
| **Net delta** | **-4** | resolved − regressed |

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
| Likely Closed   |        7 |              16 |           1 |                 0 |
| Uncertain       |        6 |               3 |           0 |                 1 |
| No Web Presence |        0 |               2 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 0 | — |
| 60-69 | 5 | 0% | 2 | 0% |
| 70-79 | 19 | 84% | 13 | 54% |
| 80-89 | 3 | 67% | 11 | 73% |
| 90-100 | 20 | 90% | 32 | 66% |

## Resolved rows (baseline wrong → iteration correct)


### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _https://basketsandbeadskenya.org loads with real business content describing hand-crafted fair trade products by Kenyan artisans, current contact info for founder Eldonna Lewis Fernandez including (310) 591-9803 and Irvine CA address, and https://basketsandbeadskenya.com contact page confirms operat_

### Row 193 — Alpha Outpost
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Likely Closed** (72%) ✓
- Iteration evidence: _Website domain hijacked by spam/casino content (non-functional as of search). Contact page archive shows business address and phone at 2015 Dean St., St. Charles, IL. Salary.com lists 6–10 employees, $1M–$5M revenue, founded 2015. YouTube reviews of subscription boxes from ~2016 (first-year retrospe_

### Row 380 — A Simple Organizing & Moving Company, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Likely Closed** (90%) ✓
- Iteration evidence: _Website domain is a parked/squatted placeholder page with no business content, FMCSA DOT snapshot shows DOT# 4058103 as active but no independent social media presence, Google Maps, Yelp, or other channel reveals any recent operational activity for A Simple Organizing & Moving Company, LLC as of 202_

### Row 556 — Spicers Nicer Massage Therapy
- Your label: **Active**
- Baseline AI: **Uncertain** (60%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _Listed website is a Facebook business page (facebook.com/spicersnicermassagetherapy); per FAST PATH rules, Facebook page URLs are evaluated as the primary channel, and qualifies as Active if most recent post or update within 12 months shows business activity (current as of May 2026)._

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Likely Closed** (75%) ✓
- Iteration evidence: _Website is a domain parking page for sale; FMCSA/Safer record shows active USDOT 3310327 with authorized property operating authority but different address; Indeed reviews and ZoomInfo/LoadConnect listings exist but no dates post-2022; no Google Maps, Facebook, Instagram, LinkedIn, or recent marketp_

## Regressed rows (baseline correct → iteration wrong)


### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _experience.com listing shows current business hours (Wed-Fri 7AM-5PM, Sat 7AM-1PM) and phone (843) 312-2149 for Overtons Grading LLC in Ridgeville, SC; Syracuse University IVMF veteran services directory lists overtonsgrading.com as active with owner Keith Overton._

### Row 413 — Granted Advocacy Partners, Inc. (GAP, Inc.)
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _standingap.com returns 404 error but LinkedIn-style company page at standingap.com/board-of-directors lists Lisa Francis as current CEO and Founder of Granted Advocacy Partners, Inc. with substantive leadership content and ©2026 footer implied by context._

### Row 624 — Casa Los Juanes
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (88%) ✗
- Iteration evidence: _The listed website URL (https://airbnb.com/rooms/36275724) is an active Airbnb listing for a vacation rental property named Casa Los Juanes in St. Augustine, Florida. Airbnb listings with active booking pages and current availability represent operating businesses. The property is searchable and boo_

### Row 97 — Tripoli Gift Company
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (50%) ✓
- Iteration AI: **Likely Closed** (75%) ✗
- Iteration evidence: _listed website is a dead domain (DNS failure / no visible Tripoli Gift Company content), no matching Google Business Profile or open listing for 'Tripoli Gift Company' in Luray, Virginia, and no active Facebook, Instagram, or marketplace storefront showing recent sales or activity specifically under_

### Row 388 — Business Served
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (85%) ✗
- Iteration evidence: _Listed website https://businessserved.com shows only generic placeholder text repeating 'Customized Human Resources Consulting and Professional Development Service' with no specific business details, products, or recency; Google searches for 'Business Served' Charlotte return no matches for this bus_

### Row 602 — Griggsgear.com
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Website https://griggsgear.com loads with active contact page and business operations; supported by ZoomInfo profile listing headquarters, phone, and revenue with no closure indicators._

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Website loads with real business content (IT services company offering managed IT, cybersecurity, HIPAA compliance, and specialized services for law firms and government), physical address in Jacksonville FL, phone number listed, service descriptions specific and current. Separately, 'Secretariat Ad_

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Likely Closed** (72%) ✗
- Iteration evidence: _[Domain confirmed dead via direct check] Domain https://norwoodnaturals.com is a non-functional parking/placeholder page. Comprehensive search across Facebook, Instagram, and LinkedIn returned no business page or active social presence for 'Norwood Natural's CBD'. Google search for 'Norwood Natural'_

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (92%) ✗
- Iteration evidence: _Etsy shop URL (etsy.com/shop/CRSpices) is a valid storefront endpoint; Oshkosh Chamber directory lists Wisconsin Spice Inc. at the same address with current phone number and website, confirming this is a real, registered business in the spice/seasonings industry in Wisconsin; no closure signals foun_

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
- Iteration AI: **Likely Closed** (78%)

### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **Likely Closed** (75%)

### Row 125 — Emotion On Walls
- Your label: **No Web Presence**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (72%)

### Row 31 — King’s Coffee, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 470 — TTG Properties
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Uncertain** (65%)

### Row 163 — Dashfire Beards
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (92%)

### Row 286 — Sword & Plough
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)

### Row 680 — Bundook
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%)

### Row 114 — Disgruntled Decks
- Your label: **Active**
- Baseline AI: **Uncertain** (50%)
- Iteration AI: **Uncertain** (68%)

### Row 177 — Peachy Keen Perfume
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (92%)

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Likely Closed** (75%)