# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_5b_predictions.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 35/58 = 60.3% | **-8.6 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 3 | Was wrong before, now correct |
| Regressed | 8 | Was correct before, now wrong |
| Unchanged (correct) | 32 | Correct in both |
| Unchanged (wrong) | 15 | Wrong in both |
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
| Active          |       20 |               0 |           2 |                 0 |
| Likely Closed   |        8 |              11 |           4 |                 1 |
| Uncertain       |        5 |               1 |           4 |                 0 |
| No Web Presence |        0 |               2 |           0 |                 0 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 7 | 29% |
| 60-69 | 5 | 0% | 2 | 50% |
| 70-79 | 19 | 84% | 10 | 80% |
| 80-89 | 3 | 67% | 11 | 55% |
| 90-100 | 20 | 90% | 28 | 64% |

## Resolved rows (baseline wrong → iteration correct)


### Row 314 — A Guide to Improvised Weaponry
- Your label: **Active**
- Baseline AI: **Likely Closed** (85%)
- Iteration AI: **Active** (85%) ✓
- Iteration evidence: _Website at terryschappert.com/book.html actively promotes 'A Guide to Improvised Weaponry' book with Amazon purchase link and 2015 release date alongside current site navigation for ongoing media and TV projects._

### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (87%) ✓
- Iteration evidence: _Website basketsandbeadskenya.com currently shows 'coming soon' placeholder, but business is clearly operating: contact page lists active email (eldonna@basketsandbeadskenya.com) and phone (310-591-9803), founder Eldonna Lewis Fernandez identified with current business role, 'Our Story' page describe_

### Row 380 — A Simple Organizing & Moving Company, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Likely Closed** (72%) ✓
- Iteration evidence: _Website simpleoam.com is a dead parking page (non-functional as of May 2026); FMCSA SAFER database shows DOT# 4058103 registered to the Haslet TX address with phone (817) 564-4474, but no current social media presence found on Facebook, Instagram, or LinkedIn for this business; no Google Maps listin_

## Regressed rows (baseline correct → iteration wrong)


### Row 87 — Saltwater & Sand
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Website returns 404 error (dead domain); initial search results contain no listings, directories, social media, Google Maps, or other presence specific to 'Saltwater & Sand' in Pismo Beach, CA, with no activity found after 2021 across standard channels._

### Row 413 — Granted Advocacy Partners, Inc. (GAP, Inc.)
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Uncertain** (62%) ✗
- Iteration evidence: _Website (standingap.com) returns 404 error. Found reference to 'Lisa Francis, CEO and Founder of Granted Advocacy Partners, Inc.' on standingap.com board page (result [4]), confirming business existence, but no current activity verification across Google Search, Google Maps, Facebook, Instagram, Lin_

### Row 95 — Travel Halo
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _RocketReach profile lists Michael Vahey currently as Manager, Inventor, Entrepreneur at Travel Halo (no date but active profile as of 2026), with supporting ZoomInfo listing address, phone, and website._

### Row 161 — CHAT Nature's Skin & Hair Co LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (78%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Live website at https://chatshco.com/home shows real products like Refine Cleanser priced at $24.99 with copyright 2026; BBB listing confirms address at 3809 32nd St, Tuscaloosa, AL and phone (205) 394-7561._

### Row 126 — Enchanted Rose Floral
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (72%) ✓
- Iteration AI: **Uncertain** (55%) ✗
- Iteration evidence: _Website shows 'Opening Soon' password-protected page; ZoomInfo lists Country Elegance Florists at a Grand Junction address with 1-10 employees but no recency or direct match; no active social media, Google Maps, or recent reviews found for Enchanted Rose Floral._

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Live website secretariat-intl.com with detailed office locations, services, and contact info across multiple US cities; recent job postings for Secretariat Strategie LLC on dailyremote.com and talents.vaia.com; S&P Global ratings article on Secretariat Advisors LLC._

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Multiple directory listings including THCaNearby with 10 reviews calling it a reliable Indianapolis shop, CannabisShop.com with store details and hours, and AiLOQ describing premium hemp products for adults/pets; website is dead parking page but directories indicate ongoing operation._

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Etsy shop CRSpices at https://etsy.com/shop/CRSpices listed with real products available for unique or custom purchase as a spice business, current as of 2026 search results._

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
- Iteration AI: **Likely Closed** (78%)

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
- Iteration AI: **Uncertain** (55%)

### Row 193 — Alpha Outpost
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (92%)

### Row 163 — Dashfire Beards
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (88%)

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

### Row 556 — Spicers Nicer Massage Therapy
- Your label: **Active**
- Baseline AI: **Uncertain** (60%)
- Iteration AI: **Uncertain** (50%)

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **Likely Closed** (85%)

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (95%)