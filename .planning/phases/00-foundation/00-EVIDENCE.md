# Phase 0 — Evidence Log

Manual demo artifacts captured during Phase 0 acceptance. Each item maps to D-00-11
in `00-CONTEXT.md`. The Phase 0 exit demo (Wave 5) attaches the actual screenshots,
Loom timestamps, and ticket IDs against the rows below.

## D-00-11 Item 1 — Magic-link login + middleware allowlist

- [ ] `@syr.edu` login screenshot (or Loom timestamp): _pending Wave 3 (Plan 00-04)_
- [ ] `@gmail.com` 403 screenshot (middleware reject): _pending Wave 3 (Plan 00-04)_
- [ ] RLS reject screenshot (auth.is_allowed_domain() in psql): _pending Wave 3 (Plan 00-04)_

## D-00-11 Item 2 — Codegen drift PR fails CI

- [ ] PR URL (intentional column drop without regen): _pending — open after Wave 2 merges_
- [ ] Screenshot of failing `codegen-drift` GitHub Action check: _pending_
- [ ] Screenshot of `git diff` output produced by `bash scripts/check-drift.sh`: _pending_
- [x] Workflow file exists: `.github/workflows/codegen-drift.yml` (this plan)
- [x] D-00-03 hard guard step present (rejects non-empty `web/drizzle/migrations/`)
- [x] Workflow invokes `bash scripts/check-drift.sh`

## D-00-11 Item 3 — Eval-CI regression PR fails CI

- [ ] PR URL (intentional gold-set label flip): _pending Wave 5 (Plan 00-06)_
- [ ] Screenshot of failing `eval-ci` check: _pending Wave 5 (Plan 00-06)_
- [ ] Routing-label distribution artifact captured in CI run: _pending Wave 5_

## D-00-11 Item 4 — verifications append-only

- [ ] psql output showing `P0001` on `UPDATE verifications`: _captured via `bash scripts/phase0-demo.sh` (Wave 1; re-run for demo)_
- [ ] psql output showing `23505` on duplicate `(run_id, row_index, pass)` INSERT: _Wave 1 — captured during demo run_

## D-00-11 Item 5 — Worker heartbeat row

- [ ] psql query result showing recent heartbeat row: _pending Wave 4 (Plan 00-05)_
- [ ] Railway deploy log showing the worker process started: _pending Wave 4_

## D-00-11 Item 6 — Resend DNS ticket

- [ ] IT ticket ID: _pending Wave 5 (Plan 00-06)_
- [ ] Date filed: _pending Wave 5_
- [ ] Resend dashboard screenshot showing pending verification: _pending Wave 5_

---

## How to populate

After each wave merges, attach the missing artifacts inline (paste screenshot
markdown image links or paste Loom permalinks). When all six items are checked,
the phase-0 exit demo (Loom walkthrough for Jim per `00-CONTEXT.md` §Specifics)
records the full sequence end-to-end.

## Cross-references

- Demo script: `scripts/phase0-demo.sh` (D-00-11 items 1/4/5 automation)
- Drift gate: `.github/workflows/codegen-drift.yml`
- Eval gate: `scripts/eval-ci.sh` (Wave 5 wires into CI)
- Phase 0 success criteria: `.planning/ROADMAP.md` §Phase 0
