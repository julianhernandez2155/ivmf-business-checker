# Iteration 1 vs Baseline Comparison

**Baseline:** `business_checker/eval/datasets/bmosg_v1_eval_sample.csv`
**Iteration:** `business_checker/eval/datasets/bmosg_v1_iteration_4_predictions.csv`
**Scoreable rows (excludes UTD/empty):** 58

## Headline

| Metric | Baseline | Iteration 1 | Delta |
|---|---|---|---|
| Agreement | 40/58 = 69.0% | 35/58 = 60.3% | **-8.6 pp** |

## Change classification

| Class | Count | Description |
|---|---|---|
| Resolved | 6 | Was wrong before, now correct |
| Regressed | 11 | Was correct before, now wrong |
| Unchanged (correct) | 29 | Correct in both |
| Unchanged (wrong) | 12 | Wrong in both |
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
| Active          |       21 |               1 |           0 |                 0 |
| Likely Closed   |       11 |              11 |           0 |                 2 |
| Uncertain       |        5 |               1 |           2 |                 2 |
| No Web Presence |        0 |               1 |           0 |                 1 |

## Calibration: confidence band vs accuracy

| Band | Baseline n | Baseline acc | Iteration n | Iteration acc |
|---|---|---|---|---|
| 50-59 | 11 | 36% | 0 | — |
| 60-69 | 5 | 0% | 0 | — |
| 70-79 | 19 | 84% | 16 | 81% |
| 80-89 | 3 | 67% | 9 | 11% |
| 90-100 | 20 | 90% | 33 | 64% |

## Resolved rows (baseline wrong → iteration correct)


### Row 271 — Princess Leahs Designs
- Your label: **Uncertain**
- Baseline AI: **Active** (95%)
- Iteration AI: **Uncertain** (75%) ✓
- Iteration evidence: _[URL on file but could not confirm content — flagged for review] Listed website is an Etsy /people/ profile page (not a /shop/ storefront); Etsy searches for business name yield only generic Princess Leia market/category pages from unrelated sellers, with no specific shop, social media, Google Maps,_

### Row 685 — Basket and Beads Kenya
- Your label: **Active**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _https://basketsandbeadskenya.org and https://basketsandbeadskenya.com load with real content describing fair trade baskets, beads, and bags handcrafted by Kenyan artisans, current contact info for founder Eldonna Lewis Fernandez in Irvine CA including phone (310) 591-9803 and email, and mentions of _

### Row 114 — Disgruntled Decks
- Your label: **Active**
- Baseline AI: **Uncertain** (50%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _Website https://disgruntleddecks.com loads with real product description for the Disgruntled Decks card game including specific military themes, target audience, and purpose, indicating a currently operating business._

### Row 380 — A Simple Organizing & Moving Company, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (55%)
- Iteration AI: **Likely Closed** (72%) ✓
- Iteration evidence: _Website (simpleoam.com) is a dead parking/placeholder page. FMCSA SAFER database shows registered address and phone (817-564-4474) at 808 Schoolhouse Rd, Haslet TX, but no recent activity signals found. oTrucking directory entry exists but contains no recency data. Search results reference generic o_

### Row 556 — Spicers Nicer Massage Therapy
- Your label: **Active**
- Baseline AI: **Uncertain** (60%)
- Iteration AI: **Active** (95%) ✓
- Iteration evidence: _Listed website is the Facebook page facebook.com/spicersnicermassagetherapy; as a Facebook-native business, it qualifies as Active per FAST PATH if recent posts within 12 months show activity (2023–2026), though specific post dates unavailable in provided search results._

### Row 88 — SerenaTea,LLC
- Your label: **No Web Presence**
- Baseline AI: **Uncertain** (75%)
- Iteration AI: **No Web Presence** (72%) ✓
- Iteration evidence: _The listed website (serenateallc.com) is a dead Wix parking page with no business content. Search results return 'SereniTea' and 'Serenity' businesses in Chicago, but none match 'SerenaTea, LLC' specifically. No Google Maps listing, Facebook page, Instagram account, or other channel returned evidenc_

## Regressed rows (baseline correct → iteration wrong)


### Row 535 — Overton's Grading, LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _experience.com listing shows current business hours (Thu/Fri 7AM-5PM, Sat 7AM-1PM) and contact phone (843) 312-2149 for Overtons Grading LLC in Ridgeville, SC; Syracuse University IVMF veteran directory lists overtonsgrading.com and owner Keith Overton as active._

### Row 413 — Granted Advocacy Partners, Inc. (GAP, Inc.)
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (85%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Charity Navigator shows Granted Advocacy Partners Inc. as an active 501(c)(3) organization with EIN 82-3291226, headquartered in Southlake, TX, with IRS ruling year 2018. Board of Directors page on standingap.com confirms Lisa Francis as CEO and Founder with 25+ years of community service. Organizat_

### Row 95 — Travel Halo
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (75%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _RocketReach profile lists Michael Vahey currently as Manager, Inventor, Entrepreneur at Travel Halo (no date but active listing as of 2026), ZoomInfo shows active company profile with phone and address, though website is dead and no recent social/marketplace activity found._

### Row 161 — CHAT Nature's Skin & Hair Co LLC
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (78%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Website https://chatshco.com loads with real products like Refine Cleanser priced at $24.99 and copyright 2026 footer, plus active Chatto Skin & Hair Care storefront at chatto.com selling Nature's Natural hair products._

### Row 126 — Enchanted Rose Floral
- Your label: **Likely Closed**
- Baseline AI: **Likely Closed** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Country Elegance Florists listed as participant in Petal It Forward 2025 event (SAF 2025 PDF) alongside other active CO florists, indicating current operation in Grand Junction despite password-protected 'Opening Soon' website._

### Row 624 — Casa Los Juanes
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (78%) ✗
- Iteration evidence: _The listed Airbnb URL (https://airbnb.com/rooms/36275724) returns only generic Airbnb navigation boilerplate with no business-specific content, product details, or listing information. Search results show only historical references to Joaneda House (a state-owned restaurant/wine shop at 57 Treasury _

### Row 97 — Tripoli Gift Company
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (50%) ✓
- Iteration AI: **Active** (85%) ✗
- Iteration evidence: _Website tripoligiftcompany.com loads with real product content (gift sets, military-themed gifts); founder Joe Winslow (22-year Marine Corps veteran) actively referenced in VA.gov news article as 'military gifts expert'; business listed on IVMF (D'Aniello Institute for Veterans and Military Families_

### Row 388 — Business Served
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **No Web Presence** (85%) ✗
- Iteration evidence: _Listed website https://businessserved.com shows only placeholder template text repeating 'Customized Human Resources Consulting and Professional Development Service' with no real business-specific content, products, or services; Google searches for 'Business Served' Charlotte return only generic pro_

### Row 451 — Secretariat Strategie LLC
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (75%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Active listings for Secretariat Strategie LLC on talents.vaia.com and dailyremote.com posting remote consultant job (current as of 2026), plus parent company secretariat-intl.com with detailed office locations and services including Fort Lauderdale-area reference._

### Row 176 — Norwood Natural's CBD
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (55%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Multiple cannabis directories including THCaNearby.com and cannabisshop.com list Norwood Natural's CBD as an active Indianapolis shop with reviews and store details (reviews from 2023+ implied by current listings), plus Manta and AiLOQ confirm physical address and veteran-owned operations with produ_

### Row 111 — CRSpices, ll
- Your label: **Uncertain**
- Baseline AI: **Uncertain** (72%) ✓
- Iteration AI: **Active** (95%) ✗
- Iteration evidence: _Listed Etsy shop URL etsy.com/shop/CRSpices qualifies as active storefront for product-based business per FAST PATH rules (Etsy /shop/ pattern indicates commerce presence with products available)._

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
- Iteration AI: **Likely Closed** (85%)

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
- Iteration AI: **No Web Presence** (75%)

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

### Row 538 — Spectra Cargo & Logistics, LLC
- Your label: **Likely Closed**
- Baseline AI: **Uncertain** (65%)
- Iteration AI: **Active** (85%)