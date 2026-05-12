# Pitfalls Research

**Domain:** Bulk business verification SaaS — Python verification engine + Next.js app + Supabase-only shared state
**Researched:** 2026-05-12
**Confidence:** HIGH (stack-specific; informed by v1.0 production behavior and known failure modes of pgmq/Realtime/RLS/Pydantic-Postgres splits)

This file enumerates mistakes specific to: (a) migrating an existing Python verification engine to a worker-app split, and (b) using Supabase as the only shared state between a Railway Python worker and a Vercel Next.js frontend. Generic web-app pitfalls are excluded.

---

## Critical Pitfalls

### Pitfall 1: Double-billing on FireCrawl/Perplexity retries (no idempotency key on the API call itself)

**What goes wrong:**
Worker calls Perplexity, request takes 45s, network blip, worker retries, both requests complete, both are billed, and **both attempt to insert a `verifications` row**. A naive `INSERT` either creates duplicates or, with a unique constraint, the second insert fails and the worker treats it as a hard error and retries the whole row again — compounding the bill.

**Why it happens:**
Developers put the idempotency key on the DB row (good) but not on the upstream API call, and they put retry logic at the wrong layer (around the whole verify-and-insert block instead of around the API call only). pgmq visibility-timeout redelivery then re-runs the entire job from the top.

**Warning signs:**
- Perplexity dashboard cost diverges from `cost_estimate_cents` sum on `verifications` by >5%
- Same `(run_row_id, pass_no)` shows multiple insert attempts in worker logs
- FireCrawl 429 + retry storm after a transient Cloudflare blip; bill doubles overnight

**How to avoid:**
- Generate `idempotency_key = hash(run_row_id, pass_no, prompt_hash)` **before** the API call
- Send it in the Perplexity/FireCrawl request headers where supported; store it locally as a dedup lock (Postgres advisory lock or `INSERT … ON CONFLICT DO NOTHING RETURNING` on an `api_calls` table) **before** spending money
- pgmq message handler must be: (1) check `api_calls` table for prior success → return cached result; (2) only then call upstream
- `verifications` row insert is `ON CONFLICT (idempotency_key) DO NOTHING` — never raises

**Phase to address:** Phase 2 (Live verification) — must land with the first real upstream call. Schema lands in Phase 0.

---

### Pitfall 2: Realtime reconnect storms during long runs

**What goes wrong:**
Worker emits one Realtime event per row (e.g. 12,000 events for a 12k upload). Browsers on flaky wifi reconnect, replay backlog, and either crash the tab or thunder the Supabase Realtime quota. On Vercel, multiple admin tabs amplify the storm.

**Why it happens:**
"Realtime progress" is interpreted as per-row events. Devs forget Realtime is fan-out, not fan-in: every subscriber pays for every event. Default channel auth doesn't rate-limit.

**Warning signs:**
- Supabase Realtime quota warnings during a single large run
- Progress UI freezes for 30+ seconds, then jumps 1000 rows
- Browser memory grows linearly with run length

**How to avoid:**
- Worker writes per-row to DB but **batches Realtime broadcasts** to one event per N seconds (or every M rows), payload = aggregate counts only
- Use a `run_progress` table with `(run_id, completed, failed, in_flight, updated_at)` updated via `UPDATE … SET …` every 2s; Realtime subscribes to that single row, not to `verifications`
- Frontend reads detailed rows on-demand via paginated query, not via Realtime
- Set Realtime RLS to deny anon; only the row owner + admin can subscribe

**Phase to address:** Phase 2 (Live verification) — design the progress channel before wiring any UI.

---

### Pitfall 3: RLS forgotten on anonymous outreach form writes

**What goes wrong:**
Tokenized outreach form lets a business owner click an email link and self-attest "we're still operating." The form posts to a Supabase table. Without scoped RLS, anyone with the anon key can read or write any row. Worse, a spoofed token can write to a *different* business's outreach response.

**Why it happens:**
The form must accept **unauthenticated** writes (the recipient is not a Supabase user), so devs disable RLS on the `outreach_responses` table "temporarily." Then they ship.

**Warning signs:**
- `outreach_responses` has policies like `USING (true)` or RLS is `DISABLED`
- Tokens are non-cryptographic (sequential, short, or guessable)
- Form endpoint accepts the token in the body, not validated server-side against a hashed column

**How to avoid:**
- Never write directly from the browser to Supabase for outreach. Route through a **Next.js route handler** (server-side) that validates the token against `outreach_tickets.token_hash` (sha256) before inserting
- Token is 32-byte random, single-use, expires in 14 days, hashed in DB
- `outreach_responses` RLS: `INSERT` denied to anon entirely; only the service-role-key path (used by the route handler after validation) can insert
- Submissions write to a *pending* state; admin approval (Phase 4) flips it to verification — never auto-promote

**Phase to address:** Phase 4 (Outreach). Token + RLS design must be in the phase 4 entry checklist.

---

### Pitfall 4: Schema drift between Python Pydantic models and Postgres

**What goes wrong:**
Schema lands in Supabase via SQL migrations. Python worker has hand-written Pydantic models. Six weeks later a column is added (`notes_md`), the migration ships, the worker keeps deserializing without it, then a different column is *renamed* and the worker silently writes to a column that no longer exists — or worse, writes the wrong column because Pydantic ignores unknown fields by default.

**Why it happens:**
Two sources of truth. Devs treat the SQL schema as canonical for the frontend (via supabase-js types generation) but maintain a parallel Pydantic model by hand for the worker.

**Warning signs:**
- Worker inserts silently succeed but values land in wrong columns
- Adding a NOT NULL column breaks the worker only at runtime
- Frontend types updated; worker still uses old field names

**How to avoid:**
- **Generate Pydantic models from Postgres schema** as a build step. Use `datamodel-code-generator` with `--input-file-type=jsonschema` fed by `supabase gen types` (or a direct `pg_dump --schema-only` + a converter). Commit generated models to repo with a CI check that fails if regenerating produces a diff.
- Pydantic `model_config = ConfigDict(extra='forbid')` so unknown fields raise loudly
- Worker startup: run a schema-version handshake — query `pg_catalog` for expected columns; refuse to start if schema hash differs from what worker was built with
- Treat SQL migrations as the only source of truth; never edit Pydantic by hand

**Phase to address:** Phase 0 (Foundation) — the codegen pipeline is part of the bootstrap. If skipped now, every later phase compounds the drift.

---

### Pitfall 5: Canonical match silent merge (the EIN-collision / shared-address trap)

**What goes wrong:**
2-of-N field consensus matches two different businesses that share a registered-agent address and a generic phone (e.g., LegalZoom-formed LLCs in Wyoming). Worker silently merges them into one `business_id`. Future verifications now apply to "Acme Holdings LLC and 14 other LLCs sharing this address" — the gold set is poisoned and the analytics dashboard reports impossible status changes ("active → closed → active" within hours).

**Why it happens:**
Adversarial review (per PROJECT.md) caught EIN auto-merge as the only safe auto-merge. Devs forget that 2-of-N can still produce false positives at scale; they ship "2-of-N → admin review queue" but the queue triggers only on *new* matches, not on retroactive matches when a new business is added that links two previously-separate businesses.

**Warning signs:**
- A single `business_id` has wildly inconsistent verification history (active/closed flip-flops with no admin edits)
- `business_current_state` has businesses with >1 EIN ever attached
- pg_trgm similarity scores on merged businesses are clustered around the 2-of-N threshold

**How to avoid:**
- EIN auto-merge: only when EIN is non-null on both sides AND matches exactly. Validate EIN format before storing.
- 2-of-N matches always create a `match_candidate` row, never auto-link. Admin must approve. Never auto-promote on age.
- Detect "registered agent" / "answering service" / "holding company" patterns: maintain a blocklist of high-collision addresses, phones, and domains (e.g., `*.wixsite.com`, common RA addresses) — these fields do NOT count toward 2-of-N consensus
- Periodic job: re-validate all merges nightly; flag if pg_trgm similarity has decayed below threshold
- Append-only: a merge is a `merge` row in an audit table referencing source `business_id`s; un-merge is supported

**Phase to address:** Phase 1 (Cache-only) — canonical model lands here. Blocklist + match_candidate flow is part of acceptance.

---

### Pitfall 6: Aggregator phantom reads during concurrent pass writes

**What goes wrong:**
Multi-pass aggregator reads all passes for a `(run_id, run_row_id)` from `verifications`, applies override logic, writes to `business_current_state`. With 3–8 concurrent workers, Pass 2 finishes and triggers aggregation *while* Pass 3 is mid-insert; aggregator sees only Passes 1–2, decides "uncertain," writes that, and never re-runs after Pass 3 lands. Result: `business_current_state` reflects an incomplete pass set.

**Why it happens:**
The worker treats each pass as independent. Aggregation is triggered eagerly on each pass complete. There's no "all passes for this row are done" barrier. pgmq doesn't natively express dependencies.

**Warning signs:**
- `business_current_state.status` disagrees with the last row in `verifications` for the same business
- Re-running the aggregator manually on the same data produces different results
- Eval harness regression spikes after enabling concurrency increase

**How to avoid:**
- `run_rows` row has `passes_completed` counter; atomically incremented via `UPDATE … SET passes_completed = passes_completed + 1 RETURNING passes_completed`
- Aggregator only fires when `passes_completed = passes_required` (gate condition returned by the UPDATE)
- Aggregator query uses `SELECT … FOR UPDATE` on `business_current_state` row to serialize writes for the same business across concurrent workers
- All reads in the aggregator transaction use `REPEATABLE READ` isolation
- Belt-and-suspenders: a nightly reconciliation job re-aggregates all rows where `verifications.created_at > business_current_state.updated_at`

**Phase to address:** Phase 2 (Live verification) — concurrency lands here. Aggregator barrier must ship with the first live-pass write.

---

### Pitfall 7: Cost cap drift — local tally vs provider truth

**What goes wrong:**
Worker tracks "cents spent this month" by summing `cost_estimate_cents` on inserted `verifications` rows. Budget cap = $500/month. But the local estimate uses fixed per-call costs, while Perplexity actually charges variably (tokens in/out, model tier), and FireCrawl charges per credit, not per call. After a month, provider invoice is $720, app shows $487, no cap ever tripped.

**Why it happens:**
Real cost is only knowable from the provider. Devs build the cap on the only number they have at write-time (estimate) and never reconcile.

**Warning signs:**
- Monthly invoice from Perplexity/FireCrawl >10% above app's tally
- "Cost remaining" graph keeps decreasing smoothly while real spend has already spiked
- A single bad upload (large content scrapes) makes the gap blow out

**How to avoid:**
- Pre-flight estimate cap: cheap, fast, conservative (worst-case token count × max model cost) — hard stop on enqueue if estimated remaining < estimated run cost
- Live tally cap: updated per-call from the provider's response headers (Perplexity returns usage; FireCrawl returns credits consumed) — hard stop on **each call** if running tally + this call's projected cost > cap
- Daily reconciliation job: hit Perplexity/FireCrawl billing APIs, write `provider_truth_cents` to `api_keys` table, alert if drift > 5%
- Two caps: a soft cap at 80% (warns admin, pauses non-priority runs) and a hard cap at 100% (kills all runs, requires admin unpause)

**Phase to address:** Phase 0 (admin keys table + cap fields) + Phase 2 (live tally + provider reconciliation). Reconciliation lands no later than Phase 2 exit.

---

### Pitfall 8: Eval gold set RLS-filtered in CI (false-pass regression gate)

**What goes wrong:**
Eval harness queries Supabase for the gold set using the **anon** key (or a user-scoped key) because that's what's in CI env. RLS filters out rows the test user can't see. The gold set looks smaller than it is — sometimes empty. Eval reports 100% accuracy on 0 rows. CI passes. Prompt regression ships to production.

**Why it happens:**
Devs treat Supabase keys interchangeably. The service-role key is "scary" so they default to anon. RLS is invisible — no error, just missing rows.

**Warning signs:**
- Eval log shows `n_examples=0` or far fewer than expected
- Eval passes despite a prompt change that obviously broke accuracy locally
- `count(*)` from the gold-set table differs between worker and CI

**How to avoid:**
- Eval harness uses the **service-role key** stored as a CI secret (with the runner restricted to the eval job only)
- Eval entry point asserts `n_examples >= EXPECTED_MIN_GOLD_SIZE` and **fails** if not — never silently passes on empty
- Separate `eval_gold` table with `service_role_only` RLS policy (deny everyone else explicitly) — makes the access path obvious
- CI job logs the row count of the gold set as a first step; PR review checks the number didn't drop

**Phase to address:** Phase 2 (eval-in-CI lands here). Gold-set count assertion is a phase-2 acceptance criterion.

---

### Pitfall 9: Run immutability violated by admin "edits"

**What goes wrong:**
Admin notices a misclassification, opens the DB editor (Phase 3), and updates `business_current_state.status` directly. Audit ledger isn't aware. Later, IVMF asks "why was this business marked active on April 1?" — and the answer in the DB is "closed," with no record of the change.

**Why it happens:**
"Append-only" is enforced for the verification engine but not for the admin UI, because the admin UI was built later and a direct `UPDATE` was the obvious path.

**Warning signs:**
- `business_current_state.updated_at` newer than the latest `verifications.created_at` for that business
- Diffing nightly snapshots shows status changes without corresponding verification rows
- Admin can edit fields in the UI without a "reason" prompt

**How to avoid:**
- Database trigger: `BEFORE UPDATE` on `business_current_state` (and `verifications`) raises unless the session has set a local variable `app.admin_edit_id` referring to a row in `admin_edits` (with reason, actor, timestamp)
- The admin UI's "edit" action actually **inserts a new `verifications` row** with `source='admin_edit'`, then the aggregator recomputes `business_current_state` — the admin never UPDATEs the canonical table directly
- `verifications` has a trigger that blocks UPDATE/DELETE entirely (`BEFORE UPDATE … RAISE EXCEPTION`); only INSERT is allowed
- Audit ledger is a separate table with `INSERT`-only RLS and no UPDATE/DELETE policy at all

**Phase to address:** Phase 3 (Manual workflows) — admin UI lands here. Triggers ship before the UI does, not after.

---

### Pitfall 10: PII boundary leak to external APIs

**What goes wrong:**
Verification prompt includes owner name + home address (some MWBE filings list owner residence). Sent to Perplexity. Perplexity's data retention policy may include training; even if not, the data has left the IVMF boundary without compliance signoff. Jim escalates; outreach phase blocked indefinitely.

**Why it happens:**
The v1.0 desktop app already sent business name + city + state to Perplexity (low-risk). The web pivot reuses the prompt template. Nobody re-audits the input fields when the worker accepts uploads with new columns.

**Warning signs:**
- Upload schema accepts arbitrary columns (free-form CSV)
- No allowlist for which fields are passed to external APIs
- No PII scan on uploaded data
- Compliance signoff is on the project plan but not on a phase gate

**How to avoid:**
- Explicit allowlist of fields permitted in the prompt: `business_name`, `city`, `state`, `naics`, `website`. Everything else stays in Postgres.
- Pre-flight PII scan on upload: regex for SSN, DOB, residence address patterns; reject or mask before the row enters the queue
- Compliance signoff is a **phase-4 entry gate** (blocks outreach launch); for phases 0–2, the allowlist is the defense
- Document the PII boundary in a `model_card.md` shipped with the worker
- Log every outbound API payload (truncated, with PII fields nulled) to a `api_calls` audit table — provable boundary

**Phase to address:** Phase 0 (allowlist + scan land at upload-ingest design). Phase 4 (outreach) requires compliance signoff before launch.

---

### Pitfall 11: pgmq visibility-timeout misconfigured for hours-long jobs

**What goes wrong:**
pgmq message has a 30s visibility timeout (default-ish). Worker pulls a job, starts a 10-minute Perplexity scrape, message becomes visible to another worker at 30s, second worker pulls and starts the same job, both bill the API. Or worker is restarted (Railway deploy), in-flight messages re-deliver, partially completed rows get re-processed without idempotency protection.

**Why it happens:**
pgmq defaults aren't tuned for long jobs. Devs read the README, ship, and learn at scale.

**Warning signs:**
- Duplicate `api_calls` rows for the same `idempotency_key`
- Worker logs show "already processed, skipping" frequently (signal that dedup is catching things that *would* have been double-billed)
- Railway deploys cause cost spikes

**How to avoid:**
- Visibility timeout >> worst-case row duration. For per-row jobs: 5 min. For batch jobs: 30+ min. Configure per-queue.
- Worker emits a **heartbeat** every N seconds that extends visibility via `pgmq.set_vt(queue, msg_id, new_vt)` — keep the lock alive while genuinely working
- Idempotency keys (Pitfall 1) catch the failures this prevents
- On Railway deploy: `SIGTERM` handler drains the queue (stop pulling new messages, finish in-flight, exit) — Railway grace period is 30s by default; configure higher

**Phase to address:** Phase 0 (queue setup). Heartbeat lands in Phase 2 (long jobs become real then).

---

### Pitfall 12: Realtime channel auth defaults — info leak across users

**What goes wrong:**
User A and User B both upload runs. Realtime channel is `runs:*` (wildcard). Both subscribe. User A sees User B's run progress and row-level data including business names. RLS on the underlying table doesn't apply to Realtime by default unless you've enabled "RLS for Realtime" and written matching policies.

**Why it happens:**
Supabase Realtime RLS for Postgres Changes requires explicit opt-in (per-publication). Broadcast channels have separate auth that devs often skip.

**Warning signs:**
- Browser network tab shows messages for runs the user doesn't own
- No `auth.uid()` check in Realtime policies
- Single channel name used across all users

**How to avoid:**
- Per-user channel naming: `run:{run_id}` where `run_id` is UUID; channel-auth function validates `run.owner_id = auth.uid()` OR `auth.role() = 'admin'`
- Enable RLS on the `run_progress` table for the `supabase_realtime` publication; policy mirrors the run-owner check
- Broadcast/Presence channels use `private: true` with an auth callback
- Test: log in as User A, subscribe to User B's `run:{B_run_id}` — should get 401

**Phase to address:** Phase 0 (auth + RLS scaffolding). Verified in Phase 2 (Realtime ships there).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hand-write Pydantic models instead of generating from schema | Save 1 day in Phase 0 | Pitfall 4 (silent column drift, runtime breakage) | Never — schema drift will bite by Phase 2 |
| Use anon key in worker for "simplicity" | Skip RLS thinking | Worker can't read/write the rows it needs; devs disable RLS to work around it; everything leaks | Never |
| Single Realtime channel for all runs | Simple subscription code | Pitfall 12 (cross-user leak); Pitfall 2 (storms) | Never in production; OK for solo localhost dev |
| Skip idempotency keys in MVP | Faster Phase 1 cache-only | Pitfall 1 reappears the moment Phase 2 ships | Acceptable in Phase 1 *only because* there's no live API call; must land before Phase 2 |
| Aggregator triggered on every pass insert (no barrier) | Simple trigger; "real-time-feeling" updates | Pitfall 6 (phantom reads at concurrency) | Never with concurrency > 1 |
| Eval harness against latest production DB instead of frozen gold set | Always tests "real" data | Gold set drifts; regressions go undetected; can't reproduce historical results | Never — gold set must be frozen + versioned |
| Direct UPDATE in admin UI on `business_current_state` | Easy admin workflow | Pitfall 9 (audit ledger lies) | Never |
| Trust `cost_estimate_cents` for cap enforcement | One number to track | Pitfall 7 (cap drift, $$$ overrun) | Never alone — must reconcile against provider |
| Allow arbitrary CSV columns into prompt | Flexibility for new datasets | Pitfall 10 (PII leak; compliance escalation) | Never — explicit allowlist required |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Supabase pgmq | Default visibility timeout for long jobs | Tune per-queue; heartbeat to extend; SIGTERM drain on deploy |
| Supabase Realtime | Subscribing to row-level changes for high-volume tables | Subscribe to an aggregated `run_progress` row; batch updates server-side |
| Supabase RLS | Forgetting RLS applies separately to Realtime publications | Enable RLS for the `supabase_realtime` publication; write parallel policies |
| Supabase Auth | Using anon key from the worker | Service-role key on worker (kept in Railway secrets); never expose to browser |
| Perplexity Sonar | Treating timeouts as transient → retry without idempotency | Idempotency key + cached result check before retry; respect rate-limit headers |
| FireCrawl | Retrying after 429 immediately | Honor `Retry-After`; exponential backoff with jitter; idempotency key |
| Resend | Sending from a domain without DKIM/SPF/DMARC | Block phase-4 launch until DNS records verified; check `/email-validation` endpoint |
| Vercel | Putting long jobs in a Vercel function | Vercel route handlers only enqueue to pgmq + return 202; never `await` work |
| Railway | Default 30s SIGTERM grace | Configure `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` higher; handle SIGTERM in Python |
| Pydantic v2 + Postgres | `ignore` mode hides schema drift | `extra='forbid'`; codegen models from `pg_dump --schema-only` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Per-row Realtime broadcasts | Browser memory grows; quota warnings | Batched `run_progress` updates every 2s | ~500-row runs and up |
| pg_trgm canonical match without GIN index | Match queries take seconds, then minutes | `CREATE INDEX … USING gin (normalized_name gin_trgm_ops)` | ~5k businesses in canonical table |
| Aggregator scans all `verifications` for a business | Aggregator latency grows linearly | Partial index on `(business_id, run_id)`; materialized `business_current_state` | ~10 passes per business over time |
| Unbounded queue depth on bad upload | Worker falls hours behind; UI looks frozen | Pre-flight estimate gate; per-run row cap (e.g. 100k); admin must approve over threshold | Single 50k-row upload at 1 QPS = 14 hours |
| Re-aggregating all rows nightly | Reconciliation job takes longer than the night | Aggregate only rows changed since last reconciliation (use updated_at watermark) | ~100k verifications in ledger |
| Synchronous PII scan in upload route handler | Upload UI hangs on big CSVs | PII scan happens in worker after enqueue; upload route just stores file + queues | CSVs > ~10k rows |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Outreach token sent in URL fragment / referer-leakable param | Token leaked via Referer header to scripts on landing page | Tokens in path segments, validated server-side; no third-party scripts on outreach pages |
| Outreach token reuse | Stale clicks accepted weeks later, possibly by wrong party | Single-use: mark `used_at` on first valid POST; subsequent attempts 410 Gone |
| Storing raw API keys in admin UI table | Leak via DB dump or accidental export | Encrypt at rest with KMS or Postgres `pgcrypto` symmetric key from Railway secret; UI shows last-4 only |
| Service-role key accessible to Next.js client | Full RLS bypass from browser | Service-role key in **server-only env vars** (no `NEXT_PUBLIC_` prefix); accessed only in route handlers |
| Eval gold set readable by all admins | Insider can train against the test | `eval_gold` RLS: service-role only; admins access via aggregated metrics, not row reads |
| Audit ledger has UPDATE/DELETE policies | Insider can erase tracks | No UPDATE/DELETE policy at all; trigger raises on UPDATE/DELETE attempts |
| CSV uploads accept arbitrary file types | XLSX with macros, zip bombs, SSRF via formulas | Validate MIME; parse with pandas in safe mode; reject formulas (`=`/`+`/`-`/`@` cell starts); size cap |
| Logging Perplexity prompts with PII intact | PII proliferates to logs / Sentry | Log payload schema + hash, not raw content; null PII fields before logging |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Progress bar that resets on reconnect | User assumes run failed, re-uploads → duplicate cost | Persistent progress in DB; reconnect re-reads state; idempotent uploads |
| "Run failed" with no recovery path | User loses hours of partial work | Surface "Resume Run" button driven by `run_rows.status='pending'` count |
| Cost shown only post-run | Surprise bills | Pre-flight estimate displayed before "Start"; live tally during run |
| Admin review queue with no diff view | Can't tell why 2-of-N matched | Show the source fields side-by-side with which fields matched |
| Email outreach with no opt-out | Spam complaints; DMARC reputation damage | Required unsubscribe link; track `opted_out` per business |
| Random-sample labeling UI shows the AI's answer | Anchoring bias contaminates the gold set | Hide AI verdict until labeler commits their own; then reveal |
| Run-complete email with no link to results | User has to navigate manually | Tokenized direct link to the run detail page |
| Realtime progress that updates faster than the eye | Performance feel but useless | Throttle to 1-2 updates/sec; show ETA, not just count |

## "Looks Done But Isn't" Checklist

- [ ] **Idempotency:** Worker has idempotency keys on API calls AND DB inserts — verify by killing the worker mid-call and confirming no duplicate bill
- [ ] **RLS:** Service-role key only on worker/server; every table has RLS enabled with at least one DENY policy as default — verify by hitting tables with anon key and confirming empty results
- [ ] **Realtime auth:** Each user's channel is private — verify by logging in as User B and trying to subscribe to User A's run channel; expect 401
- [ ] **Schema codegen:** Pydantic models regenerate-clean from current schema — verify with `git diff` after running codegen in CI
- [ ] **Aggregator barrier:** Aggregator waits for all required passes — verify with a concurrent test that runs N passes in parallel and confirms `business_current_state` reflects all N
- [ ] **Cost cap:** Both pre-flight and live tally caps trip — verify by setting a $0.01 cap and running a small batch; expect hard stop
- [ ] **Cap reconciliation:** Provider-truth job runs and writes to `api_keys.provider_truth_cents` — verify daily run logs
- [ ] **Eval gate:** CI fails on regression — verify by intentionally breaking the prompt and confirming CI blocks deploy
- [ ] **Eval gold size:** Gold set count asserted at start of eval run — verify by emptying gold set and confirming eval fails (not passes empty)
- [ ] **Run immutability:** `verifications` rejects UPDATE/DELETE — verify with a direct SQL UPDATE; expect raise
- [ ] **Admin edit flow:** Admin "edit" inserts a new verifications row, not an UPDATE — verify by inspecting DB after admin edits a status
- [ ] **PII allowlist:** Outbound payloads only contain allowlisted fields — verify by inspecting `api_calls.payload_redacted` audit rows
- [ ] **Outreach tokens:** Single-use, hashed at rest, expiring — verify by replaying a used token; expect 410
- [ ] **pgmq drain on SIGTERM:** Railway deploys don't double-process messages — verify by deploying mid-run and checking for duplicate `api_calls` rows
- [ ] **Canonical match audit:** Every merge has a `match_candidate`/`admin_approval` row OR is EIN-based — verify by querying for merges without provenance
- [ ] **Resend DNS:** SPF, DKIM, DMARC all verified — verify in Resend dashboard before phase 4 launch
- [ ] **Compliance signoff:** Jim's written signoff on PII boundary recorded — verify the artifact exists before outreach launch

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Double-billing on retries | MEDIUM | (1) Add idempotency keys to api_calls table + dedup before upstream; (2) request Perplexity/FireCrawl credit on documented duplicates; (3) backfill `verifications` to dedupe |
| Realtime reconnect storm | LOW | Switch to `run_progress` aggregated row immediately; throttle existing emit calls server-side; clients pick up automatically |
| RLS on outreach exploited | HIGH | (1) Disable outreach endpoint immediately; (2) audit `outreach_responses` for non-token-validated rows; (3) invalidate all outstanding tokens; (4) rebuild route handler with server-side validation |
| Schema/Pydantic drift breakage | MEDIUM | (1) Roll worker back to last known-good build; (2) regenerate models from current schema; (3) ship codegen-in-CI gate to prevent recurrence |
| Canonical silent merge corrupted gold set | HIGH | (1) Snapshot `businesses` table; (2) un-merge all non-EIN merges (audit ledger has source IDs); (3) re-route through admin review; (4) re-run eval on cleaned gold set; (5) compare to pre-merge baseline |
| Aggregator phantom read | MEDIUM | (1) Add passes-completed barrier; (2) reconcile by re-aggregating all rows where `verifications.max(created_at) > business_current_state.updated_at` |
| Cost cap drift / overrun | HIGH | (1) Hard-pause all runs; (2) reconcile against provider invoice; (3) update cap-enforcement logic to use response-header costs; (4) negotiate with provider if overrun is large |
| Eval false-pass on empty gold set | MEDIUM | (1) Add `n_examples >= MIN` assertion; (2) re-run eval on all post-regression deploys; (3) roll back any deploy that didn't pass with gold-set assertions in place |
| Run immutability violated | HIGH (audit fail) | (1) Reconstruct change history from PG WAL / backups if available; (2) document gap to IVMF; (3) add triggers; (4) re-affirm audit policy |
| PII leak to external API | HIGH (compliance) | (1) Stop runs; (2) inventory what was sent; (3) disclose to Jim/compliance immediately; (4) request data deletion from Perplexity per their policy; (5) implement allowlist + scan; (6) post-mortem |
| pgmq visibility timeout too short | LOW | Tune timeout; add heartbeat; idempotency catches the damage already done |
| Realtime cross-user leak | HIGH (privacy) | (1) Disable wildcard channels; (2) audit access logs for cross-user subscriptions; (3) re-issue per-user channels; (4) notify affected users if leak confirmed |

## Pitfall-to-Phase Mapping

Project phases (per PROJECT.md milestone v1.1): 0 Foundation · 1 Cache-only · 2 Live verification · 3 Manual workflows · 4 Outreach · 5 Analytics.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Double-billing on retries | Phase 0 (schema) + Phase 2 (logic) | Kill worker mid-call; confirm no duplicate `api_calls` row |
| 2. Realtime reconnect storms | Phase 2 | Run 12k-row batch; confirm <1 Realtime event/sec per channel |
| 3. RLS on anon outreach writes | Phase 4 | Attempt direct insert with anon key; expect denied |
| 4. Schema/Pydantic drift | Phase 0 | CI step: `python -m codegen && git diff --exit-code` |
| 5. Canonical silent merge | Phase 1 | Insert 2 businesses sharing only address+phone; confirm match_candidate created, not auto-merged |
| 6. Aggregator phantom reads | Phase 2 | Run N parallel passes; confirm `business_current_state` reflects all N |
| 7. Cost cap drift | Phase 0 (schema) + Phase 2 (reconciliation) | Daily reconciliation job logs drift; alert if >5% |
| 8. Eval gold set RLS-filtered | Phase 2 | CI logs `n_examples`; assertion fails if below floor |
| 9. Run immutability violated | Phase 0 (triggers) + Phase 3 (admin UI) | `UPDATE verifications` directly via psql; expect raise |
| 10. PII leak | Phase 0 (allowlist) + Phase 4 (compliance gate) | Audit `api_calls.payload` for non-allowlisted fields |
| 11. pgmq visibility timeout | Phase 0 (queue config) + Phase 2 (heartbeat) | Hold a message past timeout; confirm not redelivered |
| 12. Realtime cross-user leak | Phase 0 (RLS scaffolding) + Phase 2 (Realtime ships) | Subscribe to another user's channel; expect 401 |

## Sources

- IVMF Business Checker v1.0 production behavior (`business_checker/`) — known issues documented in PROJECT.md
- Supabase docs on pgmq, Realtime RLS, and service-role usage (Context7-verifiable; HIGH confidence)
- pgmq README on visibility timeouts and message redelivery semantics
- Perplexity Sonar + FireCrawl API behavior under retry storms (observed during BMSG run, 2026-04-30)
- Pydantic v2 schema strictness (`extra='forbid'`) — official Pydantic docs
- Adversarial review captured in PROJECT.md Key Decisions (EIN auto-merge only; 2-of-N → admin queue)
- Enterprise AI Standards (memory: `enterprise_ai_standards_ref.md`) — PII boundary, eval-as-gate, governance prerequisites

---
*Pitfalls research for: IVMF Business Checker v1.1 — Python worker + Next.js + Supabase-only-shared-state*
*Researched: 2026-05-12*
