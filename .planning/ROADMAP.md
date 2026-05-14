# ROADMAP — Milestone v1.1: Web Platform Pivot

**Project:** IVMF Business Checker
**Milestone:** v1.1 — Web Platform Pivot
**Created:** 2026-05-12
**Granularity:** Standard (7 phases — Phase 0 + 6 numbered phases)
**Coverage:** 50/50 v1.1 requirements mapped

## Rationale

**Framing decision (2026-05-13):** The product is a *triage engine*, not a status oracle. AI emits routing labels; humans resolve them. See [2026-05-13-decision-triage-not-oracle.md](./2026-05-13-decision-triage-not-oracle.md) for the locked output schema and phase responsibilities.

Phases derived from the research SUMMARY.md build-order table. Three structural notes:

1. **Phase 0 is foundation-heavy and carries disproportionate risk weight.** Schema + RLS + auth + worker scaffold + eval-CI gate must all be green before any business logic lands. Skipping any compounds across every later phase.
2. **Phase 1 (cache-only) and Phase 2 (live) are intentionally separate.** Phase 1 ships a working web app with canonical matching + cache lookup + XLSX/CSV export and zero external API calls. This gives clean acceptance of schema/canonical/RLS/Realtime before any money is at risk and produces the "reupload dedupe" demo moment for Jim.
3. **Aggregator extraction to `business_checker/tools/aggregator.py` is a v1.0 polish pass BEFORE Phase 0 begins.** It is a Phase 0 dependency, NOT a phase deliverable. The Phase 2 worker imports the module unchanged. This lowers per-phase risk and lets the eval gold set re-validate the extraction immediately.

Outreach (Phase 4) is the only externally-blocked phase (IT must verify Resend DNS on the IVMF subdomain). All other phases ship independently of that unblock.

## Phases

- [ ] **Phase 0: Foundation** — Schema, RLS, auth, worker scaffold, pgmq, codegen + eval-CI gates green
- [ ] **Phase 1: Cache-Only Verification** — Upload → canonical match → cache hit OR "not yet verified" → XLSX/CSV export, zero API calls
- [ ] **Phase 2: Live Verification** — Real Perplexity + FireCrawl calls; multi-pass aggregator → `business_current_state`; pause/resume on credit exhaustion
- [ ] **Phase 3: Manual Workflows** — Unified review queue, random-sample labeling, admin edits as new verifications
- [ ] **Phase 4: Outreach** — Admin-approved tickets via Resend, HMAC-tokenized forms, admin approval gate (externally blocked by IT)
- [ ] **Phase 5: Analytics & Receipts** — Dashboard widgets, dedupe demo widget, run-completion email receipts
- [ ] **Phase 6: Decommission Desktop** — Regression vs BMSG + Alabama VOB baselines, tag v1.1.0, archive v1.0

## Phase Details

### Phase 0: Foundation
**Goal:** Foundational infrastructure is live — schema, RLS, auth, worker, codegen, and eval-CI gate are all green so every subsequent phase composes cleanly.
**Depends on:** v1.0 polish pass extracting multi-pass aggregator to `business_checker/tools/aggregator.py` (NOT a phase deliverable; precondition).
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, CANON-03, CANON-05, CANON-06, CANON-07, CANON-08, ANALYTICS-04
**Plans:** 6 plans across 6 waves
Plans:
- [x] 00-01-wave0-test-scaffolding-PLAN.md — Wave 0 stub test files, fixtures, scripts, Makefile (no requirements; scaffolding)
- [x] 00-02-supabase-schema-rls-PLAN.md — Wave 1 schema + RLS + append-only triggers + pgmq queues + normalize helpers (CANON-03, CANON-05, CANON-06, CANON-07, CANON-08, AUTH-04)
- [x] 00-03-codegen-drift-gate-PLAN.md — Wave 2 Drizzle introspect + Pydantic codegen + GitHub Actions drift gate (no new reqs; supports P4 defense; live drizzle-kit pull deferred until dev DB)
- [ ] 00-04-web-auth-shell-PLAN.md — Wave 3 Next.js 16 + magic-link auth + middleware allowlist + /me page (AUTH-01, AUTH-02, AUTH-03)
- [ ] 00-05-worker-railway-pgmq-PLAN.md — Wave 4 FastAPI worker scaffold + heartbeat + pgmq long-poll (D-00-09, D-00-11 item 5; no new reqs)
- [ ] 00-06-eval-ci-demo-PLAN.md — Wave 5 eval-CI regression gate + Resend DNS ticket + Phase 0 exit demo (ANALYTICS-04)
**Success Criteria** (what must be TRUE):
  1. User with @syr.edu email can sign in via magic-link or password; non-allowlisted domains are blocked at middleware AND RLS layers.
  2. Admin can extend the email domain allowlist by editing a config row with no code change.
  3. Every admin write action produces an audit_log row with before/after diff (verified by triggering a config change and inspecting the row).
  4. Pushing a worker deploy with a schema drift (Pydantic/Drizzle out of sync with Postgres) fails CI; pushing a deploy that regresses the eval gold-set accuracy below baseline fails CI.
  5. Attempting `UPDATE` or `DELETE` on the `verifications` table raises a Postgres exception; an `INSERT` succeeds and idempotency UNIQUE keys reject duplicate `(run_id, row_index, pass)` and `(provider, request_hash)` inserts.
  6. pgmq queues `q_verify` and `q_aggregator` are configured with vt=300s; upload-parse rejects files whose columns fall outside the public-registry allowlist; Resend DNS ticket for IVMF subdomain is filed with IT.

### Phase 1: Cache-Only Verification
**Goal:** A user can upload a CSV/XLSX, see canonical matches against existing verified businesses, and export a v1.0-compatible XLSX/CSV — without the system spending a single cent on external APIs.
**Depends on:** Phase 0
**Requirements:** CANON-01, CANON-02, CANON-04, JOBS-01, JOBS-05, JOBS-13, EXPORT-01, EXPORT-02, EXPORT-03, EXPORT-05, EXPORT-06, ANALYTICS-05
**Success Criteria** (what must be TRUE):
  1. User can upload a CSV or XLSX, map source columns to canonical fields (name/address/owner/etc.), and submit a run that completes with zero external API calls.
  2. Rows with EIN matches auto-merge to the existing canonical business; rows hitting 2-of-N consensus on (name, domain, owner, phone, address) are routed to the admin review queue; collision-blocklisted fields (registered-agent addresses, `*.wixsite.com`, answering-service phones) do not contribute to 2-of-N voting.
  3. User can download an XLSX and a CSV export, byte-compatible with v1.0 column shape (AI_Status, AI_Confidence, AI_Evidence, AI_Source_URL, AI_Checked_At, AI_Method, AI_From_Cache, Business_ID); cached rows have `AI_From_Cache=true`, uncached rows are marked "not yet verified".
  4. The run detail page shows a dedupe widget reading "Uploaded N rows. K cache hits. M new businesses added." and a re-export reflects the latest state (after a manual change in Phase 3, the same re-export call updates).
  5. Run progress streams via a single batched `run_progress` Realtime row updated every 2s; failed rows surface in an admin-visible error log with reason.
  6. RLS prevents user A from downloading user B's export via signed URL; admin can download any.
**Plans:** TBD
**UI hint**: yes

### Phase 2: Live Verification
**Goal:** Users can run an end-to-end verification against real Perplexity + FireCrawl APIs, with hard cost caps, resumable jobs, and aggregator-driven canonical state — the full v1.0 capability surface, hosted.
**Depends on:** Phase 1
**Requirements:** JOBS-02, JOBS-03, JOBS-04, JOBS-06, JOBS-07, JOBS-08, JOBS-09, JOBS-10, JOBS-11, JOBS-12, JOBS-14, EXPORT-04
**Success Criteria** (what must be TRUE):
  1. Before submitting, user sees a pre-flight cost estimate (`row_count × avg_cost × passes`); submission is blocked if the estimate exceeds remaining monthly budget; user can set an optional per-run cap that overrides the default.
  2. A run survives browser close, laptop sleep, worker crash (pgmq vt=300s + heartbeat), and provider credit exhaustion; admin tops up and clicks resume; the run continues from the exact paused row with no duplicate API calls (idempotency on `(provider, request_hash)` holds).
  3. Multi-pass aggregator (imported unchanged from `business_checker/tools/aggregator.py`) fires only when `passes_completed = passes_required` per row; writes a derived row to `business_current_state` via trigger maintenance, never `REFRESH MATERIALIZED VIEW`.
  4. Admin can register, rotate, and disable Perplexity and FireCrawl keys; keys are encrypted at rest; admin can set monthly cap and low-balance threshold; system pauses run + alerts admin at 100% cap and warns at 85%.
  5. Admin can register a backup API key per provider and enable opt-in auto-fallback on a per-run basis (default off); user can see full run history with status, completion stats, cost actual vs estimate.
  6. Verification accuracy on the BMSG and Alabama VOB reference subsets matches or exceeds v1.0 baseline as measured by the eval harness; run-completion email receipt sends to the user with stats and download links.
**Plans:** TBD
**UI hint**: yes

### Phase 3: Manual Workflows
**Goal:** Admins can resolve low-confidence rows, label samples for gold-set growth, and make corrections — all while preserving the append-only audit guarantee.
**Depends on:** Phase 2 (needs real merge_review and uncertain rows to operate on)
**Requirements:** MANUAL-01, MANUAL-02, MANUAL-03, MANUAL-04, MANUAL-05
**Success Criteria** (what must be TRUE):
  1. Admin can view a unified review queue containing canonical merge candidates (2-of-N), uncertain verifications, and (post-Phase 4) outreach responses; each item shows enough context to resolve in one click.
  2. Admin can resolve a queue item (merge / don't merge / override status); resolution writes the appropriate verification(s), canonical edits, and audit log row atomically in a single transaction.
  3. Admin attempting to "edit" a business status creates a NEW row in `verifications` with `method='admin_edit'` and a reason; original verification rows remain untouched (verified by inspecting row count before/after).
  4. Admin can take a random sample (by count or percentage) of any run and label the sampled rows in a labeling UI; labels are persisted and visible to the eval harness for gold-set growth.
**Plans:** TBD
**UI hint**: yes

### Phase 4: Outreach
**Goal:** Admins can email business owners to confirm operating status via tokenized forms, with admin approval gating every verification write — closing the loop on uncertain rows.
**Depends on:** Phase 3 (review queue must already exist; outreach responses become a queue item kind). **Externally blocked by IT for Resend DNS on the IVMF subdomain.**
**Requirements:** OUTREACH-01, OUTREACH-02, OUTREACH-03, OUTREACH-04, OUTREACH-05, OUTREACH-06, OUTREACH-07, OUTREACH-08, OUTREACH-09
**Success Criteria** (what must be TRUE):
  1. User can submit an outreach ticket for a run, filtered to uncertain/likely_closed rows with an email present; admin can approve or reject the ticket before any email leaves the system.
  2. Approved tickets send via Resend from the configured IVMF subdomain (SPF/DKIM/DMARC verified); each email contains a unique HMAC-signed token URL pointing to an unauthenticated Next.js form.
  3. Business owner can submit the form (unauthenticated) to confirm/update name, owner, address, phone, website, status; the submission writes to a service-role-only `form_responses` table — anon clients cannot reach `verifications` directly.
  4. Each form response appears in the admin review queue; admin approval writes a new verification with `method='email_response'`, `confidence=0.95`; rejection leaves no verification.
  5. Resend bounce/complaint webhook flags bounced addresses on the business record and excludes them from future outreach; admin dashboard shows the funnel (sent → delivered → opened → responded → approved-into-verification).
**Plans:** TBD
**UI hint**: yes

### Phase 5: Analytics & Receipts
**Goal:** Admins can see cost, hit-rate, and status trends at a glance; users get the deduplication payoff visible on every run.
**Depends on:** Phase 4 (outreach funnel widget needs outreach data; other widgets work earlier but ship together)
**Requirements:** ANALYTICS-01, ANALYTICS-02, ANALYTICS-03
**Success Criteria** (what must be TRUE):
  1. Admin dashboard renders cache hit rate over time (per-run and rolling) sourced from `verifications` + `run_rows`.
  2. Admin dashboard shows monthly $ spent vs cap per API key with a daily breakdown; values reconcile against `budget_ledger` rather than only pre-flight estimates.
  3. Admin dashboard shows status distribution (active / likely_closed / closed / uncertain / errored) per run, derived from `business_current_state`.
**Plans:** TBD
**UI hint**: yes

### Phase 6: Decommission Desktop
**Goal:** v1.0 desktop is formally retired with proof that v1.1 meets or beats it on the two reference runs; the milestone closes.
**Depends on:** Phases 0–5
**Requirements:** *(no new REQs — phase exists to validate prior work and execute the cutover)*
**Success Criteria** (what must be TRUE):
  1. v1.1 reproduces a verification run against `business_checker/Runs/BMOSG_All_Businesses_2026-04-30_1619/` and `business_checker/Runs/Alabama_Product_Based_VOBs_2026-04-07_131659_7288/` inputs and matches or exceeds v1.0 eval accuracy.
  2. PROJECT.md "Active" → "Validated" transitions are recorded for every v1.1 requirement; Tkinter GUI and `run_checker.py` are archived under a `v1.0-frozen` git tag.
  3. Repository is tagged `v1.1.0`; STATE.md reflects milestone complete; IVMF staff receive cutover instructions and the desktop app is officially retired.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Foundation | 0/6 | Planned | — |
| 1. Cache-Only Verification | 0/0 | Not started | — |
| 2. Live Verification | 0/0 | Not started | — |
| 3. Manual Workflows | 0/0 | Not started | — |
| 4. Outreach | 0/0 | Not started | — |
| 5. Analytics & Receipts | 0/0 | Not started | — |
| 6. Decommission Desktop | 0/0 | Not started | — |

## Coverage Verification

All 50 v1.1 requirements mapped to exactly one phase:

| Phase | REQ-IDs | Count |
|-------|---------|-------|
| 0 | AUTH-01, AUTH-02, AUTH-03, AUTH-04, CANON-03, CANON-05, CANON-06, CANON-07, CANON-08, ANALYTICS-04 | 10 |
| 1 | CANON-01, CANON-02, CANON-04, JOBS-01, JOBS-05, JOBS-13, EXPORT-01, EXPORT-02, EXPORT-03, EXPORT-05, EXPORT-06, ANALYTICS-05 | 12 |
| 2 | JOBS-02, JOBS-03, JOBS-04, JOBS-06, JOBS-07, JOBS-08, JOBS-09, JOBS-10, JOBS-11, JOBS-12, JOBS-14, EXPORT-04 | 12 |
| 3 | MANUAL-01, MANUAL-02, MANUAL-03, MANUAL-04, MANUAL-05 | 5 |
| 4 | OUTREACH-01, OUTREACH-02, OUTREACH-03, OUTREACH-04, OUTREACH-05, OUTREACH-06, OUTREACH-07, OUTREACH-08, OUTREACH-09 | 9 |
| 5 | ANALYTICS-01, ANALYTICS-02, ANALYTICS-03 | 3 |
| 6 | (regression + cutover; no new REQs) | 0 |
| **Total** | | **50** |

Coverage: 50/50 ✓ — no orphans, no duplicates.

---
*Last updated: 2026-05-14 — Phase 0 in progress (2/6 plans complete)*
