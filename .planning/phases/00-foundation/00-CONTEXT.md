# Phase 0: Foundation - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 0 delivers the foundational infrastructure that every later phase composes on top of: a provisioned Supabase project with the v1.1 schema (canonical businesses, append-only verifications ledger, runs, run_rows, review queue, outreach tables stub, api_keys, budget_ledger, audit_log, app_config), RLS policies, append-only triggers, the pgmq queues `q_verify` and `q_aggregator` configured with vt=300s, an authenticated Next.js shell that gates `@syr.edu` users via magic-link in both middleware and RLS, a Railway-deployed Python FastAPI worker scaffold that connects to Postgres and long-polls pgmq (but does NOT yet call Perplexity/FireCrawl), a Drizzle (TS) + datamodel-code-generator (Python) codegen pipeline wired into CI as a drift gate, and the v1.0 eval harness running in CI as a deploy gate.

**Not in Phase 0:** any business logic, any external API calls, any upload UI, any canonical matching, any export, any worker job that does real work. Phase 0 ships infrastructure only.

</domain>

<decisions>
## Implementation Decisions

### Repo & Deploy Layout
- **D-00-01:** Single monorepo with three top-level directories: `web/` (Next.js → Vercel), `worker/` (FastAPI + reuses `business_checker/tools/` as an installable package → Railway), `supabase/` (migrations, RLS, triggers, cron, seed). Vercel and Railway both configured with subdirectory build roots. **Why:** schema changes touch all three at once; one PR keeps them atomic. **For planner:** the `business_checker/` directory at repo root stays as the Python verification engine and is imported by `worker/` via editable install (`pip install -e ../business_checker`). The Tkinter GUI files (`business_checker_gui.py`, `business_checker_app.py`, `run_checker.py`) stay frozen at v1.0 and are not maintained but are not deleted either.

### Local Dev Experience
- **D-00-02:** Cloud-only development against a dedicated `ivmf-checker-dev` Supabase project. Production is a separate project. No `supabase start` / Docker requirement. **Why:** Julian builds from a laptop between class/work; Docker friction is not worth the offline-first guarantee. Cloud dev gives same Realtime/pgmq/cron behavior as prod for free on the free tier. **For planner:** `.env.local` for `web/` points to dev project anon+service keys; `.env` for `worker/` points to dev project Postgres URL. Both committed as `.env.example` with key names only. Production keys live in Vercel + Railway env settings.

### Migration Tooling
- **D-00-03:** Supabase CLI is the single source of truth for schema, RLS, triggers, functions, and cron. Migrations live in `supabase/migrations/*.sql` and are hand-written or exported from the Supabase dashboard. Drizzle is **introspect-only** — it generates TS types from the live database via `drizzle-kit pull`. datamodel-code-generator does the same for Python via live DB introspection. **Drizzle migration generation (`drizzle-kit generate`) is forbidden.** **Why:** two migration tools = inevitable drift; the research already pinned RLS/triggers/cron to Supabase CLI; making Drizzle introspect-only removes the conflict surface entirely. **For planner:** add a CI guard that fails if anything under `drizzle/migrations/` exists.

### Auth UX (Phase 0 scope)
- **D-00-04:** Magic-link only in Phase 0. No password sign-up flow, no password reset flow, no password field on the sign-in page. AUTH-01 is satisfied via the "or" clause. **Why:** smallest Phase 0 surface; magic-link covers @syr.edu staff who already have university email. Password option can be added in a future minor phase if Jim or IVMF staff push back on email friction. **For planner:** sign-in page has one input (email) and one button (send magic link). Server validates `@syr.edu` (or whatever the `app_config.email_domain_allowlist` row says) BEFORE invoking `supabase.auth.signInWithOtp()`.

### Domain Allowlist Mechanism
- **D-00-05:** `app_config` table with rows like `(key='email_domain_allowlist', value='["syr.edu"]'::jsonb)`. Next.js middleware reads this on every request (with edge caching, 60s TTL). A Postgres RLS function `auth.is_allowed_domain(email text) returns boolean` reads the same row and is referenced by the policy on `auth.users`. Admin can extend the allowlist by editing the config row from the admin UI — no code change required (AUTH-02). **Why:** AUTH-02 explicitly says "via a config row." This is the standard pattern. **For planner:** the middleware AND RLS layers MUST both enforce; reading only one is a known-bypass shape.

### Audit Log Shape
- **D-00-06:** A single `audit_log` table with columns `(id, actor_user_id, action, table_name, row_pk, before jsonb, after jsonb, diff jsonb, created_at, request_id)`. Generic `audit_log_trigger()` function uses `TG_TABLE_NAME`, `TG_OP`, `OLD`, `NEW` to populate. Attached to every admin-writable table (initially: `app_config`, `api_keys`, `budget_ledger`, and a stub for `outreach_tickets`). **Why:** AUTH-04 requires before/after diff for every admin write action; one trigger function reused across tables minimizes drift. **For planner:** `diff` column is computed in the trigger using `jsonb_object_agg` of changed keys to avoid downstream parsing.

### Append-Only Triggers on `verifications`
- **D-00-07:** `BEFORE UPDATE` and `BEFORE DELETE` triggers on `verifications` raise `EXCEPTION 'verifications is append-only — use INSERT with method=admin_edit'`. **Why:** CANON-06 requires Postgres-enforced immutability; an RLS policy alone is bypassable by service-role. Trigger is unconditional. **For planner:** verify with an integration test that attempts an UPDATE and asserts the SQLSTATE.

### Idempotency UNIQUE Keys
- **D-00-08:** `verifications` has `UNIQUE (run_id, row_index, pass)` and a second table `api_calls` has `UNIQUE (provider, request_hash)` for outbound API dedup. Both columns are NOT NULL on insert. **Why:** CANON-07 + research Pitfall P1 (double-billing). The api_calls table is created in Phase 0 even though no calls happen until Phase 2 — the schema gate must be green.

### pgmq Configuration
- **D-00-09:** Two queues created via `pgmq.create('q_verify')` and `pgmq.create('q_aggregator')`, both with default vt=300s configured at the consumer (worker) call site, NOT at create time (pgmq vt is per-read in tembo-pgmq-python 0.10). Worker uses `read_with_poll(queue, vt=300, qty=1, max_poll_seconds=20)`. **Why:** research §pgmq + roadmap §Phase 0 success criterion 6.

### Upload-Parse Column Allowlist
- **D-00-10:** A `app_config` row stores the allowed source-column header set (initially the BMSG/MWBE public-registry headers). Phase 0 stubs the upload endpoint with a parse function that rejects files whose headers fall outside the allowlist with a clear error. Actual upload UI ships in Phase 1; the parse function is unit-tested in Phase 0 against the two reference Run input files. **Why:** PII defense-in-depth without making compliance a phase gate (PROJECT.md key decisions); research Pitfall P10.

### Phase 0 "Done" Demo (Exit Criteria)
- **D-00-11:** Phase 0 is shipped when ALL of the following are demonstrable in one ~10-minute walkthrough:
  1. A `@syr.edu` magic-link login round-trip lands the user on a `/me` page showing their email and role; a `@gmail.com` login attempt is blocked at the middleware with a clear message.
  2. A PR that intentionally drops or renames a column in a `supabase/migrations/*.sql` file without regenerating Drizzle types and Pydantic models fails the GitHub Actions check with a non-zero diff from `drizzle-kit pull` or `datamodel-codegen`.
  3. A PR that introduces an intentional accuracy regression to the v1.0 eval gold set (e.g., flipping an expected label) fails the eval-CI step.
  4. A test attempting `UPDATE verifications SET status='active' WHERE id=...` raises the append-only exception; a duplicate `INSERT` with the same `(run_id, row_index, pass)` raises a unique-violation.
  5. The worker is running on Railway, has long-polled `q_verify` for at least one cycle, and shows a heartbeat row in a `worker_heartbeats` table.
  6. The Resend DNS ticket for the IVMF subdomain is filed with IT and referenced by ticket ID in STATE.md.

  **Why:** without a concrete demo, Phase 0 can "look done" while quietly broken on the gates that protect every later phase. The drift-trip PR and the immutability assertion are the two highest-leverage checks.

### Claude's Discretion
The planner has discretion on:
- Exact Postgres column types (use Drizzle/datamodel-code-generator defaults; document any deviations).
- Folder layout inside `web/`, `worker/`, and `supabase/` (follow Next.js App Router conventions; FastAPI dispatcher/heartbeat module layout per research §ARCHITECTURE).
- CI provider — pick GitHub Actions unless a stronger reason emerges; it has the lowest config burden and Vercel + Railway both have first-party GitHub integration.
- Whether the heartbeat watchdog runs as pg_cron or as a worker self-loop in Phase 0 (research suggests pg_cron; either is acceptable as long as it produces a row that the Phase 0 demo can read).
- Test framework choices (pytest for worker, vitest for web are the standard picks).
- Specific shape of the `/me` page beyond "shows email and role" — minimal styling acceptable; Phase 0 is not a UI phase.

### Folded Todos
None — no todos from `gsd-tools todo` matched Phase 0 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & Milestone Context
- `.planning/PROJECT.md` — Project identity, milestone v1.1 goal, key decisions table (rows 1–12)
- `.planning/REQUIREMENTS.md` — All 50 v1.1 requirements; Phase 0 IDs: AUTH-01..04, CANON-03, CANON-05, CANON-06, CANON-07, CANON-08, ANALYTICS-04
- `.planning/ROADMAP.md` — Phase 0 section: goal, dependencies, success criteria, requirements
- `.planning/STATE.md` — Current position, accumulated context, Phase 0 preconditions, externally-blocked items

### Architecture & Stack Research
- `.planning/research/SUMMARY.md` — Executive summary; build order with phase gates; top 8 pitfalls
- `.planning/research/STACK.md` — Locked versions for Next.js 16.2 / React 19 / Drizzle 0.45 / FastAPI 0.136 / psycopg 3.3 / tembo-pgmq-python 0.10 / datamodel-code-generator 0.57; rejected tools list
- `.planning/research/ARCHITECTURE.md` — Topology diagram, worker module layout, table inventory, RLS policy shape
- `.planning/research/FEATURES.md` — Feature table-stakes grouped by domain
- `.planning/research/PITFALLS.md` — Specifically: P1 (double-billing), P4 (schema drift), P7 (cap schema), P10 (PII allowlist), P11 (pgmq vt), P12 (Realtime RLS)

### v1.0 Code (preserved, do not modify in Phase 0)
- `business_checker/tools/check_business.py` — Perplexity Sonar call (Phase 2 will import; Phase 0 only verifies importability)
- `business_checker/tools/scrape_website.py` — FireCrawl fallback (Phase 2 import target)
- `business_checker/tools/columns.py` + `business_checker/tools/build_output.py` — XLSX export shape (Phase 1 import target; Phase 0 verifies the package installs)
- `business_checker/eval/` — Gold set + scoring scripts (Phase 0 wires into CI)
- `business_checker/CLAUDE.md` — WAT-framework operating notes for the verification engine

### External Docs Worth Reading
- Supabase Auth (magic-link, OTP, `app_metadata` for RBAC), Supabase Queues GA / pgmq, Supabase RLS, Supabase CLI migrations
- `tembo-pgmq-python` 0.10 release notes — `read_with_poll`, `set_vt`
- `datamodel-code-generator` 0.57 — Postgres input mode, `extra=forbid` flag
- Drizzle 0.45 — `drizzle-kit pull` (introspection)
- Vercel App Router subdirectory deploys; Railway monorepo subdirectory deploys

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `business_checker/tools/check_business.py` — pure function `check_business(api_key, name, website, city, state) -> dict`. Phase 0 verifies it can be imported from the Railway worker via editable install. Phase 2 actually calls it.
- `business_checker/tools/columns.py` + `build_output.py` — XLSX assembly with v1.0-compatible column shape. Phase 1 import target; Phase 0 verifies install.
- `business_checker/eval/` — gold set + `score.py` + `sample.py`. Phase 0 CI step runs `python -m business_checker.eval.score` against the gold set and exits non-zero on regression.
- `business_checker/tools/judge.py` + `business_checker/tools/confidence_score.py` — exist and are exported; not in Phase 0 scope but should remain importable.

### Established Patterns
- WAT framework: tools/ contains deterministic Python; workflows/ contains markdown SOPs; agents/Claude coordinate. The new worker on Railway is a `tools/` consumer + workflow re-implementation in async Python — same separation of concerns.
- `.env` for secrets, `.env.example` committed as template — extend this convention to `web/.env.example` and `worker/.env.example`.
- pytest in `business_checker/tests/` is already wired up; mirror in `worker/tests/`.

### Integration Points
- `business_checker/tools/` becomes an installable package (`business_checker` namespace) imported by the Railway worker via `pip install -e ../business_checker`. Requires a minimal `pyproject.toml` at `business_checker/` (already present per repo listing).
- The Vercel `web/` deploy reads from the dev Supabase project; the Railway `worker/` reads from the same project's Postgres connection string; both share `app_config` rows.
- The eval CI step on GitHub Actions runs in the same job that builds the worker image — no separate workflow.

### Constraints from Existing Architecture
- Tkinter GUI files at `business_checker/business_checker_gui.py` and `business_checker_app.py` are frozen v1.0; the planner must NOT delete or refactor them in Phase 0 (PROJECT.md key decision).
- `business_checker/Runs/` contains the two reference run folders (BMSG, Alabama VOB) used as Phase 6 regression baselines — must not be touched.
- `business_checker/cache/` (SQLite v1.0 cache) is being replaced by the canonical DB; Phase 0 leaves the directory in place but the new worker does not read from it.

</code_context>

<specifics>
## Specific Ideas

- The Phase 0 demo walkthrough (D-00-11) is the acceptance artifact. Record a 10-minute Loom for Jim once Phase 0 ships — establishes the "this is built correctly" narrative early.
- The drift-trip PR (D-00-11 item 2) is the single highest-leverage Phase 0 check. Without it, every later phase risks shipping with stale models. Land it before any business logic ships.
- Worker heartbeat row (D-00-11 item 5) doubles as the basis for the heartbeat watchdog that Phase 2 needs for resumability. Build it once, reuse.

</specifics>

<deferred>
## Deferred Ideas

- **Password authentication UX** — Phase 0 ships magic-link only. Revisit in a v1.2 minor phase if IVMF staff feedback requires.
- **CI on Railway or Vercel instead of GitHub Actions** — Defer unless GitHub Actions cost or speed becomes a real problem. GitHub Actions is free for this scale.
- **Supabase local (Docker) dev environment** — Defer indefinitely; cloud-only dev project is the current decision.
- **Multi-environment promotion flow (dev → staging → prod)** — Phase 0 ships dev + prod only. Staging can be added in a later milestone if release cadence demands.
- **Audit log retention/archival policy** — Not a Phase 0 concern; revisit when audit_log table size becomes a real signal (likely v1.2+).
- **Outreach token HMAC implementation** — Phase 4 scope; Phase 0 leaves `outreach_tickets` and `form_responses` as stub tables only.

</deferred>

---

*Phase: 00-foundation*
*Context gathered: 2026-05-12*
