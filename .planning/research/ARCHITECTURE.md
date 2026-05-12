# Architecture Research — v1.1 Web Platform Pivot

**Domain:** Hosted bulk-verification SaaS layered on top of an existing Python verification engine
**Researched:** 2026-05-12
**Confidence:** HIGH (architecture decisions already locked in PROJECT.md; this document maps integration surface)

---

## 1. Overall Topology

```
                              ┌────────────────────────┐
                              │      End Users         │
                              │ (IVMF admin + analyst) │
                              └────────────┬───────────┘
                                           │ HTTPS
                                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          VERCEL  (Next.js 14 App Router)                 │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  UI Pages (RSC)        Route Handlers (Edge/Node)                │    │
│  │  - /runs               - POST /api/upload   (signed URL issuer)  │    │
│  │  - /runs/[id]          - POST /api/runs     (enqueue)            │    │
│  │  - /review             - POST /api/review/* (manual labels)      │    │
│  │  - /outreach           - POST /api/outreach (approve / response) │    │
│  │  - /analytics          - GET  /api/export/[runId]                │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└───────────┬────────────────────────────────────────────┬─────────────────┘
            │ supabase-js (anon + service role)          │ Resend SDK
            │ Realtime WS                                │ (signed tokens)
            ▼                                            ▼
┌──────────────────────────────────────────┐   ┌────────────────────────┐
│            SUPABASE  (us-east)           │   │       RESEND           │
│  ┌────────────────────────────────────┐  │   │  IVMF subdomain        │
│  │  Postgres 15 + extensions:         │  │   │  SPF/DKIM/DMARC        │
│  │   • pg_trgm  (fuzzy matching)      │  │   │  Inbound webhook ───┐  │
│  │   • pgmq     (job queue)           │  │   └─────────────────────┼──┘
│  │   • pgcrypto (HMAC tokens)         │  │                         │
│  │   • uuid-ossp                      │  │                         │
│  ├────────────────────────────────────┤  │                         │
│  │  Tables:                           │  │                         │
│  │   businesses (canonical)           │  │                         │
│  │   verifications (APPEND-ONLY)      │  │                         │
│  │   business_current_state  (MV/tbl) │  │                         │
│  │   runs / run_rows                  │  │                         │
│  │   review_queue / manual_labels     │  │                         │
│  │   outreach_tickets / responses     │  │                         │
│  │   api_keys / budget_ledger         │  │                         │
│  │   audit_log (triggered)            │  │                         │
│  ├────────────────────────────────────┤  │                         │
│  │  Auth (admin / user RBAC)          │  │                         │
│  │  RLS policies on every table       │  │                         │
│  │  Realtime channels (batched)       │  │                         │
│  │  Storage buckets (uploads/exports) │  │                         │
│  └────────────────────────────────────┘  │                         │
└──────────┬───────────────────────────────┘                         │
           │ pgmq pull (long-poll)                                   │
           │ INSERTs / RPC                                           │
           ▼                                                         │
┌──────────────────────────────────────────────────────────────────┐ │
│                   RAILWAY  (Python 3.12 FastAPI worker)          │ │
│  ┌────────────────────────────────────────────────────────────┐  │ │
│  │  workers/                                                  │  │ │
│  │   • dispatcher.py  — pgmq.read(visibility=300s) loop       │  │ │
│  │   • heartbeat.py   — re-enqueue stuck msgs cron            │  │ │
│  │   • verify_job.py  — wraps tools.check_business            │  │ │
│  │   • aggregator_job.py — wraps tools.aggregator             │  │ │
│  │   • outreach_job.py — Resend send + webhook receive ←──────┼──┘
│  │   • eval_job.py    — eval harness in CI (deploy gate)      │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  business_checker/tools/  (PRESERVED, unchanged interface) │  │
│  │   • check_business.py     (Perplexity Sonar)               │  │
│  │   • scrape_website.py     (FireCrawl + HTTP fallback)      │  │
│  │   • columns.py            (schema mapping)                 │  │
│  │   • build_output.py       (Excel — reused for exports)     │  │
│  │   • [REMOVED] cache.py    (replaced by Postgres lookup)    │  │
│  │   • [REMOVED] checkpoint.py (replaced by run_rows table)   │  │
│  └────────────────────────────────────────────────────────────┘  │
└────────────┬──────────────────────────────┬──────────────────────┘
             │ HTTPS                        │ HTTPS
             ▼                              ▼
   ┌─────────────────────┐      ┌─────────────────────┐
   │  Perplexity Sonar   │      │     FireCrawl       │
   └─────────────────────┘      └─────────────────────┘
```

---

## 2. Component Inventory (NEW / MODIFIED / REMOVED)

### NEW — Frontend (Vercel / Next.js)

| Component | Responsibility |
|-----------|----------------|
| `app/(auth)/login` | Supabase Auth UI (magic link + password) |
| `app/runs/page.tsx` | List runs, status badges, cost-to-date |
| `app/runs/[id]/page.tsx` | Live progress (Realtime subscription, batched), pause/resume controls |
| `app/runs/new/page.tsx` | CSV/XLSX upload → signed-URL POST → enqueue |
| `app/review/page.tsx` | Manual review queue (2-of-N matches, low-confidence rows) |
| `app/labeling/page.tsx` | Random-sample labeling UI (eval gold-set additions) |
| `app/outreach/page.tsx` | Outreach ticket approval, response inbox |
| `app/analytics/page.tsx` | Cache-hit rate, $/run, status distribution, eval drift |
| `app/api/upload/route.ts` | Issues Supabase Storage signed URL; inserts `runs` row |
| `app/api/runs/[id]/enqueue/route.ts` | RPC → `pgmq.send` (server-role only) |
| `app/api/outreach/respond/route.ts` | Tokenized public form endpoint (HMAC verify) |
| `app/api/export/[runId]/route.ts` | Calls worker `/export` or signs Storage URL |
| `lib/supabase/server.ts` | Service-role client (server-only) |
| `lib/supabase/client.ts` | Anon client (browser, RLS-bound) |
| `lib/realtime/run-channel.ts` | Subscribe to `run:{id}` broadcasts (2s batches) |

### NEW — Backend (Railway / Python)

| Component | Responsibility |
|-----------|----------------|
| `workers/main.py` | FastAPI app exposing `/health`, `/metrics`, `/export/{run_id}`, internal admin endpoints |
| `workers/dispatcher.py` | Long-polling pgmq consumer; spawns per-job tasks with asyncio semaphore (QPS limiter) |
| `workers/heartbeat.py` | Cron loop: re-enqueues messages whose visibility timeout expired; emits `job_stuck` alerts |
| `workers/jobs/verify_row.py` | One row → cache lookup → `check_business()` → write `verifications` row |
| `workers/jobs/aggregator.py` | Triggered after all rows in a run reach `verifications`; runs multi-pass override logic; upserts `business_current_state` |
| `workers/jobs/outreach_send.py` | Builds Resend payload with HMAC-tokenized response URL; logs `outreach_tickets` row |
| `workers/jobs/outreach_response.py` | Resend inbound webhook → validate HMAC → write `outreach_responses` (status=pending_admin) |
| `workers/jobs/email_receipt.py` | Run-completion email via Resend |
| `workers/jobs/eval_run.py` | CI gate: replays gold set against current prompt/model, blocks deploy on accuracy regression |
| `workers/lib/supabase_client.py` | Postgres client (psycopg or supabase-py, service role) |
| `workers/lib/canonical.py` | EIN auto-merge + 2-of-N field consensus → review queue routing |
| `workers/lib/realtime_batcher.py` | Buffers row-completion events 2s, emits single `runs:{id}` broadcast |
| `workers/lib/budget_guard.py` | Pre-flight cost estimate + monthly cap check before `check_business()` |
| `workers/lib/idempotency.py` | `(run_id, business_id, pass_n)` → ULID idempotency key for retries |

### NEW — Database (Supabase / Postgres)

| Object | Type | Notes |
|--------|------|-------|
| `businesses` | table | Canonical entity; one row per real business; EIN nullable, `match_signals` JSONB |
| `verifications` | table | **APPEND-ONLY**; every check (cache hit, API call, manual, outreach) is a row; idempotency key UNIQUE |
| `business_current_state` | table (not MV) | Materialized via trigger on `verifications` INSERT; holds aggregated status |
| `runs` | table | Upload metadata, status, cost_to_date, paused_at, completed_at |
| `run_rows` | table | One per uploaded row; FK to `runs`; replaces CSV checkpoint; status enum |
| `review_queue` | table | Rows awaiting admin: 2-of-N canonical matches, low-confidence verifications |
| `manual_labels` | table | Gold-set additions from labeling UI |
| `outreach_tickets` | table | Admin-approved sends; HMAC token stored hashed |
| `outreach_responses` | table | Inbound form submissions; status: pending_admin → approved/rejected |
| `api_keys` | table | Admin-managed Perplexity/FireCrawl keys; encrypted at rest |
| `budget_ledger` | table | Append-only spend log; monthly cap enforced via SUM check |
| `audit_log` | table | Trigger-fed; every UPDATE/DELETE on sensitive tables |
| `pgmq.q_jobs` | queue | pgmq queue for verification jobs |
| `pgmq.q_aggregator` | queue | Separate queue for aggregator passes (lower QPS, larger payload) |
| `pgmq.q_outreach` | queue | Separate queue for email sends |
| RLS policies | — | Every table; admin = all, user = own runs only; outreach response endpoint uses service role |
| Trigger `tr_verifications_to_current_state` | trigger | On INSERT: upsert `business_current_state` based on latest pass verdicts |
| Trigger `tr_audit_log` | trigger | On UPDATE/DELETE: insert into `audit_log` |

### MODIFIED — Existing Python (`business_checker/tools/`)

| File | Change | Rationale |
|------|--------|-----------|
| `check_business.py` | **No interface change.** Keeps `check_business(api_key, name, website, city, state) -> dict`. Internal Pattern B aggregator-override logic preserved. | Treated as a pure function the worker wraps. |
| `scrape_website.py` | **No interface change.** Still returns `(text, cost, error)`. | Same. |
| `columns.py` | **Minor.** Add helpers that map dict result → `verifications` table columns. | Bridges Python tool output to DB row. |
| `build_output.py` | **Modified.** Refactor `build_output_excel(input_path, output_path, checkpoint_path)` to also accept a list of `verification` dicts loaded from Postgres (not just CSV). Two-source signature. | Export endpoint needs to read DB, not CSV; output format unchanged. |

### REMOVED — Existing Python

| File | Reason for removal |
|------|---------------------|
| `tools/cache.py` | Replaced by Postgres lookup against `business_current_state` keyed on canonical `business_id`. Old (name+city+state) hash key misses variants — flagged in PROJECT.md known issues. |
| `tools/checkpoint.py` | Replaced by `run_rows` table; thread-safe by definition via row-level locks. |
| `run_checker.py` | Replaced by `workers/dispatcher.py`. Concurrency control moves from `ThreadPoolExecutor` to asyncio semaphore per-key (tier-aware QPS). |
| `business_checker_gui.py` | Frozen at v1.0. Web UI replaces it. |

---

## 3. Integration Points

### Worker ↔ Existing Python Tools

The Railway worker imports `business_checker.tools.check_business` and `business_checker.tools.scrape_website` **as-is**. The Python verification engine becomes a library; the worker is a thin adapter:

```python
# workers/jobs/verify_row.py — illustrative shape
from business_checker.tools.check_business import check_business

async def run(job: VerifyRowJob) -> None:
    # 1. Canonical lookup
    biz = await canonical.resolve(job.name, job.city, job.state, job.ein)
    if biz and (cached := await db.current_state(biz.id, max_age_days=30)):
        await db.insert_verification(_as_cache_hit(biz, cached, job))
        return

    # 2. Budget guard
    if not await budget_guard.allow(estimated_cost=0.005):
        await db.pause_run(job.run_id, reason="budget_exhausted")
        return

    # 3. Existing Python tool (unchanged)
    result = check_business(
        api_key=await api_keys.current_perplexity(),
        name=job.name, website=job.website,
        city=job.city, state=job.state,
    )

    # 4. Append-only write with idempotency
    await db.insert_verification(
        idempotency_key=ulid(job.run_row_id, pass_n=1),
        business_id=biz.id,
        run_id=job.run_id,
        source="perplexity_sonar",
        **columns.result_to_row(result),
    )

    # 5. Realtime (batched)
    realtime_batcher.enqueue(job.run_id, job.run_row_id, result["status"])
```

**Critical:** the worker never reaches into `cache.py` or `checkpoint.py`. State lives in Postgres exclusively.

### Worker ↔ Supabase

- **Inbound:** pgmq long-poll with `vt=300s` (5-min visibility timeout). Worker calls `pgmq.delete(msg_id)` only after `verifications` INSERT succeeds.
- **Outbound writes:** psycopg via PgBouncer transaction-mode pooler (Supabase pooler endpoint). Service role JWT. RLS bypassed by service role for writes; SELECTs scoped explicitly by `run_id`/`user_id`.
- **Realtime:** worker calls `realtime.send(channel='runs:{id}', event='progress', payload={...})` via `pg_notify` wrapper. Batched 2s by `realtime_batcher`.

### Next.js ↔ Supabase

- **Browser → Supabase:** anon JWT, RLS-enforced. User sees only own runs/rows.
- **Server routes → Supabase:** service-role JWT, server-only env. Used for `pgmq.send`, audit-bypass admin ops, signed-URL minting.
- **Realtime subscription:** browser subscribes to `runs:{id}` channel filtered by RLS on `run_rows`.

### Worker ↔ External APIs

| API | Caller | Auth | Failure handling |
|-----|--------|------|------------------|
| Perplexity Sonar | `tools/check_business.py` (unchanged) | Admin-managed key fetched from `api_keys` at job start | Existing retry/backoff preserved; 4xx → log error verification (NOT cached); 429 → re-enqueue with backoff |
| FireCrawl | `tools/scrape_website.py` (unchanged) | Admin-managed key | Existing fallback to direct HTTP preserved |
| Resend | `workers/jobs/outreach_send.py` (new) | API key in worker env | 5xx → re-enqueue; webhook signature required for inbound |

### Resend → Worker (inbound)

Inbound email webhook hits `POST workers/outreach/webhook`. HMAC signature header verified; token (in `From` reply-to or form URL) is HMAC-validated against `outreach_tickets.token_hash`. Response row inserted with `status='pending_admin'` — **never auto-promoted to verification**. Admin approval in UI flips it.

---

## 4. State Transition Map (today → tomorrow)

| Concern | v1.0 (desktop) | v1.1 (web) | Migration point |
|---------|----------------|------------|-----------------|
| Per-business result cache | `cache/results.db` SQLite (name+city+state hash) | `businesses` + `business_current_state` (canonical id) | Phase 2 (cache-only verification) |
| Per-run progress | `Runs/<ts>/checkpoint.csv` (thread-safe lock) | `run_rows` table (row-level locks) | Phase 2 |
| Pass history & override input | In-memory list aggregated by `run_checker.py` | `verifications` rows; aggregator reads via SELECT | Phase 3 (live verification) |
| Aggregated verdict | Computed at end of run, written to Excel | `business_current_state` (trigger-maintained on verifications INSERT) | Phase 3 |
| Run output | `Runs/<ts>/output.xlsx` | Supabase Storage; built on-demand by `build_output.py` reading DB | Phase 2 |
| API keys | User's `.env` | `api_keys` table (admin-managed, encrypted) | Phase 1 (foundation) |
| Cost tracking | Per-run log line | `budget_ledger` append-only; monthly cap enforced | Phase 1 |
| Concurrency control | `ThreadPoolExecutor(max_workers=N)` | Asyncio semaphore + pgmq fan-out | Phase 3 |

---

## 5. Critical Data Flows

### Flow A — CSV upload → results

```
User                Next.js              Supabase             Railway Worker        Perplexity
 │                    │                     │                      │                   │
 │ Upload XLSX ─────► │                     │                      │                   │
 │                    │ Mint signed URL ──► │ (Storage: uploads/)  │                   │
 │ ◄─ signed URL ──── │                     │                      │                   │
 │ PUT file ────────────────────────────────►│                     │                   │
 │                    │ INSERT runs(status='parsing')              │                   │
 │                    │ pgmq.send(q='parse', run_id) ─────────────►│                   │
 │                    │                     │                      │ Parse XLSX        │
 │                    │                     │ ◄──INSERT run_rows[] │                   │
 │                    │                     │                      │ For each row:     │
 │                    │                     │                      │  pgmq.send(verify)│
 │                    │                     │                      │                   │
 │                    │                     │   (verify queue is drained by dispatcher)│
 │                    │                     │                      │ canonical.resolve │
 │                    │                     │ ◄──SELECT business_current_state         │
 │                    │                     │     (cache hit? skip API)               │
 │                    │                     │                      │ check_business() ►│
 │                    │                     │                      │ ◄──────────────── │
 │                    │                     │ ◄──INSERT verification                  │
 │                    │                     │     (trigger: upsert business_current_state)
 │                    │                     │ ◄──realtime.send(runs:{id}, batch 2s)   │
 │ ◄── live progress ─────────────────────  │                      │                   │
 │                    │                     │   When all rows done:                    │
 │                    │                     │   pgmq.send(q='aggregator', run_id)     │
 │                    │                     │                      │ Multi-pass agg    │
 │                    │                     │ ◄──UPDATE business_current_state        │
 │                    │                     │ ◄──UPDATE runs(status='complete')       │
 │                    │                     │                      │ Resend receipt    │
 │ ◄── email + ────────────────────────────────────────────────────│                   │
 │     export link    │                     │                      │                   │
```

### Flow B — Credit exhaustion → resume

```
Worker                                     Supabase
 │                                            │
 │ check_business() → 401/insufficient_funds  │
 │ budget_guard or API error caught           │
 │ INSERT verifications(error='credit_exhausted', source=...)
 │ UPDATE runs SET status='paused', paused_reason='budget' ───►
 │ pgmq does NOT delete msg → visibility expires → returns to queue
 │ (but dispatcher skips when run.status='paused')             │
 │ realtime.send(runs:{id}, event='paused')  ─────────────────►│
 │                                                              │
 │  ... admin tops up key in UI, clicks Resume ...              │
 │                                                              │
 │ Next.js: UPDATE runs SET status='running', api_key_id=X      │
 │          pgmq.send(q='resume', run_id)                       │
 │                                                              │
 │ Worker resume job:                                           │
 │   SELECT run_rows WHERE run_id=X AND status IN ('pending','errored_retryable')
 │   re-enqueue each (idempotency_key dedupes against any in-flight) ─►
```

The `verifications` append-only contract means resuming never loses prior partial work — completed rows are simply skipped (idempotency_key collision on retry).

### Flow C — Manual review → verification write

```
Admin                Next.js              Supabase
 │                     │                      │
 │ Opens /review       │                      │
 │ ────────────────────►SELECT review_queue WHERE assignee IS NULL OR =me
 │ ◄─ rows ─────────── │                      │
 │ Picks row, decides "Active"                │
 │ POST /api/review/[id]/resolve              │
 │                     │ Service role:        │
 │                     │  INSERT verifications(                    │
 │                     │   source='manual_review',                 │
 │                     │   reviewer_id=user, status='Active', ...) │
 │                     │  UPDATE review_queue SET resolved_at=now  │
 │                     │  (trigger updates business_current_state) │
 │                     │  (audit_log row written)                  │
 │ ◄─ 200 ───────────  │                      │
```

Key invariant: admin actions **never UPDATE verifications**; they always INSERT a new row with `source='manual_review'`. Audit trail is the row sequence on the same `business_id`.

### Flow D — Form response → admin approval → verification

```
Business owner         Resend            Worker webhook        Supabase           Admin
   │                     │                    │                   │                  │
   │ Receives email      │                    │                   │                  │
   │ (token URL embedded)│                    │                   │                  │
   │ Clicks link, submits form ──► /api/outreach/respond           │                  │
   │                     │                    │ (Next.js)         │                  │
   │                     │                    │ HMAC verify token │                  │
   │                     │                    │ INSERT outreach_responses(status='pending_admin')
   │                     │                    │                   │ realtime to admin
   │                     │                    │                   │ ────────────────►│
   │                                                              │                  │
   │       (Alternative: email reply → Resend inbound webhook)    │                  │
   │                     │ POST webhook ─────►│ /outreach/webhook │                  │
   │                     │                    │ HMAC verify, parse│                  │
   │                     │                    │ INSERT outreach_responses             │
   │                                                              │                  │
   │                                                              │ Admin reviews    │
   │                                                              │ ◄────────────────│
   │                                                              │ Approves         │
   │                                                              │ INSERT verification(source='outreach', ...)│
   │                                                              │ UPDATE outreach_responses(status='approved')
   │                                                              │ (trigger → business_current_state)│
```

Auto-promotion is explicitly out of scope (PROJECT.md). Token spoofing is mitigated by HMAC; double-submit by `(ticket_id, response_hash)` UNIQUE.

---

## 6. Cross-Cutting Concerns

### Multi-Pass Aggregator — server-side execution

**Decision: event-driven via dedicated pgmq queue, NOT cron.**

- When the last `run_row` for a run transitions to `verified`, a Postgres trigger inserts a message into `pgmq.q_aggregator` with payload `{run_id, pass_n}`.
- `workers/jobs/aggregator.py` reads the message, SELECTs all `verifications` for businesses in the run, runs the existing override logic (currently inline in `check_business.py` Pattern B + `run_checker.py` multi-pass loop — extract into `business_checker/tools/aggregator.py` during Phase 3), and writes consolidated rows back as new `verifications` with `source='aggregator_pass_N'`.
- The trigger on `verifications` upserts `business_current_state` automatically — no separate update step.
- Cron is only used for the heartbeat watchdog and the weekly eval drift run, not for aggregator dispatch.

Why not a Postgres materialized view: refresh cost on a 50k-row run is unbounded and blocks readers. A regular table maintained by trigger gives O(1) per-INSERT amortization.

### Realtime backpressure

The naive pattern — emit one Realtime broadcast per `verifications` INSERT — caused reconnect storms in load tests of similar systems (Supabase docs caution at >10 msgs/s/channel). Mitigation:

- `workers/lib/realtime_batcher.py` buffers row-completion events per `run_id` in an asyncio queue.
- Flush every 2s OR every 100 events, whichever comes first.
- Single broadcast payload: `{counts: {active: 12, closed: 3, ...}, recent: [last 20 row summaries], run_progress: 0.42}`.
- Client merges incrementally; full state available on reconnect via `SELECT business_current_state WHERE run_id=...`.

### RLS interaction with service-role-only outreach

The outreach response endpoint must accept POSTs from unauthenticated browsers (business owners clicking email links). Resolution:

- The public `POST /api/outreach/respond` route in Next.js is unauthenticated **at the HTTP layer** but uses the service-role Supabase client **server-only**.
- Token in URL is HMAC-validated against `outreach_tickets.token_hash` *before* any DB write. Failures return 404 (do not leak ticket existence).
- The `outreach_responses` table has RLS: `INSERT` denied for anon; only service role can write. Reads scoped to admin.
- The Resend inbound webhook hits the **worker** (Railway), not Next.js — separation reduces frontend attack surface and lets HMAC verification share `outreach_tickets` access with send-side logic.
- Service role JWT lives in Railway env + Vercel server env only; never shipped to browser.

### Idempotency

Every retryable write carries `idempotency_key = ulid(run_row_id, pass_n, source)`:

- `verifications.idempotency_key UNIQUE` — duplicate INSERTs from FireCrawl 429-retry storms become no-ops.
- pgmq `vt=300s` + heartbeat: if a worker dies mid-job, message reappears; idempotency key prevents double-write of the verification, double-bill of the API, and double-count in `budget_ledger`.

### Audit log

`audit_log` is fed by a generic trigger on every UPDATE/DELETE on `runs`, `review_queue`, `outreach_*`, `api_keys`, `manual_labels`. INSERTs on `verifications` are themselves the audit trail (append-only) so no trigger needed there.

---

## 7. Suggested Build Order (Phase Plan)

Each phase ships independently and is demoable. Order is dictated by hard dependencies: auth & schema before any feature, cache before live verify (so cost is bounded during testing), live verify before manual review (review queue depends on real low-confidence rows), outreach last (needs DNS + compliance signoff).

### Phase 1 — Foundation
**Ships:** working login, empty UI shell, worker heartbeat, schema deployed, eval CI gate green.
- Supabase project, full schema migration, RLS policies, audit trigger.
- Next.js skeleton + Supabase Auth + RBAC (admin/user).
- Railway worker scaffold (FastAPI, pgmq dispatcher stub, heartbeat watchdog).
- Python models generated from Postgres schema (`workers/lib/db_models.py`).
- Admin `api_keys` CRUD + `budget_ledger` table + monthly cap RPC.
- Eval harness (`workers/jobs/eval_run.py`) wired to GitHub Actions deploy gate.
- **NEW:** model-gen pipeline (introspect → dataclasses), queue-dispatcher cron, heartbeat watchdog, RLS policy module, audit-log trigger, eval-CI runner.

### Phase 2 — Cache-only verification
**Ships:** CSV upload → canonical match → result from cache OR `Uncertain (not yet verified)` → CSV/XLSX export. Zero API calls.
- CSV/XLSX upload route + Storage signed URLs.
- Parse job populates `run_rows`.
- Canonical matching (`workers/lib/canonical.py`): EIN auto-merge, 2-of-N → `review_queue`.
- DB-backed cache lookup against `business_current_state`.
- `build_output.py` modified to read DB and emit XLSX matching v1.0 column layout.
- Realtime progress wired (batched).
- **Validates:** schema, RLS, Realtime backpressure, export format parity — all without spending a cent.

### Phase 3 — Live verification
**Ships:** end-to-end run on real APIs; multi-pass aggregator producing `business_current_state`; pause/resume on credit exhaustion.
- Wrap `tools.check_business` in `workers/jobs/verify_row.py`.
- Extract multi-pass logic from `run_checker.py` into `business_checker/tools/aggregator.py`; wrap in `workers/jobs/aggregator.py`.
- Trigger on last-row-complete → enqueue aggregator.
- Trigger on `verifications` INSERT → upsert `business_current_state`.
- Budget guard pre-flight + per-call check.
- Pause/resume UI + dispatcher gating on `runs.status`.
- Eval harness regression gate enforced on every deploy.

### Phase 4 — Manual workflows
**Ships:** review queue functional, random-sample labeling adds to gold set, admin DB editor produces new `verifications` with audit trail.
- `/review` UI consuming `review_queue`.
- `/labeling` random-sample UI → `manual_labels` → eval gold-set integration.
- Admin editor writes new `verifications` (source=manual), never UPDATE.

### Phase 5 — Outreach
**Ships:** admin approves tickets → Resend sends → owner submits form → admin approves → verification written.
- DNS records live (IT-blocked).
- Compliance signoff on PII (Jim-blocked).
- `outreach_tickets` admin approval flow.
- `outreach_send` job with HMAC token minting.
- Public response form + worker webhook.
- Admin approval UI → verification write.

### Phase 6 — Analytics + receipts
**Ships:** dashboard, weekly eval drift alerts, run-completion emails.
- `/analytics` views over `verifications`, `budget_ledger`, `outreach_*`.
- Cron: weekly eval run → drift alert via Resend if accuracy delta >2%.
- Run-completion email receipt job.

### Phase 7 — Decommission desktop
**Ships:** v1.1 declared GA; v1.0 archived.
- Final regression vs reference Runs (BMSG + Alabama VOB).
- Update PROJECT.md Validated list.
- Tag `v1.1.0`.

---

## 8. Architectural Patterns Applied

### Pattern: Append-Only Ledger + Materialized Current State
- `verifications` = ledger. Never UPDATE.
- `business_current_state` = projection. Trigger-maintained.
- **Trade-off:** storage grows linearly with checks; mitigated by partition-by-month on `verifications` if needed at scale.

### Pattern: Visibility-Timeout Queue + Idempotency Key
- pgmq `vt=300s` gives at-least-once delivery.
- Idempotency key on `verifications` makes the consumer exactly-once at the effect level.

### Pattern: Batched Broadcast
- Realtime events batched 2s to avoid client reconnect storms above ~10 msgs/s/channel.

### Pattern: Service Role at the Edge
- Service role JWT used in Next.js server routes + Railway worker.
- Anon JWT for browser; RLS does the rest.
- Public unauthenticated endpoints (outreach response) use service role with HMAC token validation.

---

## 9. Anti-Patterns to Avoid

| Anti-pattern | Why it's wrong | Do instead |
|--------------|----------------|------------|
| UPDATE on `verifications` | Destroys audit trail; defeats the append-only contract | INSERT new row with new `source` value |
| Realtime broadcast per row | Reconnect storms above 10 msgs/s | Batch 2s in `realtime_batcher` |
| pgmq `vt=30s` default | Long Perplexity calls (15-30s) + retries blow past timeout | Set `vt=300s` explicitly |
| Materialized view for `business_current_state` | REFRESH blocks readers on large runs | Regular table + trigger upsert |
| Service role in browser | Total RLS bypass = data breach | Service role server-only env var |
| Auto-promote outreach responses to verifications | Token spoofing risk | Admin approval required (PROJECT.md decision) |
| Cron-based aggregator dispatch | Race against in-flight rows; latency | Trigger on last-row-complete + pgmq |
| Reimplementing `check_business.py` | Loses Pattern B aggregator-override logic, breaks eval gold-set | Import as library, wrap in worker job |

---

## 10. Scaling Considerations

| Scale | Bottleneck | Mitigation |
|-------|------------|------------|
| Today (single IVMF tenant, 50k-row uploads) | Perplexity QPS cap (Tier 2 = 8 QPS) | Asyncio semaphore matches tier |
| 10x volume (multiple departments, weekly runs) | `verifications` table size | Monthly partitioning; archive older partitions to cold storage |
| Eval drift over time | Prompt rot; world changes (businesses close) | Weekly eval cron + drift alert; mandatory deploy gate |
| Pgmq backlog | Single-worker throughput | Scale Railway worker replicas; pgmq is multi-consumer safe |

---

## 11. Open Questions for Roadmapper

1. **Phase 2 vs Phase 3 cutover:** Phase 2 ships a working web app that can never call an API. Is this acceptable as a demo to Jim, or should Phases 2 and 3 be folded together?
2. **Aggregator extraction timing:** Currently the multi-pass loop lives in `run_checker.py` and Pattern B override lives in `check_business.py`. Extracting into `business_checker/tools/aggregator.py` is a Phase 3 task but could happen during v1.0 cleanup if a polishing pass is desired first.
3. **Storage for uploads:** XLSX uploads contain PII. Default Supabase Storage bucket is fine for v1.1, but compliance signoff may require encryption-at-rest beyond the default. Track as a Phase 5 (outreach) precondition since that's when PII first hits external (Perplexity) — though arguably the upload itself is the boundary.

---

*Architecture research for: IVMF Business Checker v1.1 Web Platform Pivot*
*Researched: 2026-05-12*
