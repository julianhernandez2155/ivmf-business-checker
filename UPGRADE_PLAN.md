# Business Checker Upgrade Plan

**Project:** IVMF Business Operational Status Checker
**Date:** 2026-04-06
**Status:** Current tool works well at ~$0.006/check with Perplexity Sonar. These upgrades refine efficacy, efficiency, and cost without changing the core architecture.

---

## Current Architecture Summary

```
Input (.xlsx) → Column Detection → ThreadPoolExecutor (1-8 workers)
  └─ Per row: scrape_website() → check_business() [Perplexity Sonar] → checkpoint.csv
Final: build_output_excel() → Results.xlsx (color-coded)
```

**Key files:**
- `tools/check_business.py` (371 lines) — Core API logic, prompt, post-processing
- `tools/scrape_website.py` (126 lines) — Basic HTTP scraper, slop detection
- `tools/checkpoint.py` (115 lines) — Thread-safe CSV state management
- `tools/build_output.py` (201 lines) — Excel output formatting
- `tools/columns.py` (36 lines) — Header auto-detection
- `run_checker.py` (263 lines) — Headless CLI batch runner

**Current performance:** ~$0.005-0.008/check, ~2-3s latency, 20K+ records processed successfully.

---

## Session 1: URL Normalization

**Effort:** 30 min | **Impact:** Prevents redundant scrapes, enables cache hits in Session 2

### Problem
No URL normalization before scraping or API calls. These all refer to the same site but are treated as different inputs:
- `http://www.acme.com`
- `https://acme.com/`
- `HTTPS://WWW.ACME.COM`
- `http://acme.com/index.html`

This causes redundant work when the same business appears across datasets with slightly different URL formats.

### What to Build
New function `normalize_url(url: str) -> str` in `tools/scrape_website.py` (or a new `tools/normalize.py` if preferred).

**Normalization rules:**
1. Lowercase the entire URL
2. Strip trailing slashes
3. Remove `www.` prefix from domain
4. Remove default paths (`/index.html`, `/index.php`, `/home`)
5. Ensure `https://` scheme (default if missing)
6. Strip query parameters and fragments (business sites don't use meaningful ones)

**Integration points:**
- Call `normalize_url()` at the top of `scrape_website()` before the HTTP request
- Call `normalize_url()` in `check_business()` before building the prompt (line 68)
- The normalized URL gets passed to the prompt AND stored in checkpoint

### Files Changed
- `tools/scrape_website.py` — Add function, call it at entry
- `tools/check_business.py` — Normalize before prompt construction (line 68)

### Acceptance Criteria
- [ ] `normalize_url("HTTP://WWW.ACME.COM/") == "https://acme.com"`
- [ ] `normalize_url("http://acme.com/index.html") == "https://acme.com"`
- [ ] `normalize_url("") == ""` (empty passthrough)
- [ ] `normalize_url(None) == ""` (None passthrough)
- [ ] Existing scraper behavior unchanged for normalized URLs
- [ ] Unit tests for all normalization edge cases

### Risks
- Some businesses intentionally use `http://` (no SSL). Normalizing to `https://` for display in the prompt is fine since Perplexity searches by domain anyway, but the scraper should try `https://` first, fall back to `http://`.

---

## Session 1.5: Pre-existing Bug Fixes

**Effort:** 1 hr | **Impact:** Prevents silent data loss, reduces false closures on sparse sites

Three pre-existing bugs identified by Codex review during Session 1. Not introduced by normalization work — logging here to fix before Session 2.

### Bug 1 (P1): In-flight rows dropped on Stop → Start (`business_checker_app.py:266-269`)

**Problem:** When the user clicks Stop and immediately starts a new run, any worker that finishes after `run_gen` has incremented silently drops its result — it fails the generation check and never calls `save_checkpoint()`. The UI claims progress is saved after every row, but this path loses paid-for results with no error or log.

**Fix:** Before the `run_gen` guard discards a result, save it to the checkpoint under the old run's path. The result was paid for — it should be persisted regardless of whether the UI is still watching.

**Files:** `business_checker_app.py`

### Bug 2 (P1): 80-char threshold misclassifies valid sparse sites (`scrape_website.py:181-186`)

**Problem:** Pages with fewer than 80 characters of visible text are marked `is_slop = True`. Legitimate small-business sites — a logo, phone number, and booking link — can easily be under this threshold. When `is_slop` is True, `check_business()` tells Perplexity the domain is a parking/placeholder page, which biases the result toward `Likely Closed` or `Uncertain`.

**Fix:** Lower the threshold (40 chars is a reasonable floor — genuine parking pages are typically much shorter than that, or just the domain name), or add a secondary check before marking as slop (e.g., does the page contain a phone number or address pattern?). At minimum, lower to 40 and document the rationale.

**Files:** `tools/scrape_website.py`

### Bug 3 (P2): Run directories collide within the same minute (`business_checker_app.py:606-610`)

**Problem:** `run_name` is generated from a timestamp truncated to the minute. Two runs started within the same minute for the same workbook share a directory and checkpoint file — the second run silently merges with or overwrites the first, breaking retry/resume/export for both.

**Fix:** Include seconds in the timestamp, or append a short random suffix (4 hex chars is sufficient). Either ensures uniqueness in practice.

**Files:** `business_checker_app.py`

### Acceptance Criteria
- [x] Stop → immediate Start does not drop any in-flight rows from the stopped run
- [x] Sparse but real business sites (phone + address, under 80 chars) are not marked as parking pages
- [x] Two runs started within the same minute produce distinct directories and checkpoints
- [x] All existing tests still pass

### Known Limitation (deferred)

**Stop → New Run → Retry Failed race** (`checkpoint.py:rewrite_checkpoint`): If the user stops a run, starts a new run, and then immediately retries failed rows from the old run, there is a window where old-gen workers finishing their API calls can append to the old run's checkpoint *after* `rewrite_checkpoint` has already overwritten it. The appended rows will reappear in the retry set. This is a pre-existing gap — not introduced by Bug 1's fix — and requires specific sub-second timing to trigger in practice. Deferred to a future cleanup session.

---

## Session 2: Result Cache (SQLite)

**Effort:** 2-3 hrs | **Impact:** Saves 10-20% on repeat/overlapping dataset runs

### Problem
If "AABON 2, INC" in Birmingham, AL appears in the Alabama dataset AND the national VOB dataset, the tool pays for two Perplexity API calls. At 20K records across multiple IVMF datasets, there's likely 10-20% overlap. That's $10-20 wasted per full run.

### What to Build
New file: `tools/cache.py` — SQLite-backed result cache.

**Cache key:** SHA-256 hash of `normalize(name).lower() + "|" + city.lower() + "|" + state.lower()`
- Website is NOT part of the key — same business, same location = same check regardless of URL variation
- Name normalization: lowercase, strip punctuation, collapse whitespace

**Cache schema:**
```sql
CREATE TABLE results (
    cache_key   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT,
    state       TEXT,
    status      TEXT NOT NULL,
    confidence  INTEGER NOT NULL,
    evidence    TEXT NOT NULL,
    citations   TEXT,          -- JSON array
    checked_at  TEXT NOT NULL,  -- ISO timestamp
    cost_usd    REAL DEFAULT 0.0
);
```

**Cache TTL:** 30 days default, configurable via `.env` (`CACHE_TTL_DAYS=30`). After 30 days, re-check the business — status may have changed.

**Integration points:**
- `check_business()` in `check_business.py`: Check cache before API call, save to cache after successful API call
- Cache file location: `Business Checker/cache/results.db` (auto-created)
- Add `--no-cache` flag to `run_checker.py` for forcing fresh checks
- Log cache hits: `[42/709] CACHED Active (95%) | $0.000 | AABON 2, INC`

**Thread safety:** SQLite with WAL mode handles concurrent reads. Writes are serialized by SQLite's internal locking — no additional threading.Lock needed.

### Files Changed
- `tools/cache.py` — New file (~80-100 lines)
- `tools/check_business.py` — Add cache check/save around API call
- `run_checker.py` — Add `--no-cache` flag, pass cache instance to workers
- `.env.example` — Add `CACHE_TTL_DAYS=30`

### Acceptance Criteria
- [x] Second run of same dataset hits cache, cost = $0.00 for cached rows
- [x] Cache entries expire after TTL
- [x] `--no-cache` bypasses cache entirely
- [x] Cache hits logged distinctly from API calls
- [x] Thread-safe under concurrent workers (threading.local per-thread connections)
- [x] Unit tests for cache key generation, TTL expiry, hit/miss, concurrent writes

### Risks
- Business status changes over time. 30-day TTL is conservative — IVMF typically runs datasets months apart, so most cache entries will expire naturally.
- Cache key must handle messy business names: "AABON 2, INC" vs "AABON 2 INC" vs "Aabon 2, Inc." should all hit the same cache entry.

### Dependency
- Session 1 (URL normalization) should be done first — normalized URLs improve cache consistency, but the cache itself doesn't depend on URLs as a key.

---

## Session 3: Firecrawl Scraper Upgrade

**Effort:** 2 hrs | **Impact:** Better fast-path hit rate, fewer expensive full investigations

### Problem
Current scraper (`scrape_website.py`) uses basic `requests.get()` with 8s timeout. It cannot:
- Render JavaScript (Wix, Squarespace, Shopify sites return empty/minimal HTML)
- Bypass anti-bot protections (Cloudflare, CAPTCHA)
- Handle SPAs (React/Vue sites that load content dynamically)

When the scraper gets no content, the business falls through to Perplexity's full 8-channel investigation — which is slower and marginally more expensive. Improving scrape quality means more businesses hit the fast path.

### What to Build
Replace the HTTP logic in `scrape_website()` with Firecrawl API calls, keeping the same interface.

**Approach:** Firecrawl as primary, current `requests.get()` as fallback.

```python
def scrape_website(url: str) -> dict:
    """Same interface, better scraping."""
    url = normalize_url(url)
    if not url:
        return {"success": False, "is_slop": False, "text": "", "note": "No URL"}

    # Try Firecrawl first (JS-aware, anti-bot bypass)
    if firecrawl_key:
        result = _scrape_firecrawl(url)
        if result["success"]:
            return result

    # Fallback to direct HTTP (free, works for simple sites)
    return _scrape_direct(url)
```

**Firecrawl integration:**
- Endpoint: `POST https://api.firecrawl.dev/v1/scrape`
- Returns clean markdown — convert to plain text, apply same slop detection
- Cost: ~$0.001/scrape on Standard plan (1 credit per page)
- Timeout: 15s (Firecrawl handles JS rendering, needs more time)

**Keep existing slop detection** — same `_SLOP_MARKERS` list, same `<80 chars` check. Firecrawl returns better content, but the classification logic stays identical.

### Files Changed
- `tools/scrape_website.py` — Refactor into `_scrape_firecrawl()` + `_scrape_direct()`, keep `scrape_website()` as the public interface
- `.env.example` — Add `FIRECRAWL_API_KEY=` (optional — tool works without it)
- `requirements.txt` — No new dependency needed (uses `requests` which is already installed)

### Acceptance Criteria
- [ ] JS-rendered sites (Wix, Squarespace) return real content
- [ ] Firecrawl failure falls back to direct HTTP silently
- [ ] No Firecrawl key = tool works exactly as before (zero regression)
- [ ] Slop detection still works on Firecrawl output
- [ ] Cost tracking: scrape cost added to per-check cost in logs
- [ ] MAX_TEXT cap (600 chars) still applied to Firecrawl output
- [ ] Unit tests for both paths + fallback behavior

### Risks
- Firecrawl adds ~$0.001/check to cost. Negligible at scale.
- Firecrawl rate limits (200 req/min on Standard) are well above Perplexity's limits, so no bottleneck.
- If Firecrawl is down, fallback to direct HTTP means zero downtime impact.

### Dependency
- Session 1 (URL normalization) should be done first — Firecrawl scraping benefits from normalized URLs.

---

## Session 4: System Prompt Separation

**Effort:** 1 hr | **Impact:** Minor cost + latency reduction via Perplexity's prompt caching

### Problem
The prompt in `check_business.py` (lines 122-235) is ~2,000 tokens of static instructions + ~50 tokens of per-business variables. Every API call sends the full 2,000 tokens. Perplexity caches system prompts across calls with the same content — moving the static instructions to a `system` message lets Perplexity serve them from cache.

### What to Build
Split the current single `user` message into:

1. **System message** (static, ~1,800 tokens) — All the investigation instructions, channel definitions, confidence rubric, critical rules. This is identical for every business.
2. **User message** (dynamic, ~200 tokens) — Business name, location, website note, scrape section. This changes per call.

**Change in payload structure:**
```python
# Before
payload = {
    "model": "sonar",
    "messages": [{"role": "user", "content": full_prompt}],
    ...
}

# After
payload = {
    "model": "sonar",
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},  # cached by Perplexity
        {"role": "user", "content": business_prompt},   # per-business variables only
    ],
    ...
}
```

**System prompt content** (extracted from current prompt):
- Research analyst role definition
- Fast path criteria (lines 130-149)
- Full investigation channels 1-8 (lines 153-198)
- Status definitions (lines 202-207)
- Critical rules (lines 209-214)
- Confidence rubric (lines 218-233)
- Response format instructions (line 235)

**User prompt content** (per-business):
- Business name, location, website note
- Scrape section (website content or dead-domain note)
- Location note

### Files Changed
- `tools/check_business.py` — Extract `SYSTEM_PROMPT` constant, restructure `payload` construction

### Acceptance Criteria
- [ ] Results are identical quality to current prompt (test with 10 known businesses)
- [ ] System prompt is a module-level constant (not rebuilt per call)
- [ ] Cost per check is equal or lower
- [ ] No change to response parsing or post-processing logic
- [ ] Standalone test (`python tools/check_business.py`) still works

### Risks
- Perplexity's system prompt caching behavior is not publicly documented with guarantees. The change is still correct architecture regardless — separating static from dynamic is clean design.
- Must verify Perplexity sonar accepts `system` role messages (it does — standard OpenAI-compatible API).

### Dependency
- None. Can be done in any order.

---

## Session 5: Accuracy Validation Mode

**Effort:** 2-3 hrs | **Impact:** Trust, reporting, calibration — makes this a professional tool

### Problem
The tool reports confidence scores (e.g., "Active 95%") but there's no validation that these scores are calibrated. A business marked "Active 95%" might actually be correct 95% of the time — or it might be correct 80% of the time. Without measurement, you can't know. IVMF needs a number they can put in reports.

### What to Build
New file: `tools/validate.py` — Validation mode that samples results and generates an accuracy report.

**Two-part system:**

**Part A: Sample Generator**
```bash
python tools/validate.py sample --checkpoint Runs/.../checkpoint.csv --count 50
```
- Randomly samples N results from a completed checkpoint
- Stratified sampling: proportional representation of each status (Active, Likely Closed, Uncertain, No Web Presence)
- Outputs `validation_sample.xlsx` with columns:
  - Business Name, Website, City, State
  - AI_Status, AI_Confidence, AI_Evidence
  - `Human_Status` (blank — for manual entry)
  - `Human_Notes` (blank — for manual entry)
  - `Correct` (blank — formula: =IF(AI_Status=Human_Status, "Yes", "No"))

**Part B: Accuracy Reporter**
```bash
python tools/validate.py report --sample validation_sample.xlsx
```
- Reads completed validation sample (after human fills in Human_Status)
- Calculates:
  - Overall accuracy: % of AI_Status matching Human_Status
  - Per-status accuracy: accuracy breakdown by status category
  - Confidence calibration: for "Active 95-100%", what % were actually correct?
  - Confusion matrix: where does the tool get it wrong? (e.g., calls Active when actually Closed)
- Outputs `validation_report.md` with results + `validation_report.xlsx` with detailed data

**Example output:**
```
IVMF Business Checker — Validation Report
==========================================
Sample size: 50 businesses
Date range: 2026-03-17 to 2026-04-06

Overall Accuracy: 94% (47/50 correct)

Per-Status Accuracy:
  Active:           96% (24/25 correct)
  Likely Closed:    91% (10/11 correct)
  Uncertain:        100% (8/8 correct)
  No Web Presence:  83% (5/6 correct)

Confidence Calibration:
  95-100% confidence: 97% actually correct (33/34)
  80-94% confidence:  90% actually correct (9/10)
  60-79% confidence:  83% actually correct (5/6)

Errors (3):
  1. "Smith Catering" — AI said Active (90%), actually Likely Closed
     AI evidence: "Facebook page with 2024 posts"
     Human note: "Facebook belongs to different Smith Catering in Ohio"
  2. ...
```

### Files Changed
- `tools/validate.py` — New file (~150-200 lines)
- `requirements.txt` — No new dependencies (uses openpyxl already installed)

### Acceptance Criteria
- [ ] Sample generator produces correctly formatted Excel with blank human columns
- [ ] Stratified sampling ensures all status categories are represented
- [ ] Reporter handles partial completion (some rows not yet validated)
- [ ] Report includes actionable error analysis (not just numbers)
- [ ] Can be run against any checkpoint from any run
- [ ] Unit tests for accuracy calculation, stratified sampling

### Risks
- Requires human effort (~1-2 hours to manually verify 50 businesses). This is a one-time investment per major prompt revision.
- Validation is only as good as the human reviewer. IVMF staff should use the same channels the tool uses (Google Maps, Facebook, etc.) for consistency.

### Dependency
- None. Can be done at any point. Most valuable after Sessions 3-4 (to validate the upgraded tool).

---

## Session 6: Structured Evidence Output

**Effort:** 1 hr | **Impact:** Better UX for IVMF reviewers scanning Excel output

### Problem
Current evidence is a single sentence:
```
website dead, Google Maps permanently closed January 2025, Facebook inactive since 2020 | Sources: url1, url2
```

For IVMF staff reviewing hundreds of rows, parsing this sentence for each business is slow. A structured breakdown is faster to scan.

### What to Build
Update the Pydantic model and prompt to return structured evidence.

**New Pydantic model:**
```python
class ChannelSignal(BaseModel):
    channel: str      # "Website", "Google Maps", "Facebook", etc.
    finding: str      # "Active with recent reviews (2024)", "Permanently closed", "Not found"

class BusinessStatus(BaseModel):
    status:     Literal["Active", "Likely Closed", "Uncertain", "No Web Presence"]
    confidence: int
    evidence:   str                    # One-sentence summary (kept for backward compat)
    channels:   list[ChannelSignal]    # Structured breakdown
```

**Prompt addition** (at end of response instructions):
```
Also return a "channels" array listing each channel you checked and what you found.
Format: [{"channel": "Website", "finding": "Live site with products"}, ...]
```

**Excel output change** (`build_output.py`):
- New column: `AI_Channels` — formatted as multi-line text:
  ```
  Website: Dead (404)
  Google Maps: Permanently closed (Jan 2025)
  Facebook: Inactive since 2020
  LinkedIn: Not found
  ```
- Column width: 50 chars, text wrap enabled
- Inserted after `AI_Evidence`, before `AI_Checked_At`

**Checkpoint change** (`checkpoint.py`):
- Add `AI_Channels` field to `FIELDNAMES`
- Store as JSON string in CSV, parse back on load
- Backward compatible: missing field = empty string

### Files Changed
- `tools/check_business.py` — Update Pydantic model, add prompt instruction, parse channels
- `tools/checkpoint.py` — Add `AI_Channels` to fieldnames
- `tools/build_output.py` — Add channels column to Excel output
- `run_checker.py` — Pass channels through to checkpoint

### Acceptance Criteria
- [ ] Channels array populated for new checks
- [ ] Old checkpoints without channels still load correctly (backward compat)
- [ ] Excel output shows readable multi-line channel breakdown
- [ ] Evidence field still contains the one-sentence summary
- [ ] No increase in API cost (channels come from same Perplexity call)

### Risks
- Adding structured output to the prompt may increase output tokens slightly (~50-100 extra tokens). Cost impact: ~$0.0001/check. Negligible.
- Perplexity's structured JSON output must handle nested models. Test with `BusinessStatus.model_json_schema()` to confirm the schema is valid.

### Dependency
- Session 4 (system prompt separation) should be done first — the prompt changes are easier to make when static/dynamic content is already separated.

---

## Implementation Order

```
Session 1:   URL Normalization         [30 min]  — Foundation for Sessions 2 & 3  ✅ DONE
    ↓
Session 1.5: Pre-existing Bug Fixes   [1 hr]    — Data integrity before adding cache
    ↓
Session 2:   Result Cache (SQLite)    [2-3 hrs] — Uses normalized URLs for better key matching  ✅ DONE
    ↓
Session 3:   Firecrawl Scraper        [2 hrs]   — Uses normalized URLs, benefits from cache
    ↓
Session 4:   System Prompt Separation [1 hr]    — Independent, clean refactor
    ↓
Session 5:   Accuracy Validation      [2-3 hrs] — Best done after 3 & 4 to validate upgraded tool
    ↓
Session 6:   Structured Evidence      [1 hr]    — Polish, builds on prompt from Session 4
```

**Total estimated effort:** 9-12 hours across 7 sessions

**Expected outcome after all sessions:**
- Cost: ~$0.005-0.007/check (down from $0.006-0.008, cache saves 10-20% on repeat runs)
- Accuracy: Measured and reportable (validation mode)
- Scraping: JS-rendered sites now captured (Firecrawl)
- UX: Structured evidence for faster human review
- Efficiency: No redundant checks on duplicate businesses

---

## What We Decided NOT to Do

| Idea | Why Not |
|------|---------|
| Replace Perplexity with Exa + Firecrawl + LLM | 2x more expensive, 3-4x slower, loses social media coverage |
| Add Exa as fallback for Uncertain results | Not worth the integration complexity for 10-15% of checks |
| Switch to Sonar Pro | 3x cost, prompt is well-engineered enough for base Sonar |
| Build a web dashboard | Excel with color-coding is what IVMF staff need |
| Add more status categories | 4 statuses is the right granularity for this use case |
| Two-call prompt strategy | Adds latency for 20-30% of checks, marginal savings |
