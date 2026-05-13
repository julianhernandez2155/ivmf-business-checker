# Iter 14 — adjudicator smoke test

**Generated:** 2026-05-13 14:48:41
**Model:** `claude-sonnet-4-6`
**Predictions source:** `eval/reports/iter14_phase0/predictions_pass1.csv`
**Rows tested:** 3

## Results

| row_index | name | human label | Perplexity verdict | Adjudicator verdict | Match? |
| ---: | --- | --- | --- | --- | --- |
| 12 | Burn Pit BBQ | Active | Active | Active (72) | ✅ |

**Adjudicator evidence for row 12:** Perplexity prose reports the website functional with e-commerce and products (May 2026) and a Facebook post from May 12, 2026, plus listings on WisconsinMade and Wisconsin Veterans Chamber of Commerce. However, the structured own_website_scrape failed to gather data and facebook_signal is null, so these signals come entirely from perplexity_prose, which is treated as one signal among many and cannot be independently verified from structured evidence.

| 18 | Deep Sea Salt Company | Likely Closed | Likely Closed | Likely Closed (82) | ✅ |

**Adjudicator evidence for row 18:** Own website (deepseasaltco.com) is unreachable with a DNS/connection error indicating domain expiration; no Facebook or Instagram signals present; all citation hits are either unrelated businesses or a stale ZoomInfo aggregator record with no content — meeting the dead-website + no-FB + all-residue closure pattern.

| 85 | Reflections of Service | Uncertain | Uncertain | Uncertain (40) | ✅ |

**Adjudicator evidence for row 85:** The own_website_scrape returned reachable=false with no text gathered (smoke test error), so the website cannot be confirmed live. Citation hits are all from reflectionsofservice.com subpages and one directory link, but none have snippets or scraped text to confirm content. Perplexity prose describes an Oak Harbor, WA business while the queried entity is Camden, NY — a critical location mismatch that prevents confirming this is the same business. No Facebook or Instagram signals present.


**Match rate vs. Perplexity:** 3/3

Note: the adjudicator is intentionally working from minimal evidence (no website scrape, no FB signal). A real A1 run would have those signals; this smoke test only verifies the prompt parses real Perplexity outputs and returns valid JSON.