# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_5c_predictions.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 30/58 = 51.7% | **-17.2 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 3 | Was wrong before, now correct |
| Regressed | 13 | Was correct before, now wrong |
| Unchanged (correct) | 27 | Correct in both |
| Unchanged (wrong) | 15 | Wrong in both |
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
| Active          |       20 |               1 |           1 |                 0 |
| Likely Closed   |        8 |               9 |           7 |                 0 |
| Uncertain       |        6 |               1 |           1 |                 2 |
| No Web Presence |        1 |               1 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 6 | 0% |
| 60-69 | 5 | 0% | 2 | 0% |
| 70-79 | 19 | 84% | 4 | 100% |
| 80-89 | 3 | 67% | 13 | 54% |
| 90-100 | 20 | 90% | 33 | 58% |

## Resolved rows (baseline wrong → iteration correct)


### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _Multiple live websites (basketsandbeadskenya.com with contact info and returns policy, basketsandbeadskenya.org with founder details and mission, blogs referencing current retail space in Long Beach CA) show real products, services, and contact details as of 2026._

### Row 286 — Sword & Plough
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Likely Closed** (85%) ✓
- Iteration evidence: _Listed website swordandplough.com redirects to expired domain parking page on tenereteam.com with no business content; search results reference old articles/interviews pre-2023 with no recent activity found on Google, social media, or maps._

### Row 114 — Disgruntled Decks
- Your label: **Active**
- Baseline AI: **Uncertain** (50%)
- Iteration AI: **Active** (85%) ✓
- Iteration evidence: _Website https://disgruntleddecks.com loads with real product descriptions (military-themed card game playable standalone or as Cards Against Humanity expansion), shop page linking to Amazon for purchases including 'Quick and Dirty Military Edition' and 'Coastie-themed' deck, and active suggestion fo_

## Regressed rows (baseline correct → iteration wrong)


### Row 192 — 365 Self-Defense
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Website is a non-functional parking/placeholder page; no additional search results or social media activity provided across Google, Maps, Facebook, Instagram, LinkedIn, or other channels to confirm current operation._

### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (92%) ✗
- Iteration evidence: _Website dead (DNS failure), but experience.com lists Overtons Grading LLC in Ridgeville, SC with current business hours (Thu/Fri 7AM-5PM, Sat 7AM-1PM) and phone (843) 312-2149; separate Overholt Grading LLC active in Abbeville, SC on procore.com and overholtgrading.com._

### Row 95 — Travel Halo
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _RocketReach profile lists Michael Vahey currently as Manager, Inventor, Entrepreneur at Travel Halo (no date but implies present), with ZoomInfo showing active address and phone in Williamsburg, VA._

### Row 455 — SMB Coaching
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Wix website is a non-functional 'coming soon' placeholder; search results show multiple unrelated SMB entities with old content (e.g., 2016 coaching dates) or active but distinct businesses (SMB Team law firm services, SMBootcamp programs), no specific recent activity for 'SMB Coaching' found across_

### Row 161 — CHAT Nature's Skin & Hair Co LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (78%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Website https://chatshco.com returns 500 error/coming soon placeholder; only evidence is old directory listing on treasuredlocks.com with address 3732 Lorna Road Hoover AL and phone/email, no date or recent activity found across other channels._

### Row 126 — Enchanted Rose Floral
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (72%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Website shows 'Opening Soon' password-protected page; only evidence is stale ZoomInfo directory listing with no address match to Grand Junction and no recent activity found across other channels._

### Row 91 — Stars & Stripes Gifts LV
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Gudsy.org lists Help R Heroes Corp (aka Stars and Stripes Gifts LV) as an active 501(c)(3) nonprofit with unconditional exemption and deductible donations as of Dec 2023._

### Row 624 — Casa Los Juanes
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Airbnb listing at https://airbnb.com/rooms/36275724 shows current rental availability for Casa Los Juanes in St. Augustine, Florida, as an operating vacation rental business with active booking interface._

### Row 97 — Tripoli Gift Company
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (50%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Listed as active veteran-owned business on IVMF Syracuse directory (ivmf.syracuse.edu) and VA News article referencing tripoligiftcompany.com with veteran owner Joe Winslow, both post-2021 with no closure signals._

### Row 388 — Business Served
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (85%) ✗
- Iteration evidence: _Website https://businessserved.com shows only placeholder-like repetitive text with no real business details; Google searches, directories, and competitor listings yield no specific matches or activity for 'Business Served' in Charlotte, NC across all channels._

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **No Web Presence** (85%) ✗
- Iteration evidence: _Listed website cirrusts.com hosts unrelated IT services business in Jacksonville FL; exhaustive search across Google, Maps, social media, and directories found no specific presence, activity, or mentions for 'Secretariat Strategie LLC' in Fort Lauderdale or elsewhere since 2021._

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Multiple active directory listings including THCaNearby with 10 reviews describing current product selection (flower, vapes, edibles), CannabisShop.com with store details and hours, and AiLOQ.com highlighting veteran-owned status and premium hemp products, all without closure indicators as of 2026._

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Etsy shop at https://etsy.com/shop/CRSpices listed as the business website, qualifying as active e-commerce presence for a product-based spice business._

## Still-disagreement rows (wrong in both)


### Row 271 — Princess Leahs Designs
- Your label: **Uncertain**
- Baseline AI: **Active** (95%)
- Iteration AI: **Active** (92%)

### Row 85 — Reflections of Service
- Your label: **Uncertain**
- Baseline AI: **Active** (100%)
- Iteration AI: **Active** (95%)

### Row 583 — Achieve New Heights, LLC
- Your label: **Uncertain**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (80%)

### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **Likely Closed** (90%)

### Row 125 — Emotion On Walls
- Your label: **No Web Presence**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (85%)

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

### Row 680 — Bundook
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Uncertain** (65%)

### Row 177 — Peachy Keen Perfume
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (92%)

### Row 380 — A Simple Organizing & Moving Company, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (92%)

### Row 556 — Spicers Nicer Massage Therapy
- Your label: **Active**
- Baseline AI: **Uncertain** (60%)
- Iteration AI: **Uncertain** (50%)

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Active** (95%)

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)