# Phase 3 — Bug Squash + Program Verification

**Date:** 2026-04-30
**Outcome:** ✅ Complete — no blocker bugs
**Tag:** `phase-3-verified`

## Layer 1 — Test suite

`cd business_checker && python3 -m pytest -q` → **90 passed in 0.43s** ✓

All 4 CI matrix combinations green (Ubuntu/macOS × Python 3.11/3.12) at commit `68e75e2` and beyond.

## Layer 2 — Smoke runs on real BMOSG data

### First smoke run (10 rows, fresh)
```
python3 run_checker.py --input ../data/BMOSG_All_Businesses.xlsx --workers 1 --limit 10
```

| Metric | Value |
|---|---|
| Rows processed | 10 |
| Wall time | ~41s (4.1s/row, single worker) |
| Total cost | $0.0735 ($0.0073 avg/check) |
| Errors | 0 |
| Tracebacks | 0 |
| Status distribution | Active: 10 |

All 10 came back Active because BMOSG is alphabetically sorted and rows 1–10 happen to all be currently operating businesses (Agoge Life, And I Like It, Anthem Snacks, …). Notable: **Bomb Azz Lemonade (row 9)** — the case from the workflow Learnings Log that originally got Uncertain 20% in v1 of the prompt — now correctly resolves to **Active 100%**. Prompt iteration history confirmed working.

### Second smoke run (10 more rows, checkpoint resume verified)
```
python3 run_checker.py --input ../data/BMOSG_All_Businesses.xlsx --workers 1 --limit 10
# (second invocation, same Runs/ directory)
```

The runner detected `Done: 10` from the existing checkpoint and processed rows 11–20 (next 10 unchecked rows), not rows 1–10 again. **Checkpoint resume working correctly.**

| Metric | Value |
|---|---|
| Rows processed (this run) | 10 |
| Total checkpoint rows | 20 |
| Cost (this run) | $0.0735 |
| Status distribution (rows 11–20) | Active: 9, Likely Closed: 1 |

First non-Active result: **Deep Sea Salt Company** (row 18) → `Likely Closed (78%)` with evidence prefix `[Domain confirmed dead via direct check]`. The post-processing override at `tools/check_business.py:331` (No Web Presence + scrape_domain_dead → Likely Closed @ ≥70%) fired correctly.

### SQLite cache verification

The second smoke run did NOT hit the SQLite cache because the runner's checkpoint logic skipped already-done rows entirely (different mechanism from the API result cache). Direct cache test confirms the cache itself works:

```python
from tools.cache import ResultCache
cache = ResultCache()
cache.get('Agoge Life Inc.', 'Chandler', 'Arizona')
# → {'status': 'Active', 'confidence': '100', ..., 'cost_usd': 0.0, '_cached': True}
```

Cache database exists at `business_checker/cache/results.db`, ~36KB after 20 puts. Cache hit returns cost $0.0 and `_cached=True` flag (consumed downstream by `run_checker.py` for the `[CACHED]` log marker).

## Layer 3 — Manual spot-check

Three rows reviewed in detail (one per available status bucket — only Active + Likely Closed in the 20-row smoke):

### Spot-check 1: Agoge Life Inc. — Active 100%
- Website: https://www.agoge.life
- Evidence: "Website loads with real product details (Organic Hemp Protein, specific ingredients, shop now), active e-commerce elements (cart, login), and Chandler Chamber listing confirms current operation as ASU-based startup with 24/7 online orders (2026 access)."
- Citations: NSF certified listing, ASU news article (2024), Chandler Chamber business profile
- **Plausibility:** strong — three independent corroborating sources, recent dates, specific product details consistent with a real business.

### Spot-check 2: Deep Sea Salt Company — Likely Closed 78%
- Website: redacted in evidence ("Website domain failed DNS/connection check")
- Evidence: "[Domain confirmed dead via direct check] Website domain failed DNS/connection check; search results returned only unrelated Florida sea salt businesses (Florida Pure Sea Salt, Palm Beach Salt Co., Salt Bath Co.)..."
- **Plausibility:** strong — the scraper-confirmed DNS failure plus zero corroborating search results is exactly the closure pattern the prompt's "STALE RECORDS WITH NO CORROBORATION" rule targets. Confidence 78% reflects appropriate uncertainty (not 95% — the AI didn't have positive closure evidence, just absence of life signals).

### Spot-check 3: Extra Ordinary Delights — Active 95%
- Website: https://eodfudge.com/
- Evidence: "Website loads with real business-specific content including product descriptions (fudge, gift cards, confections), founder story with details about Aaron Hale and McKayla, 'Shop Now' links..."
- **Plausibility:** strong — specific founder names, product specifics, e-commerce links. The 95% (vs 100%) likely reflects no recency-dated content in the homepage scrape.

**Full URL-by-URL verification deferred to Phase 6**, where Julian will manually verify a stratified 80-row sample including the disagreement edge cases.

## Bugs investigated

### Issue 1 (from plan): Confidence as string `"0"–"100"`
**Findings:** Pipeline is consistent — `tools/check_business.py:347` intentionally converts the integer to a string before returning to the caller (per the file's own comment), and downstream consumers (`checkpoint.py`, `cache.py`, `build_output.py`) all treat it as a string. The cache's SQLite schema stores it as `INTEGER` and converts back to string on retrieval (`cache.py:153`). **Not a bug — by-design consistency.** The eval tooling in Phase 4 must coerce to int explicitly when grouping by confidence band.

### Issue 2 (from plan): `tools/check_business.py:217` re-imports per call
**Findings:** Plan note was based on a misread of an earlier line number. Line 217 is a local variable init (`scrape_gave_signal = False`), not an import. The actual `scrape_website` import lives at module top (line 19) and runs once. **Not a bug.**

### Issue 3 (from plan): `business_checker_app.py` is 887 lines (>800 line preference)
**Action:** Logged as post-demo refactor target (Codex review item #11 — "extract shared orchestration layer"). No change in this phase.

## Other findings

### Finding A: Module-as-script discoverability
`python tools/check_business.py` (the form documented in the file's docstring at line 8 and in `business_checker/CLAUDE.md`) **fails** with `ModuleNotFoundError: No module named 'tools'`. The form that works is `python3 -m tools.check_business`. Docs need updating in Phase 4 polish.

### Finding B: BMOSG row 1 doesn't have a city field for some entries
Row 1 (Agoge Life) has full state name `"Arizona"` not `"AZ"`. The cache key normalization (`tools/cache.py:_normalize_part`) lowercases and strips punctuation, so `"Arizona"` and `"arizona"` will collide correctly, but `"AZ"` would NOT collide with `"Arizona"`. **For the BMOSG run this is consistent (always full names), but for cross-dataset cache reuse with files that use abbreviations, this would miss.** Logging as a known limitation; not fixing pre-demo.

## Verification

- 90 pytest tests pass on local + CI ✓
- Smoke run produces 20 valid rows, $0.147 total cost (within $0.20 budget) ✓
- Cache mechanism works (direct test) ✓
- Checkpoint resume mechanism works (smoke run #2) ✓
- One spot-check per available status bucket completed ✓
- No tracebacks, no errors, no surprises ✓

## Next phase

Phase 3 exit criteria satisfied. Proceeding to Phase 4 — build the eval harness in `business_checker/eval/`.

The smoke-run checkpoint at `Runs/BMOSG_All_Businesses_2026-04-30_1502/checkpoint.csv` will serve as a small fixture for the eval tool's test suite (real production data from this very project, 20 rows).
