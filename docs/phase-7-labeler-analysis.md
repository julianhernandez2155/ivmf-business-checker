# IVMF Business Checker — Labeler Behavioral Analysis
## Dataset: bmosg_v1_eval_sample.csv (60 rows)
## Analyst: Claude Sonnet 4.6 | Date: 2026-04-28

---

## Preliminary: Agreement Rate

Before diving into sections, the overall landscape:

- **Total rows analyzed:** 60
- **Unable to Determine rows (excluded from disagreement analysis):** 2 (row 581 Coping Resources, row 258 L'aube Boutique)
- **Rows where predicted_status == human_label:** 38
- **Disagreements (after excluding UTD rows):** ~18 meaningful disagreements
- **Agreement on clearly active businesses:** high
- **Highest disagreement zone:** Uncertain ↔ Likely Closed boundary

---

## Section A — Labeler Patterns

### A1. What investigation methods does Julian rely on most?

Julian's investigation workflow is **visual-first, multi-channel, manual**. The pattern across justifications:

**Primary checks (used in >80% of rows):**
1. **Visual quality assessment of the website** — Julian consistently notes whether a website "looks high quality," is "colorful and lively," or is "low quality" as a pre-filter signal. Row 132 (Fundraiser Blankets): "Website is very colorful and lively. I tend to use this as an indicator of quality of the website." Row 484 (iFusion Concepts): "One caveat, the website is incredibly low quality, so i would be suspicious."
2. **Copyright year in footer** — Julian checks the footer for `© [year]` as a recency proxy. Row 132: "When you scroll to the bottom of the website it says © 2025, Birdy Boutique." Row 219 (27 West): "bottom of website indicates '© 2026, 27 West Powered by Shopify'." Row 223 (Assault Forward): "the bottom of the website it has '© 2026, Assault Forward Powered by Shopify'."
3. **Instagram check** — Julian navigates to Instagram and reads follower counts and last-post dates. Row 132 (Fundraiser Blankets): "their instagram is updated and active with 13.6k followers." Row 86 (Resin8 Art Savannah): "Their instagram is live and active with the last post 4 days ago." Row 94 (Mobile Cigar Lounge): "It's very active with over 15k followers and their last post was 1 day ago."
4. **Facebook check** — Julian searches Facebook and checks last post date. Row 95 (Travel Halo): "i did find the facebook at https://www.facebook.com/travelhalo# You just have to look up 'Travel Halo' and the last post was from 2020." Row 192 (365 Self-Defense): "i immediately found their facebook... their last post was 2023."
5. **Google Maps** — Julian checks for a Maps listing as a secondary confirmation. Row 12 (Burn Pit BBQ): "Pops up on google maps good." Row 161 (CHAT Nature's Skin & Hair): "no Google Maps listing" noted as closure signal.
6. **E-commerce functionality** — Julian manually clicks "Add to Cart" and checks checkout availability. Row 12 (Burn Pit BBQ): "you can add them to the cart and checkout." Row 86 (Resin8 Art Savannah): "there are clear product listings, that you can go and checkout."
7. **LinkedIn search with fallback** — Julian notes a consistent pattern: searching by "Business Name City State" fails on LinkedIn; searching by "Business Name" alone succeeds. This appears in rows 132, 12, 86, 217, 223.

**Secondary / situational checks:**
- **Owner LinkedIn profile** — Used for closed businesses to confirm departure dates. Row 410 (Force Multiplier Talent): "Went to ANDREW WEAVER (Andy Weaver) linkedin and saw Force Multiplier Talent logo... Oct 2018 - Dec 2024." Row 91 (Stars & Stripes Gifts LV): looked up "Gary Scaife" on LinkedIn to find founder status.
- **Google/owner name search** — Julian often appends owner name to disambiguate. Row 268 (One Fire Fight): "what i would do if nothing came up, is look up the owner, first name and last name." Row 578 (Weekend Navigators): "I looked up 'weekend navigators Monica Iannacone' which is the owners name."
- **Clicking through redirects** — Row 97 (Tripoli Gift Company): "going directly to 'https://www.tripoligiftcompany.com/' and it has a 'click here to go to our new website'."
- **Shopify Power indicator** — Julian notes "Powered by Shopify" as a quality/active signal. Row 219, 223, 685.
- **Physical promo content** — Row 349 (Devil Dog Brew): "on the first page they have a promotional video labeled 'Spring summer promo 26', confirmed by opening youtube and seeing it was posted 2 weeks ago."
- **AI-assisted synthesis** — Row 636 (SDVOSB Materials): Julian explicitly used Google Gemini to synthesize a complex website's content: "I had google gemini synthesize this summary while i was viewing the page."

---

### A2. Signals Julian Weights Heavily That AI Underweights

**1. Instagram activity / follower count as primary social proof**
The AI consistently relies on website content and directory listings, but Julian treats Instagram as a high-weight, fast-confirm signal. In multiple cases (rows 86, 94, 132, 556), a fresh Instagram post was the decisive signal. Row 556 (Spicers Nicer Massage Therapy): AI gave Uncertain (60) with no Instagram check; Julian found Facebook linking to website with a post 4 days ago → Active.

**2. Visual quality / "aliveness" of the website**
Julian explicitly states this is a strong signal (row 132). The AI cannot perceive website aesthetics, color saturation, product photography quality, or UI modernity. This is a structural gap — not something the AI can easily fix without vision capabilities.

**3. Copyright year in footer**
Simple, specific, and frequently decisive. AI could scrape this but often doesn't cite it. Row 219, 223, 132 all cite footer copyright year as confirmatory. When AI finds the same page, it doesn't cite the footer year.

**4. Owner LinkedIn employment dates as closure proof**
When a domain is dead, Julian looks up the founder by name and checks if "Force Multiplier Talent" or similar appears under Past Experience with an end date. Rows 410, 91, 578 all show this pattern. The AI never does this.

**5. Business-name-only social media search fallback**
Julian documents a consistent finding: LinkedIn and Facebook searches for "Business Name City State" fail, but "Business Name" alone succeeds. Julian adjusts for this manually (rows 132, 12, 86, 217, 223, 95, 192). The AI appears not to use this fallback strategy, leading to missed social media evidence.

**6. YouTube promotional content with upload dates**
Row 349 (Devil Dog Brew): Julian clicked through to YouTube and confirmed a video titled "Spring summer promo 26" was posted 2 weeks ago. AI found the same website but cited generic Perplexity-retrieved content without surfacing the YouTube recency.

---

### A3. Signals Julian Weights Lightly That AI Overweights

**1. Directory listings without dates**
AI frequently cites Manta, ZoomInfo, Yelp, etc. as evidence of activity. Julian rarely mentions these as meaningful. Row 562 (Back Office Administrators): "The website does look very generic... but then i went to the google maps." Julian validated the AI's directory evidence but only because Maps confirmed it — the directories themselves weren't persuasive.

**2. Federal contract records / SBA certifications as proof of active operations**
Row 527 (Universal Spartan): AI cited $2.8M+ in federal obligations, GSA contracts, SBA certification. Julian simply said "i agree with the evidence" — but in other cases (row 636 SDVOSB Materials), Julian noted the AI missed context from LinkedIn while accepting federal records. Federal records indicate legal entity status, not operational status.

**3. Third-party articles and media coverage without dates**
AI in several Uncertain cases cites press coverage or blog mentions without confirming the articles are recent. Row 286 (Sword & Plough): AI hedged at Uncertain (65) citing a Sustainable Brands article — but the article was "from at least several years ago." Julian correctly identified it as Likely Closed.

**4. Website content that "describes" services without operational proof**
Row 424 (JMCO Consulting): AI scored 100 confidence based on the website "loads with real, specific service descriptions." Julian disagreed: "I disagree with the evidence. That is not sufficient. The website is very barebones, only one page... no name of the person running the business, location, etc." The AI treats content existence as active proof; Julian requires human-traceable evidence.

---

### A4. Julian's Justification Quality

**Length:** Highly variable. Range: 4 words ("agree with the evidence") to 500+ words (row 636 SDVOSB Materials, row 85 Reflections of Service).

**Pattern by verdict type:**
- **Agreements (Active):** Short. Often 1-2 sentences: "i agree with the evidence" (rows 344, 527, 292, 699, etc.).
- **Agreements (Closed):** Short to medium. Sometimes adds the specific signal that confirmed closure (rows 87, 375, 413).
- **Disagreements:** Long. Julian explains what he found, how he searched differently, and why the AI missed it.
- **Uncertain cases:** Medium to long. Julian documents ambiguity explicitly, often suggesting follow-up.

**Specificity:** Julian is specific about dates (last post July 29, 2020), URLs (exact Facebook URLs), follower counts (13.6k, 16K), and exact search queries he used. This is investigative-quality documentation, not vague impressions.

**Depth pattern:** Julian escalates depth based on initial quality signals. Low-quality website → deep dive. High-quality website with functioning e-commerce → shorter justification.

---

### A5. How Julian Handles Ambiguous Cases

**Active vs. Uncertain boundary:**
- Julian tips toward **Active** when: there is recent social media activity (especially Instagram or Facebook within ~12 months), functioning e-commerce, and/or a copyright year in the current year.
- Julian tips toward **Uncertain** when: social media shows activity but not within 6 months, website exists but has no purchase mechanism, or there's a geographic mismatch that can't be resolved (row 258 L'aube Boutique: "GOOGLE MAP SETS THE LOCATION IN LEBANON SO I LITERALLY HAVE NO CLUE").

**Uncertain vs. Likely Closed boundary:**
- Julian tips toward **Likely Closed** when: the domain is dead AND the most recent social media post is >12 months old. Row 380 (A Simple Organizing): "non functional website parking page and last social media post was 2 years ago." Row 177 (Peachy Keen Perfume): "nice website but says coming soon and the last posts from any of their social medias was 2022."
- Julian keeps it **Uncertain** when: there is some recent signal (even just a profile update, <12 months) that warrants a direct follow-up call. Row 176 (Norwood Natural's CBD): "Last update on their facebook was Feb 2025 and they only updated their profile photo... google maps says their store is open. Would need to follow up directly."
- Julian tips toward **Uncertain** (from AI's Likely Closed) when: there is LinkedIn or Facebook activity within 12 months despite dead domain. Row 583 (Achieve New Heights): "the linkedin with... last post was 1 month ago. Same thing on the facebook, there are recent posts from 2025."

**Key threshold:** Julian's implied rule for Likely Closed is: **dead domain + no social media within ~12-18 months**. One recent social media signal overrides a dead domain and pulls it back to Uncertain.

**Unique category Julian added:** Row 125 (Emotion On Walls): AI said Likely Closed, Julian said **No Web Presence**. Julian distinguishes between "probably closed" and "never had a web presence / impossible to determine." Row 88 (SerenaTea): Same pattern — AI said Uncertain, Julian said No Web Presence.

---

### A6. Protocol Inconsistencies

**Inconsistency 1: Certain vs. Uncertain for active-but-thin businesses**
- Row 424 (JMCO Consulting): AI said Active (100), Julian said Active but wrote "this should likely be flagged as 'Uncertain' by the AI agent because it wouldn't be able to actually see the images." Julian labeled it Active but explicitly argued the AI's verdict was wrong for the wrong reasons — the business is active, but AI confidence of 100 was unwarranted given the evidence available to the AI.
- Row 314 (A Guide to Improvised Weaponry): AI said Likely Closed (85), Julian said Active. But Julian's justification says "It's not necessarily an active business, but it's also a place to buy stuff." This creates ambiguity — Julian may have labeled it Active primarily because the website has commerce functionality, even if it's a portfolio/personal brand site, not a traditional business.

**Inconsistency 2: Likely Closed vs. No Web Presence**
- Row 125 (Emotion On Walls): Julian says No Web Presence "because it doesn't come up on anything." AI said Likely Closed (75). In row 88 (SerenaTea), same logic. But in row 578 (Weekend Navigators), the AI also said Likely Closed and found nothing, yet Julian agreed with Likely Closed (not No Web Presence) because he found owner articles. The distinction between Likely Closed and No Web Presence seems to depend on whether ANY owner-linked content surfaces — but Julian doesn't document this rule explicitly.

**Inconsistency 3: Label application for deduplication case**
- Row 320 (Coping with Sexual Assault/MST) is an acknowledged duplicate of row 581 (Coping Resources — same URL, same owner). Julian labeled row 581 "Unable to Determine" and row 320 "Likely Closed" for the same underlying business. These should agree.

**Inconsistency 4: LinkedIn fallback search results influencing verdict asymmetrically**
Julian documents the LinkedIn city-state search failure pattern 5 times (rows 132, 12, 86, 217, 223) but only when agreeing with Active verdicts. He doesn't document whether the AI's failure to find LinkedIn evidence for Uncertain/Closed cases was also due to the same search query failure.

---

## Section B — Specific AI Failure Modes (Disagreement Rows)

Disagreements where `predicted_status != human_label`, excluding Unable to Determine rows.

---

```json
{
  "row_index": 271,
  "business_name": "Princess Leahs Designs",
  "ai_verdict": "Active",
  "julian_verdict": "Uncertain",
  "failure_bucket": "Marketplace-handling",
  "brief_explanation": "The AI cited the Etsy URL provided in the dataset, which is actually the owner's profile page (showing favorited items from other sellers), not her shop. The real shop is at a different Etsy URL (LCGJDesignsLLC). Even that shop has only 1 product listed and the most recent review was Dec 2023 — making Active unjustified.",
  "key_quote_from_julian": "The etsy link is valid and goes to Jessica Worley's etsy profile page. so the page it actually opens to shows her favorited items from other creators. This is one of those 'Uncertain' because it would either require the ai agent to dig deeper by clicking on her shop page link shown as 'LCGJDesignsLLC'."
}
```

```json
{
  "row_index": 85,
  "business_name": "Reflections of Service",
  "ai_verdict": "Active",
  "julian_verdict": "Uncertain",
  "failure_bucket": "URL-misinterpretation",
  "brief_explanation": "The AI cited the business website as loading with real content, but the website actually states 'At this time we are only bidding on/accepting orders for engraved drinkware; we are not accepting any new orders for custom woodcraft.' The AI presented a 'show me how to order' CTA as active commerce, when the page explicitly limits scope. Facebook last post was July 29, 2020 — 6 years ago. The AI cited only the website and didn't surface the social media recency failure.",
  "key_quote_from_julian": "Their last post was 'July 29th, 2020.' ... I would likely classify this as Uncertain because there's no indication of being able to actually actively purchase a product... and their last social media post was 6 years ago."
}
```

```json
{
  "row_index": 424,
  "business_name": "JMCO Consulting",
  "ai_verdict": "Active",
  "julian_verdict": "Active (but wrong evidence, should flag Uncertain)",
  "failure_bucket": "URL-misinterpretation",
  "brief_explanation": "AI cited YouTube videos and JMCO.com — which is an entirely different HR company (jmco.com/hr-solutions). The AI's cited evidence is not about this business at all. Julian found the real business via Facebook but noted the AI couldn't see the images proving it's a real person. AI confidence of 100 on wrong citations is a critical failure.",
  "key_quote_from_julian": "I disagree with the evidence. That is not sufficient. The website is very barebones, only one page... I found her facebook which would actually give us more evidence if we looked at the images... this should likely be flagged as 'Uncertain' by the AI agent because it wouldn't be able to actually see the images from the posts."
}
```

```json
{
  "row_index": 314,
  "business_name": "A Guide to Improvised Weaponry",
  "ai_verdict": "Likely Closed",
  "julian_verdict": "Active",
  "failure_bucket": "Single-channel-business",
  "brief_explanation": "This is a veteran's personal portfolio/brand site (Terry Schappert), not a traditional business with products. The AI correctly noted the 2015 book content but missed that the website is a living portfolio with commerce functionality. Julian classifies it Active because you can buy items from it, even if it's primarily informational.",
  "key_quote_from_julian": "THIS IS A VERY SPECIAL CASE THAT I HAVE NOT COME ACROSS BEFORE. This is basically a portfolio website for veteran terry schappert. It basically includes everything he's done, tv shows he's been apart of, books written, etc. It's not necessarily an active business, but it's stop to also buy stuff that he's created."
}
```

```json
{
  "row_index": 125,
  "business_name": "Emotion On Walls",
  "ai_verdict": "Likely Closed",
  "julian_verdict": "No Web Presence",
  "failure_bucket": "Dataset-quality",
  "brief_explanation": "The AI reached Likely Closed (75) but Julian's correct category is No Web Presence — an entirely different verdict. The business simply has no online footprint to evaluate. The AI's citations are all completely unrelated pages (TeachersPayTeachers, an art painting company, a children's lighthouse). This is a case where the dataset record itself may be a ghost entry.",
  "key_quote_from_julian": "I would say no web presence because it doesn't come up on anything."
}
```

```json
{
  "row_index": 88,
  "business_name": "SerenaTea LLC",
  "ai_verdict": "Uncertain",
  "julian_verdict": "No Web Presence",
  "failure_bucket": "Empty-builder-page",
  "brief_explanation": "AI reached Uncertain (75) because a Wix placeholder exists. Julian's correct classification is No Web Presence — the Wix placeholder is functionally equivalent to no presence. The AI treated the existence of a placeholder page as sufficient to warrant Uncertain rather than properly distinguishing between a placeholder and an actual web presence.",
  "key_quote_from_julian": "Agree with the evidence, no web presence though."
}
```

```json
{
  "row_index": 193,
  "business_name": "Alpha Outpost",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Hijacked-domain",
  "brief_explanation": "AI noted the domain was hijacked (spam/casino content) but hedged at Uncertain (65) because of third-party directory evidence of past existence. Julian went to Instagram directly from the archived/working website link and found a pinned message: 'Our store is permanently closed!' — a definitive closure signal the AI missed entirely.",
  "key_quote_from_julian": "So i went to their instagram from their website and it says 'Our store is permanently closed!'"
}
```

```json
{
  "row_index": 685,
  "business_name": "Basket and Beads Kenya",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Active",
  "failure_bucket": "Scraper-error",
  "brief_explanation": "AI reported the website showed a 'parking/coming soon page' with confidence 55. Julian went to the URL and found a fully functional Shopify storefront with © 2026 footer and add-to-cart functionality. The AI's web scraper appears to have fetched stale/cached content or a redirect page rather than the actual website. The evidence the AI acted on was simply wrong.",
  "key_quote_from_julian": "So the website does not show a parking page at all. It shows an active website, trademark at the bottom '© 2026, Baskets and Beads Kenya Powered by Shopify', ability to add to cart and purchase items. I don't know how it turned out a parking page."
}
```

```json
{
  "row_index": 556,
  "business_name": "Spicers Nicer Massage Therapy",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Active",
  "failure_bucket": "Single-channel-business",
  "brief_explanation": "The business website IS its Facebook page — this is a Facebook-primary business. AI gave Uncertain (60) because it found no recent activity dates on Facebook, only 2022 press. Julian clicked the website link within the Facebook page and found an actual website, plus a Facebook post from May 1st (4 days prior to review). The AI stopped at the Facebook page level rather than following the outbound website link.",
  "key_quote_from_julian": "Definitely still active. Though it's only a facebook page, their facebook page has a link to their actual website, and their last post on facebook was 4 days ago on May 1st."
}
```

```json
{
  "row_index": 114,
  "business_name": "Disgruntled Decks",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Active",
  "failure_bucket": "Marketplace-handling",
  "brief_explanation": "AI found only 2017 press coverage and a website that 'lacks specifics like pricing' — Uncertain (50). Julian went to the Shop tab, clicked a product, and followed the redirect to Amazon where the product is actively listed for sale. The AI failed to follow the commerce flow from the website to its external marketplace.",
  "key_quote_from_julian": "Definitely active. They don't have any real pricing, but they have active links that redirect to their amazon products. If you click on the Shop tab, then click on one of their products, and wait for it to load to amazon, you will see them."
}
```

```json
{
  "row_index": 583,
  "business_name": "Achieve New Heights LLC",
  "ai_verdict": "Likely Closed",
  "julian_verdict": "Uncertain",
  "failure_bucket": "Missed-channel",
  "brief_explanation": "AI found dead website (parking page), correctly flagged it as Likely Closed (75). Julian searched LinkedIn without city/state modifiers and found posts from 1 month ago, plus Facebook posts from 2025. Recent social media activity on a dead-domain business warrants Uncertain, not Likely Closed. AI failed to find active social media channels.",
  "key_quote_from_julian": "going to the linkedin with 'Achieve New Heights' instead of 'Achieve New Heights, LLC San Antonio Texas' shows the last post was 1 month ago. Same thing on the facebook, there are recent posts from 2025. This would definitely be uncertain and need a follow up."
}
```

```json
{
  "row_index": 258,
  "business_name": "L'aube Boutique",
  "ai_verdict": "Likely Closed",
  "julian_verdict": "Unable to Determine",
  "failure_bucket": "Missed-channel",
  "brief_explanation": "AI found DNS failure on website and concluded Likely Closed (85) with high confidence. Julian found a clearly active Instagram with a post 3 days prior, and an active Google Maps listing — but the Maps location showed Lebanon (geographic anomaly). AI missed Instagram entirely and didn't check Google Maps. This is classified as Unable to Determine due to the geographic impossibility, but it's clearly not Likely Closed.",
  "key_quote_from_julian": "I disagree. So there's no web presence but there is a clearly active instagram with the latest post literally 3 days ago. There is also an active google maps. HOWEVER THE GOOGLE MAP SETS THE LOCATION IN LEBANON SO I LITERALLY HAVE NO CLUE."
}
```

```json
{
  "row_index": 470,
  "business_name": "TTG Properties",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Empty-builder-page",
  "brief_explanation": "AI gave Uncertain (55) because the Wix site has real estate development descriptions. Julian classified Likely Closed because the website is a generic Wix template with no business owner name in the dataset and no distinguishing content.",
  "key_quote_from_julian": "I disagree. Looks like a general website. No business owner name was provided in the dataset on top of it being a generic website."
}
```

```json
{
  "row_index": 177,
  "business_name": "Peachy Keen Perfume",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Pattern-B-hesitancy",
  "brief_explanation": "AI gave Uncertain (65) because a Wix backup site had business content (founder name, product descriptions) even though the primary domain was a 'coming soon' parking page. Julian went to social media and found last posts from 2022 — combined with the dead primary domain, this tips to Likely Closed, not Uncertain. The AI treated the presence of any active-seeming content as a reason to hedge rather than close the case.",
  "key_quote_from_julian": "Probably closed. nice website but says coming soon and the last posts from any of their social medias was 2022."
}
```

```json
{
  "row_index": 380,
  "business_name": "A Simple Organizing & Moving Company LLC",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Pattern-B-hesitancy",
  "brief_explanation": "AI gave Uncertain (55) because an FMCSA carrier profile existed with a current DOT number, treating a regulatory registration as an activity signal. Julian found parking page + last social media post 2 years ago → Likely Closed. FMCSA registration doesn't prove operational status.",
  "key_quote_from_julian": "Probably closed. non functional website parking page and last social media post was 2 years ago."
}
```

```json
{
  "row_index": 163,
  "business_name": "Dashfire Beards",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Pattern-B-hesitancy",
  "brief_explanation": "AI gave Uncertain (55) because an Alignusapp directory listing existed. Julian agreed the evidence supports Likely Closed — there was no reason to hedge at Uncertain when the only evidence was a single old directory listing and a parking page.",
  "key_quote_from_julian": "I think it's likely closed based off all the evidence."
}
```

```json
{
  "row_index": 680,
  "business_name": "Bundook",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Pattern-B-hesitancy",
  "brief_explanation": "AI gave Uncertain (55) because a 2024 IVMF directory listing existed alongside a 'coming soon' password-protected website. Julian noted that being in the IVMF directory with a never-deployed website for 2+ years is a closure signal, not an active signal.",
  "key_quote_from_julian": "Probably likely closed. Coming soon website with a listing on IVMF probably means in the past 2 year they never deployed and are probably closed."
}
```

```json
{
  "row_index": 286,
  "business_name": "Sword & Plough",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Stale-recency-acceptance",
  "brief_explanation": "AI hedged at Uncertain (65) citing a Bespoke Edge interview and Sustainable Brands article — both undated/old — plus a dead website. Julian examined social media: last Facebook post 2022, dead website, all evidence pre-2023. Multiple stale signals should have tipped to Likely Closed.",
  "key_quote_from_julian": "Their website is dead, their last facebook post was 2022 and all your other evidence points to no activity. I think it's most likely closed."
}
```

```json
{
  "row_index": 538,
  "business_name": "Spectra Cargo & Logistics LLC",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Pattern-B-hesitancy",
  "brief_explanation": "AI gave Uncertain (65) citing ZoomInfo, Indeed employee reviews (undated/pre-2022), and an FMCSA record for a different entity in a different city. Julian: 'No evidence of current operations.' Multiple weak signals without any recency proof should resolve to Likely Closed, not Uncertain.",
  "key_quote_from_julian": "No evidence of current operations."
}
```

```json
{
  "row_index": 31,
  "business_name": "King's Coffee LLC",
  "ai_verdict": "Uncertain",
  "julian_verdict": "Likely Closed",
  "failure_bucket": "Pattern-B-hesitancy",
  "brief_explanation": "AI gave Uncertain (55) because FedLinks and Eventeny listings existed. Julian found the Facebook page — last post July 2024 (>10 months) + non-functional website = Likely Closed, not Uncertain. The AI flagged old directory entries without checking actual social media recency.",
  "key_quote_from_julian": "I'm gonna mark it as likely closed because i was able to find their facebook, but their last post was from july 2024 and their website is not functional."
}
```

---

## Section C — Confidence vs. Correctness Analysis

### Band: 50–59 (Low confidence)
**Total rows in band:** 10  
Row indices: 97 (50), 685 (55), 31 (55), 470 (55), 380 (55), 163 (55), 680 (55), 114 (50), 556 (60), 176 (55)

**Agreed with Julian:** ~5 (rows 97 Uncertain→Uncertain, 176 Uncertain→Uncertain, 31 Uncertain→[Julian says Likely Closed - disagree], 470 Uncertain→[Likely Closed - disagree], 163 Uncertain→[Likely Closed - disagree])

More precisely:
- Row 97 (Tripoli Gift Company): Uncertain→Uncertain ✓
- Row 176 (Norwood Natural's CBD): Uncertain→Uncertain ✓  
- Row 470 (TTG Properties): Uncertain→Likely Closed ✗
- Row 380 (A Simple Organizing): Uncertain→Likely Closed ✗
- Row 163 (Dashfire Beards): Uncertain→Likely Closed ✗
- Row 680 (Bundook): Uncertain→Likely Closed ✗
- Row 114 (Disgruntled Decks): Uncertain→Active ✗ (large miss)
- Row 556 (Spicers Nicer Massage): Uncertain→Active ✗ (large miss)
- Row 685 (Basket and Beads Kenya): Uncertain→Active ✗ (large miss, scraper error)
- Row 31 (King's Coffee): Uncertain→Likely Closed ✗

**Agreement rate: ~2/10 (20%)**  
**Pattern:** The AI's low-confidence Uncertain calls are systematically the wrong direction — it's not just uncertain, it's usually wrong. 7/10 disagreements in this band are Uncertain → should-be-Closed or Uncertain → should-be-Active. The low confidence is warranted but the reasoning is weak. Missing channels (Instagram, Facebook with name-only search) and marketplace navigation (Amazon links) are the primary drivers.

---

### Band: 60–69 (Below-average confidence)
**Total rows in band:** 6  
Row indices: 193 (65), 286 (65), 538 (65), 451 (75 — actually above), 258 (75 — above band)

Correcting: rows with 60-69:
- Row 556 (60) — in band above actually
- Row 193 (65): Uncertain→Likely Closed ✗
- Row 286 (65): Uncertain→Likely Closed ✗
- Row 538 (65): Uncertain→Likely Closed ✗
- Row 451 (75): out of band

Let me recalibrate by actual values from the data:

**60-69 band rows:** 193 (65), 286 (65), 538 (65), 424 (100-out), 556 (60)
- Row 193 (Alpha Outpost, 65): Uncertain→Likely Closed ✗
- Row 286 (Sword & Plough, 65): Uncertain→Likely Closed ✗
- Row 538 (Spectra Cargo, 65): Uncertain→Likely Closed ✗
- Row 556 (Spicers Nicer Massage, 60): Uncertain→Active ✗

**Agreement rate: ~1/5 (20%)**  
**Pattern:** Same as 50-59 band — the AI consistently hedges Uncertain when the evidence (or lack of it) should tip Likely Closed. The 60-69 band shows the same Pattern-B-hesitancy failure mode but with slightly more confidence in being uncertain.

---

### Band: 70–79 (Average confidence)
**Total rows in band:** Rows with 70-79:  
Row 97 (50-out), 375 (72), 258 (75), 581 (75), 583 (75), 87 (75), 192 (75), 455 (75), 95 (75), 578 (75), 268 (75), 410 (75), 91 (75), 18 (78), 161 (78), 349 (75 — this is 95 actually)

Corrected 70-79 rows from the data:
- Row 375 (Chosun4u, 72): Likely Closed→Likely Closed ✓
- Row 581 (Coping Resources, 75): Likely Closed→Unable to Determine (excluded)
- Row 258 (L'aube Boutique, 85 — out of band)
- Row 87 (Saltwater & Sand, 75): Likely Closed→Likely Closed ✓
- Row 192 (365 Self-Defense, 75): Likely Closed→Likely Closed ✓ (but wrong evidence)
- Row 455 (SMB Coaching, 75): Likely Closed→Likely Closed ✓
- Row 95 (Travel Halo, 75): Likely Closed→Likely Closed ✓ (but AI missed Facebook)
- Row 268 (One Fire Fight, 75): Likely Closed→Likely Closed ✓
- Row 410 (Force Multiplier Talent, 75): Likely Closed→Likely Closed ✓
- Row 91 (Stars & Stripes Gifts LV, 75): Likely Closed→Likely Closed ✓
- Row 583 (Achieve New Heights, 75): Likely Closed→Uncertain ✗
- Row 18 (Deep Sea Salt, 78): Likely Closed→Likely Closed ✓
- Row 161 (CHAT Nature's Skin, 78): Likely Closed→Likely Closed ✓
- Row 111 (CRSpices, 72): Uncertain→Uncertain ✓
- Row 602 (Griggsgear.com, 72): Uncertain→Uncertain ✓

**Agreement rate: ~13/15 (87%)** — the 70-79 confidence band is highly accurate for Likely Closed verdicts.  
**Disagreements in this band:** Row 583 (Achieve New Heights) — AI missed active social media channels behind the dead domain.

---

### Band: 80–89 (High confidence)
**Total rows in band:**
- Row 535 (Overton's Grading, 85): Likely Closed→Likely Closed ✓ (different reasoning)
- Row 413 (Granted Advocacy Partners, 85): Likely Closed→Likely Closed ✓
- Row 258 (L'aube Boutique, 85): Likely Closed→Unable to Determine ✗
- Row 314 (A Guide to Improvised Weaponry, 85): Likely Closed→Active ✗
- Row 177 (Peachy Keen Perfume, 65 — out of band)

Corrected 80-89 band:
- Row 535 (Overton's Grading, 85): ✓
- Row 413 (Granted Advocacy Partners, 85): ✓  
- Row 258 (L'aube Boutique, 85): ✗ (missed Instagram)
- Row 314 (A Guide to Improvised Weaponry, 85): ✗ (wrong business type classification)

**Agreement rate: ~2/4 (50%)**  
**Pattern:** The AI's high-confidence Likely Closed calls in the 80-89 band have notable failures. Both failures involve missed channels: Instagram (L'aube Boutique) and misclassification of business type (portfolio site vs. closed business for Terry Schappert).

---

### Band: 90–100 (Maximum confidence)
**Total rows in band:** Most Active verdicts — rows 132 (100), 12 (95), 219 (100), 86 (95), 636 (95), 217 (100), 527 (95), 85 (100), 349 (95), 562 (95), 223 (100), 344 (95), 228 (100), 424 (100), 292 (100), 699 (95), 484 (97), 589 (100), and others.

- Row 132 (Fundraiser Blankets, 100): Active→Active ✓
- Row 12 (Burn Pit BBQ, 95): Active→Active ✓
- Row 219 (27 West, 100): Active→Active ✓
- Row 86 (Resin8 Art Savannah, 95): Active→Active ✓
- Row 636 (SDVOSB Materials, 95): Active→Active ✓
- Row 217 (ViTAC Solutions, 100): Active→Active ✓
- Row 527 (Universal Spartan, 95): Active→Active ✓
- Row 85 (Reflections of Service, 100): **Active→Uncertain ✗**
- Row 349 (Devil Dog Brew, 95): Active→Active ✓
- Row 562 (Back Office Admin, 95): Active→Active ✓
- Row 223 (Assault Forward, 100): Active→Active ✓
- Row 344 (Black Ink Coffee, 95): Active→Active ✓
- Row 228 (Blue Ribbon Buckle, 100): Active→Active ✓
- Row 424 (JMCO Consulting, 100): Active→Active (but wrong reasoning, flagged as should-be-Uncertain)
- Row 292 (TJL Collection, 100): Active→Active ✓
- Row 699 (Cornhole and More, 95): Active→Active ✓
- Row 484 (iFusion Concepts, 97): Active→Active ✓
- Row 589 (Matt Webb Design, 100): Active→Active ✓
- Row 271 (Princess Leahs Designs, 95): **Active→Uncertain ✗** (Marketplace-handling)
- Row 94 (Mobile Cigar Lounge, 95): Active→Active ✓
- Row 126 (Enchanted Rose Floral, 72 — out of band)

**Agreement rate: ~17/21 (81%)**  
**Pattern:** At 90–100 confidence, Active verdicts are largely correct. The two disagreements are:
1. Row 85 (Reflections of Service, 100): AI interpreted a website describing limited service as "active commerce" — overconfident on weak e-commerce signals.
2. Row 271 (Princess Leahs Designs, 95): AI cited wrong Etsy URL type (profile page vs. shop page) — a Marketplace-handling failure at maximum confidence. This is the most dangerous type of error: high confidence, wrong answer, wrong evidence.

---

## Section D — Business Domain Patterns (Veteran-Owned Business Insights)

### D1. Business Types Most Likely to Be Misclassified

**1. Personal brand / portfolio businesses (not traditional product businesses)**
Row 314 (A Guide to Improvised Weaponry — Terry Schappert): This is a veteran TV personality with a portfolio site that also has commerce functionality. It doesn't fit standard business categories. The AI sees "2015 book content, no recent updates" and concludes Likely Closed. Julian sees a living portfolio with embedded commerce. **The AI's prompt has no category for "veteran celebrity/author/personality brand site."**

**2. Service businesses with no online purchase mechanism**
Row 85 (Reflections of Service): Engravings/drinkware made-to-order, contact-based ordering only. Row 424 (JMCO Consulting): One-page consulting site with no contact details. Row 388 (Business Served): Generic HR consulting placeholder. The AI overweights e-commerce features as an Active signal — businesses that operate contact-first don't have carts and the AI interprets this as lower confidence when it shouldn't.

**3. Facebook-primary or Instagram-primary businesses**
Row 556 (Spicers Nicer Massage Therapy): The listed "website" is literally a Facebook page URL. Row 685 (Basket and Beads Kenya): Instagram-primary with Shopify backend. Single-channel social businesses confuse the AI because it treats social profiles as secondary evidence, not primary commerce channels. These businesses may never have a standalone website.

**4. Airbnb / rental businesses registered as veteran businesses**
Row 624 (Casa Los Juanes): An Airbnb listing registered as a veteran business. The AI correctly flagged Uncertain but Julian confirmed: "this is a veteran who listed their airbnb property for anyone to register and enjoy" — it may not be a business at all. The BMOSG dataset apparently includes veterans who listed rental properties as businesses.

**5. CPG / food businesses operating through retail partners**
Row 344 (Black Ink Coffee): Sells through retail partners, not direct e-commerce. The AI correctly identified active, but these businesses often have minimal websites because their commerce is retail-B2B. They're vulnerable to misclassification if their retail partner pages aren't indexed.

**6. SDVOSB government contractors**
Rows 636 (SDVOSB Materials), 527 (Universal Spartan), 484 (iFusion Concepts): These businesses don't sell consumer products — they're government contractors who may have websites that look "thin" in consumer terms. The AI did well on these because it found federal contracting records, but Julian noted that the AI missed LinkedIn for row 636.

---

### D2. Industry-Specific Patterns

**Tactical/military gear and apparel:** Rows 228 (Blue Ribbon Buckle), 223 (Assault Forward), 217 (ViTAC Solutions) — these are typically active, have Shopify stores, and the AI handles them well.

**Coffee/food/CPG:** Rows 12 (Burn Pit BBQ), 344 (Black Ink Coffee), 349 (Devil Dog Brew) — high agreement, AI handles well. These businesses invest in web presence.

**Books/media/publishing:** Row 314 (A Guide to Improvised Weaponry), Row 581/320 (Coping Resources / Sugati Publications) — misclassified. Publishing businesses, especially niche veteran-authored books, may have old-looking websites that are still selling. The AI treats 2015 content as a closure signal.

**Beauty/personal care:** Row 86 (Resin8 Art Savannah), Row 176 (Norwood Natural's CBD), Row 177 (Peachy Keen Perfume), Row 163 (Dashfire Beards) — several closures/ambiguities in this category. These are often solo-founder side hustles with low web investment.

**Real estate/home services:** Row 470 (TTG Properties), Row 380 (A Simple Organizing) — generic builder templates are the norm, making it hard to distinguish real from dead.

**Craft/handmade marketplace sellers:** Rows 271 (Princess Leahs Designs), 111 (CRSpices), 86 (Resin8 Art Savannah) — Etsy-native businesses are systematically risky for the AI because Etsy URL structures (profile vs. shop vs. listing) are non-obvious.

---

### D3. Geographic Patterns

Observed but not statistically conclusive (small n):
- Several closed businesses cluster in Texas (rows 583 Achieve New Heights, 470 TTG Properties, 380 A Simple Organizing, 292 TJL Collection active). Texas is heavily represented in the dataset.
- Businesses in smaller markets (Armada MI, Firebaugh CA, Littleton CO) appear more likely to be active niche/specialty businesses with real web investment.
- Urban businesses (Chicago, Dallas, Charlotte) appear more likely to show generic builder templates.

---

### D4. Founder-Archetype Patterns

**Single-founder side-hustles:**
Row 86 (Resin8 Art Savannah): "I'm thinking this could be a like a side hustle type website/business." Row 271 (Princess Leahs Designs): Etsy-only, single product. Row 163 (Dashfire Beards): parking page, no social presence. These businesses have minimal web investment and are more likely to quietly close without formal announcement.

**Retired founders / founder departure:**
Row 410 (Force Multiplier Talent): Founder LinkedIn shows end date Dec 2024 — clear departure signal. Row 91 (Stars & Stripes Gifts LV): Founder changed business name entirely (HELP R HEROES). This archetype — veteran founder who rebrands or pivots without closing the original entity — creates ghost records in the BMOSG dataset.

**Female veteran founders with home-based businesses:**
Rows 581/320 (Coping Resources): "woman-veteran owned business offering publications on coping and trauma nationwide for over 20 years." Rows 562 (Back Office Administrators — Michelle McDaniel), 388 (Business Served), 424 (JMCO Consulting). These businesses often have minimal web presence, use personal name as business contact, and are contact-first rather than e-commerce.

**Multi-entity veterans (franchise operators, rebranders):**
Row 91 (Stars & Stripes Gifts LV): Founder rebranded to "HELP R HEROES." Row 320/581 duplicate: business renamed from Sugati Publications to Coping Resources to copingresources.com. Julian identified both as dataset deduplication problems.

---

## Section E — What Julian's Notes Reveal About the Tool Itself

### E1. Where the AI's Evidence-Gathering Process Broke

**1. Social media search uses city+state which fails on Facebook and LinkedIn**
This is the single most documented process failure across the entire dataset. Julian notes it explicitly in rows 132, 12, 86, 217, 223 — and by extension in all the Missed-channel failures where AI found no social presence. The AI searches "Business Name City State" on LinkedIn/Facebook, gets no results, and concludes no social presence. The correct behavior is fallback to "Business Name" only.

**2. Web scraper fetched stale/cached content instead of live page**
Row 685 (Basket and Beads Kenya): Julian found a live Shopify store; the AI reported a "coming soon" page. The Perplexity sonar API may be returning cached snapshots or the scraper hit a CDN edge case. This is an infrastructure-level reliability problem.

**3. Marketplace navigation stops at the product page URL without following redirects**
Row 271 (Princess Leahs Designs): The dataset URL points to an Etsy profile page (shows favorited items), not the shop. Row 114 (Disgruntled Decks): The website links externally to Amazon, but the AI didn't follow the Shop tab's redirect. The AI needs to follow commerce flows, not just validate the landing URL.

**4. AI cannot perceive website visual quality**
Row 132 explicitly notes this limitation. Julian uses visual quality as a pre-filter — a colorful, professional, modern design signals investment and ongoing activity. The AI has no visual capability and cannot distinguish a $5,000 Shopify build from a 2013 WordPress template.

**5. AI cited wrong entity's website for JMCO Consulting (row 424)**
The AI cited jmco.com/hr-solutions — a completely different HR company — as evidence. This is a prompt/search contamination: the search returned a stronger-authority URL for a different entity with a similar abbreviation. The AI needed to verify the citation matched the specific business in question.

**6. AI accepted FMCSA/regulatory records as operational evidence**
Row 380 (A Simple Organizing): FMCSA carrier profile with active DOT# was treated as operational evidence. But DOT numbers are never canceled — they persist even for defunct carriers. Row 484 (iFusion Concepts): Julian noted "the website is incredibly low quality, so i would be suspicious. I don't know if the ai could even pick up on that, but if the other indicators are good for active, especially sunbiz, then i feel like it's probably fine." State registration databases (Sunbiz, SBA certifications) confirm legal entity status, not operational status.

---

### E2. What the AI Was Given That Misled It

**1. Parking pages that the AI classified as business content**
Rows 455 (SMB Coaching), 583 (Achieve New Heights), 88 (SerenaTea): The AI flagged these correctly as "coming soon" or "parking" pages. But in row 685 (Basket and Beads), the AI was given a parking page when the real site was active — suggesting the AI can't reliably distinguish "I fetched a parking page for a live site" from "this site IS a parking page."

**2. Etsy profile URLs that aren't shop URLs**
Row 271 (Princess Leahs Designs): The URL in the dataset is `/people/PrincessLeahDesigns` (profile page), not `/shop/PrincessLeahDesigns` (shop page). The AI didn't detect this structural difference. Etsy profile pages look like valid business presence but show only favorited items.

**3. Wix/web builder sub-pages with real content but no commerce**
Row 177 (Peachy Keen Perfume): `peachykeenperfume.wixsite.com/peachykeenperfume` had real founder info and product descriptions but no cart. The AI weighted this content as an Active signal when it's a website-builder draft, not a live business.

**4. Old press/media coverage without dates**
Rows 286 (Sword & Plough), 314 (A Guide to Improvised Weaponry): Articles from "several years ago" without explicit dates were used as evidence of current operation. The AI needs to verify publication dates, not just existence of coverage.

**5. Dataset URL for a dead subsidiary of a renamed/rebranded business**
Row 91 (Stars & Stripes Gifts LV): The listed domain is a parking page, but the founder rebranded to "HELP R HEROES." Row 97 (Tripoli Gift Company): The listed domain redirects to the owner's new website. The AI didn't follow the redirect.

---

### E3. Search Query Patterns That Would Help the AI

From Julian's notes, the following query reformulations would improve results:

1. **LinkedIn/Facebook fallback:** When "Business Name City State" returns no results, retry with "Business Name" only. Julian documents this 5+ times.

2. **Owner name search for closures:** When a domain is dead and no social media found under the business name, search "[Owner First Name] [Owner Last Name] [Business Name]". Julian used this for rows 410, 91, 578, 268. This surfaces LinkedIn employment history (with end dates) and owner articles.

3. **Direct URL path traversal for Etsy:** When given an Etsy `/people/` URL, also fetch the `/shop/` URL for the same handle.

4. **Footer copyright year extraction:** When scraping a website, explicitly extract and return the footer copyright year. Julian uses this as a high-confidence recency signal (rows 132, 219, 223).

5. **Follow outbound commerce links:** When a website has a "Shop" or "Buy" link that points to an external marketplace (Amazon, Etsy), follow it and verify the listing exists and has recent activity.

6. **Instagram as first-check social channel (before Facebook/LinkedIn):** Julian finds Instagram most informative — recent posts, follower counts, and critically, pinned announcement posts like "Our store is permanently closed!" (row 193 Alpha Outpost). Instagram should be checked first, not last.

7. **Full business name variants:** Row 636 (SDVOSB Materials): Julian searched by the full registered name "SDVOSB Materials, Technology & Supply LLC" to find LinkedIn. Row 132 (Fundraiser Blankets): Julian switched from "Fundraiser Blankets® Armada Michigan" to "Fund Raiser Blankets" to find LinkedIn. The AI should try multiple name variants.

8. **Cross-reference URL domains for deduplication:** Row 320/581 (Coping Resources / Sugati Publications): Same URL, different business names. Julian suggests using URL as a deduplication key across the dataset to surface renamed businesses.

---

## Summary: Priority Fixes by Impact

| Priority | Fix | Evidence |
|----------|-----|---------|
| P1 | Social media search: add name-only fallback when city+state yields no results | Documented in 5+ rows; drives multiple Missed-channel failures |
| P2 | Instagram first-check: prioritize Instagram before LinkedIn/Facebook | Rows 86, 94, 132, 193, 556 — Instagram most informative for recency and closure announcements |
| P3 | Footer copyright year extraction: add explicit scrape step | Rows 132, 219, 223 — Julian's highest-confidence recency signal |
| P4 | Etsy URL normalization: distinguish /people/ vs /shop/ URLs | Row 271 — false Active at 95 confidence on wrong Etsy URL |
| P5 | Pattern-B threshold calibration: dead domain + no social activity in 12+ months = Likely Closed, not Uncertain | Rows 286, 380, 163, 680, 538, 31 — all Pattern-B hesitancy failures |
| P6 | Owner name search for dead-domain cases | Rows 410, 91, 578, 268 — founder LinkedIn end dates are definitive closure signals |
| P7 | Regulatory record handling: FMCSA/DOT/SBA = legal status, not operational status | Row 380 — DOT# ≠ active carrier |
| P8 | Scraper reliability check: verify fetched content is live (not cached/parking) | Row 685 — scraper returned parking page for live Shopify store |
