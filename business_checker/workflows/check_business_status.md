# Workflow: Check Business Operational Status

**Version:** 2.0
**Last updated:** 2026-03-17
**Tool:** `tools/check_business.py`

---

## Objective

For each business record in an Excel spreadsheet, determine whether the business
is still actively operating. Return a structured verdict with a confidence score
and evidence summary.

---

## Required Inputs

| Field | Required | Notes |
|-------|----------|-------|
| Business name | Yes | Full legal name preferred |
| City | Yes | Helps disambiguate common business names |
| State | Yes | Two-letter abbreviation preferred |
| Website | No | If present, checked first. Absence is not a signal of closure. |

---

## Tool to Call

```python
from tools.check_business import check_business

result = check_business(
    api_key=api_key,
    name="Acme Veteran Services LLC",
    website="https://acmevets.com",
    city="Syracuse",
    state="NY",
)
```

**Returns:**
```python
{
    "status":     "Active",           # see Status Definitions below
    "confidence": "87",               # string, 0–100
    "evidence":   "Website live with recent blog post (Feb 2026), Yelp shows 3 reviews from 2025.",
    "citations":  ["https://...", "https://..."],
    "error":      None,               # set to a string if the call failed
}
```

---

## Status Definitions

| Status | Meaning | Example signals |
|--------|---------|----------------|
| **Active** | Business is currently operating | Live website, recent reviews, active social media, Google Business shows open |
| **Likely Closed** | Strong evidence of closure | Google Business shows "Permanently closed", website returns 404, news article about closure, no activity in 2+ years |
| **Uncertain** | Mixed or outdated signals | Website exists but hasn't been updated in years, some reviews but no recent ones, partial information |
| **No Web Presence** | No online presence found at all | No website, no Google listing, no Yelp, no LinkedIn, not mentioned anywhere online |

---

## Confidence Thresholds

| Score | Interpretation | Action |
|-------|---------------|--------|
| 80–100 | High confidence | Accept result |
| 50–79 | Moderate confidence | Accept, but flag for spot-check if result is Likely Closed |
| 0–49 | Low confidence | Queue for manual review |

Businesses with confidence < 50 and status "Uncertain" should be flagged for
human review before being removed from the database.

---

## Edge Cases

**Common business names (e.g., "A&B Services LLC"):**
The AI may find results for a different business with the same name. City and state
help narrow results. If evidence mentions a different city, treat as Uncertain.

**Franchise locations:**
Chain/franchise locations (e.g., a McDonald's franchisee) may not have their own
web presence. The parent brand being active does not mean this specific location is.
The AI is prompted to look for the specific location, not just the brand.

**No website listed:**
A missing website is not evidence of closure. The AI will search by name and location.
Expect more Uncertain and No Web Presence results for businesses without websites.

**Businesses that moved or rebranded:**
If evidence suggests the business moved or changed names but appears to still exist,
return Active with a note in the evidence field about the change.

**Rate limit errors (429):**
The tool retries automatically with exponential backoff (30s, 60s, 90s, 120s).
If errors persist, reduce worker count. Check Perplexity tier at:
https://www.perplexity.ai/settings/api

---

## Orchestration

The tool is called row-by-row from either:

- `run_checker.py` — headless concurrent runner for large batches
- `business_checker_gui.py` — GUI for interactive use

Both use a shared checkpoint (`checkpoint.csv`) to track progress. If a run is
interrupted, it resumes from the last saved row.

---

## Output

Final results are assembled by `tools/build_output.py` into a results Excel file
with four new columns: AI_Status, AI_Confidence, AI_Evidence, AI_Checked_At.

---

## Known Constraints

- **Perplexity Tier 0 (new accounts):** 1 QPS / 50 req/min. Use 1 worker only.
- **Perplexity Tier 1:** 3 QPS. Use up to 3 workers.
- **Perplexity Tier 2:** 8 QPS. Use up to 8 workers.
- Tier advances automatically with spending history.
- Cost: ~$0.005–0.008 per business check (sonar model, March 2026).

---

## Learnings Log

| Date | Learning |
|------|----------|
| 2026-03-05 | Pilot run of 30 records: 83% Active, avg confidence 83%. Parse errors rare with structured output. |
| 2026-03-17 | Migrated from Claude API + web_search to Perplexity sonar. Structured JSON output via Pydantic eliminates parse errors entirely. Cost reduced ~6-10x. |
| 2026-03-17 | Prompt v2: Added quoted search terms, disambiguation rule (ignore unrelated mentions), Facebook/Instagram in search list, recency emphasis (2023–2026), and tightened status definitions. Bomb Azz Lemonade went from Uncertain (20%) to Active (95%) — root cause was unquoted search returning old magazine uses of the phrase, not the business. |
