# Human Labeling Protocol — IVMF Business Checker Eval

**Audience:** Julian Hernandez (sole labeler for BMOSG eval runs)
**Purpose:** Build a ground-truth dataset to measure how accurately the AI classifies veteran-owned business operational status. This dataset is what every future accuracy claim rests on — garbage in, garbage out.

---

## Goal

You are the ground truth. The AI made a prediction; you independently determine whether that prediction is correct by doing your own research. Your label is not an opinion about the AI — it is your independent assessment of whether the business is actually operating.

This dataset will be used to compute precision, recall, F1, and calibration curves. It will also identify systematic failure modes (e.g., the AI calls things "Active" when domain is expired). Quality of your labels directly determines the quality of that signal.

---

## The 4 Official Labels

Use exactly these values. The review app provides them as radio buttons.

### Active
The business is currently operational and serving customers.

Use when you find **at least two** of the following, dated within the **last 12 months**:
- A functional website with real product/service content (not a parked page or "coming soon")
- An active e-commerce store, booking system, or scheduling tool
- A verified Google Business Profile showing recent activity
- A recent social media post (Instagram, Facebook, LinkedIn) with business content
- A third-party directory listing (Yelp, BBB, chamber of commerce) with current contact info
- A news article, review, or event listing confirming current activity

**Exception — extend to 24 months only when one of the two signals is "hard evidence":** an e-commerce store with current stock and active checkout, an event calendar with future-dated events, or a course/booking page with future-dated availability. A 24-month-old Facebook post + a 22-month-old Yelp listing is **not** Active — that's two stale signals; treat as Uncertain.

**Do not use Active if** you find only a website that loads but has no products, no contact info, no indication of actual commerce.

**Edge cases — when you hit one, document your reasoning in the justification field and move on.** Examples that may come up: business rebranded under a new name, business sold to a non-veteran owner, dataset record has a typo or wrong city, owner deceased and family continues operating. Don't pre-stress these — pick a defensible call, write *why* in the justification, and we'll review the edge-case rows together at the end.

---

### Likely Closed
The business was real but shows strong signals of cessation.

**Critical principle: a dead website by itself is NOT enough.** Many small businesses let their domain lapse while continuing to operate through Facebook, Instagram, Google Maps, farmer's markets, or word of mouth. A dead domain is a *prompt to investigate other channels*, not a verdict.

Use **either** of these patterns:

**Pattern A — One unambiguous closure signal:**
- Website loads and displays "permanently closed," "no longer in business," or "thank you for X years"
- Google Business Profile shows "Permanently Closed"
- Yelp or Facebook page shows "Closed"
- Owner has publicly announced closure (news article, social post, LinkedIn update saying they moved on)

These are stand-alone — one is enough.

**Pattern B — Multiple weak signals (none alone sufficient, combined they're conclusive):**
- Dead website (expired, parked, DNS error, or 404) **AND**
- No active social media presence (Facebook/Instagram/LinkedIn either don't exist for this business or last post is 3+ years old) **AND**
- No active Google Business Profile or Yelp listing **AND**
- No marketplace presence for product businesses (Etsy/Amazon/Faire storefront missing or "currently unavailable" 6+ months) **AND**
- No recent news, press, or owner activity referencing the business

A dead domain *plus* an active Facebook with last post 4 months ago is **not** Likely Closed — that's a business that lost its website but is still operating. Label Active.

A dead domain *plus* zero other signals after thorough search is Likely Closed.

You do not need to prove closure — you need to have searched all the standard channels (per "Required Investigation" below) and come up empty on every one. If you didn't check Facebook/Instagram/Maps, you haven't earned Likely Closed yet.

---

### Uncertain
You found the business is real, but cannot determine current status from available sources.

Use when:
- Website loads but has no dates, no recent posts, no e-commerce, and you cannot verify activity
- Some channels suggest active, others suggest closed, with no way to reconcile
- Business is very new (founded within 6 months of today) with sparse online presence
- Sources conflict in a way you cannot resolve

Do **not** default here just because research is hard. Spend the full 5 minutes before choosing Uncertain.

---

### No Web Presence
The business has no verifiable online footprint at all.

Use when:
- Website URL is dead AND no Google results confirm the business exists
- No Google Business Profile, no social media pages, no directory listings
- The only thing tying the business name to the internet is the original IVMF dataset record

This label is rare. Most businesses have *something* online. If you find even one credible external reference, do not use this label.

---

### Unable to Determine (Reserve Use Only)

Use only when you genuinely cannot make a determination after 5 minutes of research AND the row has an ambiguity that more research could resolve (e.g., the business name is too generic to distinguish from many similar businesses). This label is excluded from all metrics — overusing it inflates your apparent accuracy by hiding hard cases.

**Hard limit:** No more than 10% of your labels should be Unable to Determine. If you are exceeding that, re-read the Uncertain label definition.

---

## Required Investigation Per Row

**Time box: 5 minutes.** Use a timer.

Check at minimum **2 independent sources** before labeling. Suggested order:

1. **Business website** — click the link in the app, verify it loads with real content
2. **Google search** — search the business name + city/state, look for Knowledge Panel, reviews, news
3. **Google Maps** — search the business name, check for profile and "Permanently Closed" flag
4. **Social media** — check Facebook (search for the page), Instagram, or LinkedIn if relevant to the business type
5. **Third-party directories** — Yelp, BBB, chamber of commerce, veteran-business registries

You do not need to check all five for every row. If the first two clearly answer the question, stop. If signals conflict, check more.

---

## Justification Requirement

Every label requires a justification of at least 10 characters. Write enough that someone reading it 6 months from now could reconstruct your reasoning.

**Good justification:** `Website loads with active e-commerce (adds to cart), Google Business Profile shows hours and 4.2 stars with recent reviews.`

**Bad justification:** `Active.` / `Website works.` / `Checked it.`

The justification field is how you catch your own mistakes when doing the session re-review (see Session Hygiene below). Short justifications make review impossible.

---

## Tie-Breaking Rules

These situations come up repeatedly. Follow the rule consistently.

### Live website vs. dead Google Maps listing
**Trust the website if** it has current product/service content (dated material, active shopping cart, recent blog post). Google Maps can be outdated. Label Active.

**Trust Google Maps "Permanently Closed" if** the website is also stale (no dates, no activity, no commerce). Label Likely Closed.

### Website loads but is a generic landing page (no products, no contact info)
Treat as Uncertain unless you find active commerce on a third-party platform (Etsy, Amazon, Faire). A domain that loads a blank template is not evidence of active operations.

### Business appears active on social media but website is dead
If the most recent post is within 12 months AND mentions active commerce (new products, events, orders), label Uncertain and note the split signal. Do not label Active on social alone unless the post explicitly says they are still taking orders and you see evidence of customer interaction.

### Website claims to be "under construction" or "coming soon"
Label Uncertain. It is not closed, but it is not actively serving customers.

### Conflicting reviews — some say open, some say closed
Check dates. If the most recent credible source (within 6 months) says closed, label Likely Closed. If the most recent says open and you can corroborate with a second source, label Active. If you cannot determine recency, label Uncertain.

### Marketplace-native businesses (sells only on Etsy / Amazon / Faire / Shopify)
Many veteran-owned product businesses don't run their own e-commerce site — they sell exclusively through marketplaces. Treat the marketplace presence itself as evidence-bearing:
- **Active listing with stock + recent reviews (within 12 months) = strong Active signal.** Even if the website is dead, an active Etsy or Amazon storefront with shipped orders proves operations.
- **Listing exists but products are "Currently unavailable" or store is "Vacation mode" for 6+ months = Uncertain.**
- **No listing on the marketplace they were known to use + no other channels = Likely Closed.**

For these businesses, the AI may incorrectly call them "Likely Closed" because the website is dead. Your job is to find the marketplace and verify.

### Food trucks, caterers, mobile / home-based services
These businesses typically have one strong channel (Instagram, Facebook, or a booking page) and very thin presence elsewhere. The standard "two channels" rule for Active is too strict. Override:
- **One strong channel with content within 6 months + active customer interaction (DMs answered, orders posted, events scheduled) = Active.**
- **One channel with last activity 6–24 months old, nothing more recent = Uncertain.**
- **Channel exists but has no commerce indicators (just photos, no orders/menu/booking) and no other signals = Uncertain, lean toward Likely Closed if 12+ months stale.**

Document in your justification: "Single-channel business; verified via [platform] activity dated [month/year]."

### E-commerce-only businesses (no physical location, online sales only)
Use the website + a third-party signal (BBB listing, marketplace storefront, customer reviews). Do NOT downgrade these for lacking a Google Maps listing — that's expected.

---

## Common Pitfalls

**Do not trust the AI's evidence directly.** The AI summary is a starting point, not a source. Verify independently. The entire point of this exercise is to find where the AI is wrong.

**Do not assume Active because a website exists.** Parked domains, expired sites served from cache, and "for sale" pages all look like functioning websites in a quick check. Click through to actual content.

**Do not use Likely Closed just because a business is hard to find.** Some legitimate small businesses have minimal online presence. If you cannot find them, check No Web Presence criteria. If they exist but you cannot assess status, use Uncertain.

**Do not rush past the 5-minute mark on a genuinely ambiguous case.** If you are oscillating between Active and Uncertain after 3 minutes, the 4th and 5th minutes often resolve it (or confirm you need to use Uncertain).

**Do not let the AI confidence score bias your label.** A 100% confidence prediction is as likely to be wrong as a 70% confidence prediction in the categories where the AI underperforms. Label what you find, not what the AI expects.

---

## Session Hygiene

**Splitting across days:** Labeling 80+ rows in one session degrades quality after the first 30–40. Split sessions at natural breaks (after 25–30 rows, or when your attention drops).

**Re-review the first 10 rows of each new session:** Before starting new labels, read through your first 10 from the previous session. Correct any labels that now look wrong after a break. This catches calibration drift (the tendency to be more lenient or strict as you go deeper into a session).

**One browser tab open for research:** Keep all your research in a single window. Multiple tabs for the same business can create confusion about which result belongs to which row.

**Do not label while fatigued.** Two hours of good labeling beats four hours of unreliable labeling. This dataset will be used to make real claims about system accuracy. Label quality is the bottleneck.

---

## Quick Reference Card

| Signal | Likely label |
|--------|-------------|
| Website loads + e-commerce + recent reviews | Active |
| Domain dead + no social + no GBP | Likely Closed or No Web Presence |
| GBP shows "Permanently Closed" | Likely Closed |
| Website loads but no content/dates | Uncertain |
| Social media only, last post 12 mo | Uncertain |
| Social media only, last post < 6 mo + orders | Active (use cautiously) |
| Website loads, products present, no other signals | Uncertain (verify 2nd source) |
| Completely unfindable + no external references | No Web Presence |
| You cannot distinguish from similarly-named businesses | Unable to Determine |

---

*Protocol version: 1.0 — April 2026. Revise after completing first full labeling session.*
