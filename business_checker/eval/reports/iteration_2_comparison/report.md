# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_2_predictions.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 35/58 = 60.3% | **-8.6 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 4 | Was wrong before, now correct |
| Regressed | 9 | Was correct before, now wrong |
| Unchanged (correct) | 31 | Correct in both |
| Unchanged (wrong) | 14 | Wrong in both |
| **Net delta** | **-5** | resolved − regressed |

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
| Likely Closed   |        8 |              12 |           3 |                 1 |
| Uncertain       |        3 |               1 |           3 |                 3 |
| No Web Presence |        1 |               1 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 1 | 0% |
| 60-69 | 5 | 0% | 4 | 25% |
| 70-79 | 19 | 84% | 11 | 73% |
| 80-89 | 3 | 67% | 12 | 50% |
| 90-100 | 20 | 90% | 30 | 67% |

## Resolved rows (baseline wrong → iteration correct)


### Row 271 — Princess Leahs Designs
- Your label: **Uncertain**
- Baseline AI: **Active** (95%)
- Iteration AI: **Uncertain** (72%) ✓
- Iteration evidence: _[URL on file but could not confirm content — flagged for review] The listed URL etsy.com/people/PrincessLeahDesigns is a user profile page (not a storefront /shop/ URL). Etsy market search results returned only category pages and generic Princess Leia merchandise listings, no actual shop or seller s_

### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _https://basketsandbeadskenya.org loads with real content describing artisan products sold in Southern California retail and online store, founder contact info, and mission details; https://basketsandbeadskenya.com contact page lists Irvine CA address and email with active subscription form._

### Row 114 — Disgruntled Decks
- Your label: **Active**
- Baseline AI: **Uncertain** (50%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _Website https://disgruntleddecks.com loads with detailed product descriptions for military-themed card game including FAQs, Navy edition, and direct links to purchase on Amazon, indicating current operation._

### Row 556 — Spicers Nicer Massage Therapy
- Your label: **Active**
- Baseline AI: **Uncertain** (60%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _Facebook business page (primary website listed) shows active massage therapy business with owner Jared Spicer; YouTube interview from The Pulse SD confirms current operation as CEO/Owner of Spicers Nicer Massage Therapy with specific services (deep tissue, Swedish massage, Reiki) and contact details_

## Regressed rows (baseline correct → iteration wrong)


### Row 562 — Back Office Administrations LLC
- Your label: **Active**
- Baseline AI: **Active** (95%) ✓
- Iteration AI: **Uncertain** (65%) ✗
- Iteration evidence: _Listed website https://backofficeadministrators.com not provided and appears dead/missing (no content in search results), FedLinks directory profile for Back Office Administrators, LLC in Fredericksburg VA mentions services and 50+ years experience but no activity date after 2021._

### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _experience.com profile for Overtons Grading LLC in Ridgeville, SC shows current business hours (Tue-Thu 7AM-5PM, etc.), phone (843) 312-2149, and active quote request form as of 2026._

### Row 95 — Travel Halo
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _RocketReach profile lists Michael Vahey currently as Manager, Inventor, Entrepreneur at Travel Halo (Williamsburg, VA) as of 2026; ZoomInfo shows active company profile with phone and address; website is dead parking page but owner affiliation indicates ongoing operation._

### Row 126 — Enchanted Rose Floral
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (72%) ✓
- Iteration AI: **Uncertain** (65%) ✗
- Iteration evidence: _Website shows 'Opening Soon' password-protected page with no products or services; search results show other flower delivery services in Grand Junction CO and a separate 'Enchanted Rose Floral Company' with handmade wood flowers, but no specific recent activity for 'Enchanted Rose Floral' confirmed._

### Row 624 — Casa Los Juanes
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (85%) ✗
- Iteration evidence: _Listed Airbnb URL shows generic search page with no business-specific content; searches for 'Casa Los Juanes' Saint Augustine Florida yield no matching business listings, social media, Google Maps, or marketplace presence, only unrelated historic sites and other rentals._

### Row 388 — Business Served
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (75%) ✗
- Iteration evidence: _Listed website https://businessserved.com shows only generic placeholder text repeating 'Customized Human Resources Consulting and Professional Development Service' with no real business-specific content, services, or dates; Google searches for 'Business Served' Charlotte return unrelated process se_

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **No Web Presence** (72%) ✗
- Iteration evidence: _Website domain cirrusts.com loads with generic IT services content (Jacksonville address, no business-specific details matching 'Secretariat Strategie LLC' or Fort Lauderdale). Search results return only 'Secretariat' (international consulting firm, different entity) and 'Secretariat Strategie LLC' _

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Multiple directory listings including THCaNearby with positive reviews describing current shop operations, CannabisShop.com with store details and hours, and AiLOQ.com noting veteran-owned status with premium hemp products; no closure signals found despite dead website._

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (100%) ✗
- Iteration evidence: _Etsy storefront at https://etsy.com/shop/CRSpices is the listed website and qualifies as an active marketplace with current product listings available for purchase._

## Still-disagreement rows (wrong in both)


### Row 85 — Reflections of Service
- Your label: **Uncertain**
- Baseline AI: **Active** (100%)
- Iteration AI: **Active** (95%)

### Row 583 — Achieve New Heights, LLC
- Your label: **Uncertain**
- Baseline AI: **Likely Closed** (75%)
- Iteration AI: **Likely Closed** (85%)

### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **No Web Presence** (85%)

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
- Iteration AI: **Uncertain** (65%)

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
- Iteration AI: **Uncertain** (55%)

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

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Active** (95%)

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (92%)