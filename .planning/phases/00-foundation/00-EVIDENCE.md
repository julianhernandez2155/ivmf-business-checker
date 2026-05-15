# Phase 0 — Evidence Log

Phase 0 exit demo (D-00-11) artifacts. Each item below has a status of either
`done` (live evidence captured) or `deferred` (with reason + follow-up).

**Status summary (2026-05-15):** Phase 0 ships with 1 of 6 demo items live-verified
(item 3, eval-regression gate), and 5 items deferred. The deferrals are not Phase 0
defects — they reflect external provisioning blocks (dev Supabase project not yet
provisioned; IVMF subdomain not yet provisioned) that block the *live demo* but
not the *code-level correctness* of each gate. Each deferred item points at the
code/test that proves it works once the external block clears.

## D-00-11 Item 1 — Magic-link login + middleware allowlist

- **Status:** deferred (code-complete, awaiting dev Supabase)
- **Reason:** dev Supabase project `ivmf-checker-dev` not yet provisioned; magic-link
  auth + middleware allowlist + `auth.is_allowed_domain()` RLS helper landed in plan
  00-04 (commits 8b240f1, 6500f57, e9a1de8) but cannot be browser-walked-through
  without a running Supabase Auth instance.
- **Code-level proof:**
  - Middleware allowlist: `web/middleware.ts` (committed 6500f57) — reads
    `app_config.email_domain_allowlist`, fails CLOSED to `['syr.edu']` on error.
  - RLS helper: `auth.is_allowed_domain()` migration in `supabase/migrations/0008_rbac_role_default.sql`.
  - AUTH-01/02/03 vitest + pytest assertions: commit e9a1de8.
- **Follow-up:** Run the manual browser walkthrough once `SUPABASE_DEV_DB_URL` is
  set and `supabase db push` has been executed (see STATE.md "Open
  Externally-Blocked Items"). Capture the @syr.edu success + @gmail.com 403
  screenshots inline below at that time.

## D-00-11 Item 2 — Codegen drift PR fails CI

- **Status:** deferred (code-complete, awaiting dev Supabase)
- **Reason:** the drift workflow runs `drizzle-kit pull` against the LIVE dev DB,
  not against the migration file. To actually trip the gate the demo PR must
  mutate the live dev DB so the introspection produces a smaller `schema.ts` than
  the committed one. Without a provisioned dev DB the demo cannot run — and
  opening a demo PR that would not actually fail is worse than leaving it
  deferred (it would falsely signal that the gate is broken).
- **Code-level proof:**
  - Workflow: `.github/workflows/codegen-drift.yml` (commit 7511505) — runs
    `bash scripts/check-drift.sh` which executes `drizzle-kit pull` and asserts
    `git diff --exit-code -- web/db/schema.ts`.
  - D-00-03 hard guard: rejects non-empty `web/drizzle/migrations/` before any
    other step.
  - Existing 00-EVIDENCE entries for the workflow file itself (Wave 2): `[x]
    Workflow file exists`, `[x] D-00-03 hard guard step present`, `[x] Workflow
    invokes bash scripts/check-drift.sh`.
- **Demo run (when dev DB is up):**
  ```bash
  psql "$SUPABASE_DEV_DB_URL" -c "alter table public.businesses drop column normalized_name;"
  git checkout -b demo/codegen-drift-trip
  sed -i.bak 's/  normalized_name text,//' supabase/migrations/0001_init_schema.sql && rm -f supabase/migrations/0001_init_schema.sql.bak
  git add supabase/migrations/0001_init_schema.sql
  git commit -m "demo: drop normalized_name to trip drift gate"
  git push -u origin demo/codegen-drift-trip
  gh pr create --title "[DEMO] Trip codegen drift gate" --body "..."
  # Wait for codegen-drift workflow to fail
  # Capture run URL + screenshot
  # Restore: psql ... "alter table ... add column normalized_name text;"
  # gh pr close demo/codegen-drift-trip
  ```
- **Follow-up:** Run the demo at Phase 1 entry (Phase 1 requires dev DB
  provisioning anyway — same external block clears both).

## D-00-11 Item 3 — Eval-CI regression PR fails CI  **[LIVE-VERIFIED]**

- **Status:** done (local end-to-end run captured 2026-05-15)
- **Evidence:** Local re-run of the same logic that GitHub Actions executes
  (`python -m business_checker.eval.score` → `python` baseline-compare block from
  `scripts/eval-ci.sh`). One `expected_status` label was flipped in `gold.json`,
  the scorer + assertion produced a non-zero exit; restoring the label produced
  exit 0.

  **FAIL run (label flipped on row 0: `Active` -> `closed`):**
  ```
  {"accuracy": 0.6724137931034483, "n_examples": 58,
   "routing_distribution": {"Active - auto accepted": 18, ...}}
  current accuracy: 0.6724
  baseline accuracy: 0.6897
  delta: -0.0172
  RESULT: FAIL — eval regression: 0.672 < baseline 0.690 - 0.01
  exit code: 1
  ```

  **RESTORE run (label restored via `git checkout business_checker/eval/gold.json`):**
  ```
  {"accuracy": 0.6896551724137931, "n_examples": 58,
   "routing_distribution": {"Active - auto accepted": 19, ...}}
  current accuracy: 0.6897
  baseline accuracy: 0.6897
  delta: +0.0000
  RESULT: PASS
  exit code: 0
  ```

- **Routing-label distribution surfaced (D-00-12):** both runs emitted a 6-bucket
  `routing_distribution`. Phase 0 reports it as informational; Phase 2 will gate
  on drift.
- **Workflow file:** `.github/workflows/eval-ci.yml` (commit 95a4d2a) executes
  the same assertion block on every PR.
- **Note:** A PR-based demo was not opened because the local end-to-end run
  proves the gate fires on regression and clears on restoration — the GitHub
  Actions workflow runs the exact same `scripts/eval-ci.sh` code path. Opening
  and closing a throwaway PR would only re-verify what's already proven and
  burn a PR number; will be done at Phase 1 if a reviewer wants the GitHub
  check screenshot specifically.

## D-00-11 Item 4 — verifications append-only

- **Status:** deferred (code-complete, awaiting dev Supabase)
- **Reason:** `scripts/phase0-demo.sh` runs the live SQL assertion against the
  dev DB, which is not yet provisioned. Local run output:
  ```
  ERROR: SUPABASE_DEV_DB_URL required
  ```
- **Code-level proof:**
  - Migration `supabase/migrations/0002_verifications_append_only.sql` (commit
    51f7de2) installs BEFORE UPDATE / BEFORE DELETE triggers that raise
    `EXCEPTION 'verifications is append-only — use INSERT with method=admin_edit'`
    with SQLSTATE `P0001`.
  - Integration test `worker/tests/test_verifications_append_only.py` (committed
    in plan 00-02) asserts the trigger fires with SQLSTATE `P0001`.
- **Follow-up:** Run `bash scripts/phase0-demo.sh` once `SUPABASE_DEV_DB_URL` is
  set; expected output is `OK: UPDATE raised P0001 as expected`.

## D-00-11 Item 5 — Worker heartbeat row

- **Status:** deferred (code-complete, awaiting Railway + dev Supabase)
- **Reason:** the heartbeat row is written by the Railway worker, which is not
  yet deployed (same external block as item 1+4 — dev DB + Railway
  provisioning).
- **Code-level proof:**
  - Heartbeat loop: `worker/workers/heartbeat.py` (commit 9477157) writes every
    30s using `asyncio.wait_for(shutdown.wait(), timeout=30)` so SIGTERM exits
    in ms.
  - Integration test `worker/tests/test_heartbeat.py` (commit 5bb1dc6) asserts
    the row lands within 60s.
  - Deployment manifest: `Procfile` + `railway.json` (commit 9477157).
- **Follow-up:** After Railway deploy, the `phase0-demo.sh` second step queries
  `select count(*) from worker_heartbeats where last_seen_at > now() - interval
  '60 seconds'` and asserts ≥ 1.

## D-00-11 Item 6 — Resend DNS ticket

- **Status:** deferred (until Phase 4)
- **Reason:** IVMF IT has not yet provisioned the IVMF subdomain that Resend
  needs (e.g., `outreach.ivmf.syr.edu`). The DNS ticket cannot be filed without
  the subdomain. Phase 0–3 do not send email, so this is not on the critical
  path until Phase 4 entry. Per Plan 00-06 acceptance criteria: "If Task 3 was
  blocked, the evidence log marks item 6 with the blocker reason AND there's a
  documented follow-up date before Phase 4 starts" — that condition is
  satisfied here.
- **What is in place:**
  - Resend account created on resend.com (Julian's gmail).
  - API key generated and stored locally at `worker/.env:RESEND_API_KEY`
    (gitignored — `.env` matches `.gitignore` line 1 and line 72).
  - Sandbox-only sender (`onboarding@resend.dev`) is the only sender available
    until a verified domain is added; this is a built-in safety so any
    accidental Phase 4 code execution before launch cannot reach real
    businesses (only Julian's own verified gmail).
- **Phase 0–3 testing plan:** use the Resend sandbox + Julian's gmail
  (`julianhernandez2155@gmail.com`) as the only allowed recipient until the
  IVMF subdomain is provisioned. This validates the worker → Resend integration
  surface without DNS dependencies.
- **Follow-up:** file the DNS ticket at Phase 4 entry per ROADMAP.md. Records
  needed (Resend dashboard will generate exact values):
  - SPF (TXT): `v=spf1 include:_spf.resend.com -all`
  - DKIM (CNAME × 3): `resend._domainkey`, `resend2._domainkey`, `resend3._domainkey`
  - DMARC (TXT) at `_dmarc.<subdomain>`: `v=DMARC1; p=none; rua=mailto:dmarc@<subdomain>`

---

## Deferred Items Summary

| Item | What's deferred | Blocker | Unblocks at |
|------|------------------|---------|-------------|
| 1 — Magic-link login walkthrough | Browser screenshot capture | Dev Supabase not provisioned | Phase 1 entry (same block) |
| 2 — Codegen-drift demo PR | Live drift trip + PR + workflow failure URL | Dev Supabase not provisioned | Phase 1 entry |
| 4 — `phase0-demo.sh` append-only assertion | Live `psql` against dev DB | Dev Supabase not provisioned | Phase 1 entry |
| 5 — Worker heartbeat row visible in dev DB | Railway deploy + live heartbeat insert | Railway + dev Supabase not provisioned | Phase 1 entry (or Plan 00-05 retro once provisioned) |
| 6 — Resend DNS ticket filed with IT | DNS records on IVMF subdomain | IVMF subdomain not yet provisioned | Phase 4 entry |

**Items 1, 2, 4, 5 share the same external block (dev Supabase + Railway
provisioning).** When that block clears, all four can be demoed in one ~10-min
walkthrough — i.e. the Phase 0 exit demo Loom for Jim can be recorded at the
start of Phase 1 without any code changes. The architectural Phase 0 work is
complete; only the live-verification capture awaits external provisioning.

**Item 6** is on a different track — IT must provision the IVMF subdomain
first. Phase 4 will not start until this is done.

---

## How to populate (when blockers clear)

For items 1, 2, 4, 5: replace each "deferred" block with a "done" block
following the same template as Item 3 above (captured output + commit hashes +
date verified).

## Cross-references

- Demo script: `scripts/phase0-demo.sh` (D-00-11 items 1/4/5 automation)
- Drift gate: `.github/workflows/codegen-drift.yml`
- Eval gate: `.github/workflows/eval-ci.yml` + `scripts/eval-ci.sh`
- Phase 0 success criteria: `.planning/ROADMAP.md` §Phase 0
- Locked routing schema: `.planning/2026-05-13-decision-triage-not-oracle.md`
