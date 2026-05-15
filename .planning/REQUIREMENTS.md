# Requirements — Milestone v1.1: Web Platform Pivot

**Project:** IVMF Business Checker
**Milestone:** v1.1 — Web Platform Pivot
**Created:** 2026-05-12
**Status:** Scoped, awaiting roadmap

## Active Requirements (v1.1)

### AUTH — Authentication & Authorization

- [x] **AUTH-01**: User can sign in with @syr.edu email via magic-link or password (Supabase Auth)
- [x] **AUTH-02**: Admin can extend the email domain allowlist via a config row (no code change required)
- [x] **AUTH-03**: System enforces two-role RBAC (admin / user) via Next.js middleware AND Postgres RLS, with role stored in `app_metadata`
- [x] **AUTH-04**: System writes an audit log entry (with before/after diff) for every admin write action (edit, merge, approval, key rotation)

### CANON — Canonical Business Matching

- [ ] **CANON-01**: System auto-merges an uploaded row to an existing canonical business when EIN matches exactly
- [ ] **CANON-02**: System routes 2-of-N field-consensus matches (name, website_domain, owner, phone, address) to the admin review queue rather than auto-merging
- [x] **CANON-03**: System normalizes name (strip suffix, lowercase, punctuation), domain (root, no scheme/www/path), phone (E.164), and address (US standardized via usaddress) before matching
- [ ] **CANON-04**: System maintains a blocklist of known-collision fields (registered-agent addresses, `*.wixsite.com`, answering-service phones) excluded from 2-of-N voting
- [x] **CANON-05**: System creates a new canonical business row when no match meets the threshold
- [x] **CANON-06**: System writes every verification to an append-only `verifications` table; `BEFORE UPDATE` / `BEFORE DELETE` triggers raise to enforce immutability
- [x] **CANON-07**: System enforces idempotency via UNIQUE keys on `(run_id, row_index, pass)` for verifications and on `(provider, request_hash)` for API calls
- [x] **CANON-08**: System records per-row provenance on every verification: which fields matched, match score, method used

### JOBS — Verification Runs

- [ ] **JOBS-01**: User can upload a CSV or XLSX file and map source columns to the canonical schema (name, address, owner, etc.) before submitting a run
- [ ] **JOBS-02**: System displays a pre-flight cost estimate (`row_count × avg_cost_per_row × passes`) before run submission
- [ ] **JOBS-03**: System blocks run submission if the estimated cost exceeds the remaining monthly budget for the API key
- [ ] **JOBS-04**: User can set an optional per-run cost cap that overrides the default (defaults to `min(monthly_remaining, estimate × 1.5)`)
- [ ] **JOBS-05**: System streams batched run progress to the browser via Supabase Realtime (single `run_progress` row updated every 2s, never per-row)
- [ ] **JOBS-06**: System resumes a run automatically after a worker crash via pgmq visibility timeout (vt=300s) and a heartbeat watchdog
- [ ] **JOBS-07**: System resumes a run from the exact paused row after browser close, laptop sleep, or reconnect (state queried from `verifications`, not in-memory)
- [ ] **JOBS-08**: System pauses a run cleanly (no data loss) when an API provider returns a credit-exhausted error; admin tops up and clicks resume to continue
- [ ] **JOBS-09**: System pauses a run when the monthly budget cap is hit; admin is notified via in-app alert and email
- [ ] **JOBS-10**: Admin can register, rotate, and disable per-provider API keys (Perplexity, FireCrawl) in an admin UI; keys are encrypted at rest
- [ ] **JOBS-11**: Admin can set a monthly budget cap and low-balance threshold per API key; system alerts admin at 85% of cap
- [ ] **JOBS-12**: Admin can register backup API keys per provider and enable opt-in auto-fallback on a per-run basis (default: off)
- [ ] **JOBS-13**: System logs every failed row with the error reason; admin can retry individual rows or re-enqueue all errored rows from a run
- [ ] **JOBS-14**: User can see a full history of their runs, including status, completion stats, and cost actual vs estimate

### MANUAL — Manual Workflows

- [ ] **MANUAL-01**: Admin can view a unified review queue showing items of kind: canonical merge, uncertain verification, outreach response
- [ ] **MANUAL-02**: Admin can resolve a queue item (merge, don't merge, override status, approve outreach response); resolution writes the appropriate record(s) atomically
- [ ] **MANUAL-03**: Admin "edit" of a business status writes a NEW row to `verifications` with `method='admin_edit'` and a reason; never UPDATEs an existing verification
- [ ] **MANUAL-04**: Admin can take a random sample (by count or percentage) of any run for manual labeling
- [ ] **MANUAL-05**: Admin can label sampled rows via a labeling UI; labels are stored and accessible to the eval harness for gold-set growth

### OUTREACH — Email Verification Outreach

- [ ] **OUTREACH-01**: User can submit an outreach ticket for a run, filtered by status (uncertain, likely closed) and presence of email; ticket lists target count and template version
- [ ] **OUTREACH-02**: Admin can review, approve, or reject outreach tickets before any email is sent
- [ ] **OUTREACH-03**: System sends outreach emails via Resend from a configured IVMF sender (SPF/DKIM/DMARC verified on the IVMF subdomain)
- [ ] **OUTREACH-04**: Each outreach email includes a unique HMAC-signed token URL linking to a Next.js form
- [ ] **OUTREACH-05**: Business owner can submit the form (unauthenticated) to confirm/update business name, owner, address, phone, website, operating status
- [ ] **OUTREACH-06**: Form responses write to a service-role-only `form_responses` table; anon clients have no direct access to `verifications`
- [ ] **OUTREACH-07**: Admin reviews and approves each form response before it becomes a verification row (method=`email_response`, confidence=0.95)
- [ ] **OUTREACH-08**: System handles Resend bounce/complaint webhooks; bounced addresses are flagged on the business record and excluded from future outreach
- [ ] **OUTREACH-09**: Admin dashboard shows outreach funnel: tickets sent, delivered, opened, responded, approved-into-verification

### ANALYTICS — Dashboard

- [ ] **ANALYTICS-01**: Admin dashboard shows cache hit rate over time (per-run and rolling)
- [ ] **ANALYTICS-02**: Admin dashboard shows monthly $ spent vs cap per API key, with daily breakdown
- [ ] **ANALYTICS-03**: Admin dashboard shows status distribution per run (active / likely_closed / closed / uncertain / errored)
- [x] **ANALYTICS-04**: System runs the eval harness against the labeled gold set on every worker deploy in CI; deploy is blocked if accuracy drops below the prior baseline _(Phase 0, Plan 00-06: `.github/workflows/eval-ci.yml` + `scripts/eval-ci.sh` + frozen `business_checker/eval/baseline.json`; local end-to-end verified 2026-05-15)_
- [ ] **ANALYTICS-05**: Run history shows a reupload dedupe widget: "Uploaded N rows. K cache hits ($0 cost). M API calls ($X spent). P new businesses added."

### EXPORT — Output & Receipts

- [ ] **EXPORT-01**: System generates an XLSX export at run completion with original columns + appended AI columns (AI_Status, AI_Confidence, AI_Evidence, AI_Source_URL, AI_Checked_At, AI_Method, AI_From_Cache, Business_ID), byte-compatible with v1.0 column shape
- [ ] **EXPORT-02**: System also generates a CSV export with the same columns
- [ ] **EXPORT-03**: User can re-export a run on demand from the run detail page; re-export reflects the latest state (e.g., after manual review changed a status)
- [ ] **EXPORT-04**: System sends a run-completion email receipt to the user with stats (rows processed, cache hits, API calls, new businesses, cost) and download links
- [ ] **EXPORT-05**: System maintains a shared canonical cache: every upload either matches an existing canonical business or creates a new one; verification results are stored against the canonical record so future uploads with the same business hit the cache
- [ ] **EXPORT-06**: Exports are stored in Supabase Storage with signed URLs; users can only download their own runs (RLS), admins can download any

## Out of Scope (this milestone)

### Deferred to a future milestone

- **MANUAL-DB-EDITOR**: Admin power-user UI for manual merge/split of canonical businesses and alias management — Reason: Wait until production data shows what kinds of cleanup actually need a dedicated UI. Review queue handles known cases for v1.1.
- **ANALYTICS-WEEKLY-DRIFT**: Weekly automated eval drift alert via pg_cron — Reason: Eval-in-CI (ANALYTICS-04) catches the high-frequency drift case on every deploy. Weekly cron is incremental value; defer to a later milestone.
- **CANON-NIGHTLY-REVALIDATION**: Nightly cron re-validates existing canonical merges against current field values — Reason: Useful but not required for v1.1 ROI. Manual review queue catches misses for now.

### Explicitly excluded

- **BYOK (Bring Your Own Key)**: User-supplied Perplexity/FireCrawl keys — Reason: Defeats the centralization purpose of the pivot. Admin-managed keys only.
- **Auto-merge on non-EIN matches**: Silent merge on 2-of-N field consensus — Reason: Shared registered-agent addresses, holding-company domains, and answering-service phones make silent merges unsafe. Always queue for admin.
- **Auto-acceptance of outreach form responses**: Form submission becomes a verification without admin review — Reason: Tokenized URLs can be forwarded, intercepted, or spoofed. Admin gate prevents data corruption.
- **Soft-delete on verifications**: Marking verifications as deleted — Reason: Breaks the append-only audit guarantee. All "deletes" are new verifications with method=`admin_edit`.
- **More than two RBAC roles**: Department-scoped, viewer-only, or external-partner roles — Reason: RLS complexity explosion. Two roles suffice for IVMF v1.1.
- **Auto-extending budget cap on hit**: Cap auto-raises to allow the run to complete — Reason: Defeats the whole point of the cap.
- **Per-user custom prompts**: Users can edit the verification prompt — Reason: Eval harness covers ONE prompt; user edits silently bypass the regression gate.
- **Browser-side execution of verification**: Verification runs in the user's browser tab — Reason: Vercel/Edge timeouts; ties run lifetime to a tab.
- **Continued maintenance of the Tkinter desktop app** — Reason: v1.0 desktop is frozen. All v1.0 verification logic is preserved and ported to the Railway worker.

## Validated Requirements (v1.0 — frozen, ported to worker)

These shipped in v1.0 (desktop) and are preserved through the worker:

- ✓ Single-business verification via Perplexity Sonar — `tools/check_business.py`
- ✓ Website scraping fallback — `tools/scrape_website.py`
- ✓ Concurrent batch verification with QPS tiering — adapted for asyncio semaphore in worker
- ✓ Multi-pass aggregator with override logic — to be extracted to `tools/aggregator.py` as v1.0 polish before Phase 0
- ✓ Eval harness against labeled gold set — `business_checker/eval/`
- ✓ XLSX output assembly — `tools/build_output.py` (reused for EXPORT-01)

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| AUTH-01 | Phase 0 | Complete |
| AUTH-02 | Phase 0 | Complete |
| AUTH-03 | Phase 0 | Complete |
| AUTH-04 | Phase 0 | Complete |
| CANON-01 | Phase 1 | Pending |
| CANON-02 | Phase 1 | Pending |
| CANON-03 | Phase 0 | Complete |
| CANON-04 | Phase 1 | Pending |
| CANON-05 | Phase 0 | Complete |
| CANON-06 | Phase 0 | Complete |
| CANON-07 | Phase 0 | Complete |
| CANON-08 | Phase 0 | Complete |
| JOBS-01 | Phase 1 | Pending |
| JOBS-02 | Phase 2 | Pending |
| JOBS-03 | Phase 2 | Pending |
| JOBS-04 | Phase 2 | Pending |
| JOBS-05 | Phase 1 | Pending |
| JOBS-06 | Phase 2 | Pending |
| JOBS-07 | Phase 2 | Pending |
| JOBS-08 | Phase 2 | Pending |
| JOBS-09 | Phase 2 | Pending |
| JOBS-10 | Phase 2 | Pending |
| JOBS-11 | Phase 2 | Pending |
| JOBS-12 | Phase 2 | Pending |
| JOBS-13 | Phase 1 | Pending |
| JOBS-14 | Phase 2 | Pending |
| MANUAL-01 | Phase 3 | Pending |
| MANUAL-02 | Phase 3 | Pending |
| MANUAL-03 | Phase 3 | Pending |
| MANUAL-04 | Phase 3 | Pending |
| MANUAL-05 | Phase 3 | Pending |
| OUTREACH-01 | Phase 4 | Pending |
| OUTREACH-02 | Phase 4 | Pending |
| OUTREACH-03 | Phase 4 | Pending |
| OUTREACH-04 | Phase 4 | Pending |
| OUTREACH-05 | Phase 4 | Pending |
| OUTREACH-06 | Phase 4 | Pending |
| OUTREACH-07 | Phase 4 | Pending |
| OUTREACH-08 | Phase 4 | Pending |
| OUTREACH-09 | Phase 4 | Pending |
| ANALYTICS-01 | Phase 5 | Pending |
| ANALYTICS-02 | Phase 5 | Pending |
| ANALYTICS-03 | Phase 5 | Pending |
| ANALYTICS-04 | Phase 0 | Complete (2026-05-15, Plan 00-06) |
| ANALYTICS-05 | Phase 1 | Pending |
| EXPORT-01 | Phase 1 | Pending |
| EXPORT-02 | Phase 1 | Pending |
| EXPORT-03 | Phase 1 | Pending |
| EXPORT-04 | Phase 2 | Pending |
| EXPORT-05 | Phase 1 | Pending |
| EXPORT-06 | Phase 1 | Pending |

**Coverage:** 50/50 v1.1 requirements mapped to exactly one phase. No orphans.

---
*Last updated: 2026-05-14 — Plan 00-04 closed AUTH-01/02/03 (Plan 00-02 closed CANON-03/05/06/07/08 + AUTH-04)*
