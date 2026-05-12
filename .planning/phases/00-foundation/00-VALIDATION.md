---
phase: 0
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 0 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (worker/) + vitest (web/) + bash demo script |
| **Config file** | worker/pyproject.toml, web/vitest.config.ts (both installed in Wave 0) |
| **Quick run command** | `cd worker && pytest -x -q && cd ../web && pnpm test --run` |
| **Full suite command** | `make test` (runs worker pytest, web vitest, eval-CI, drift-check) |
| **Estimated runtime** | ~60 seconds (quick) / ~180 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command for the touched layer (worker or web)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite + `scripts/phase0-demo.sh` must both be green
- **Max feedback latency:** 60 seconds for quick path

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 0-01-01 | 01 | 1 | CANON-05 | unit | `pytest worker/tests/test_schema.py -x` | ❌ W0 | ⬜ pending |
| 0-01-02 | 01 | 1 | CANON-06 | unit | `pytest worker/tests/test_append_only.py -x` | ❌ W0 | ⬜ pending |
| 0-01-03 | 01 | 1 | CANON-07 | unit | `pytest worker/tests/test_audit_trigger.py -x` | ❌ W0 | ⬜ pending |
| 0-01-04 | 01 | 1 | CANON-08 | integration | `pytest worker/tests/test_pgmq.py -x` | ❌ W0 | ⬜ pending |
| 0-02-01 | 02 | 2 | CANON-03 | ci | `bash scripts/check-drift.sh` | ❌ W0 | ⬜ pending |
| 0-02-02 | 02 | 2 | CANON-03 | ci | `gh workflow view codegen-drift` | n/a | ⬜ pending |
| 0-03-01 | 03 | 3 | AUTH-01 | e2e | `pnpm test web/tests/auth-magic-link.spec.ts` | ❌ W0 | ⬜ pending |
| 0-03-02 | 03 | 3 | AUTH-02 | unit | `pnpm test web/tests/middleware-allowlist.test.ts` | ❌ W0 | ⬜ pending |
| 0-03-03 | 03 | 3 | AUTH-03 | sql | `pytest worker/tests/test_rls_domain_allowlist.py -x` | ❌ W0 | ⬜ pending |
| 0-03-04 | 03 | 3 | AUTH-04 | sql | `pytest worker/tests/test_allowlist_admin.py -x` | ❌ W0 | ⬜ pending |
| 0-04-01 | 04 | 4 | ANALYTICS-04 | unit | `pytest worker/tests/test_heartbeat.py -x` | ❌ W0 | ⬜ pending |
| 0-04-02 | 04 | 4 | ANALYTICS-04 | integration | `pytest worker/tests/test_worker_loop.py -x` | ❌ W0 | ⬜ pending |
| 0-05-01 | 05 | 5 | CANON-03 | ci | `bash scripts/eval-ci.sh` | ❌ W0 | ⬜ pending |
| 0-05-02 | 05 | 5 | (demo) | manual | `bash scripts/phase0-demo.sh` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `worker/pyproject.toml` — add pytest 8.x + pytest-postgresql + psycopg[binary] dev deps
- [ ] `worker/tests/conftest.py` — shared fixtures (db connection, test schema bootstrap)
- [ ] `worker/tests/test_schema.py` — stub asserts tables exist for CANON-05
- [ ] `worker/tests/test_append_only.py` — stub for CANON-06 (UPDATE/DELETE raises, UNIQUE rejects dup)
- [ ] `worker/tests/test_audit_trigger.py` — stub for CANON-07 (audit_log row + jsonb diff)
- [ ] `worker/tests/test_pgmq.py` — stub for CANON-08 (q_verify, q_aggregator exist with vt=300)
- [ ] `worker/tests/test_rls_domain_allowlist.py` — stub for AUTH-03 (RLS blocks non-allowlisted JWT)
- [ ] `worker/tests/test_allowlist_admin.py` — stub for AUTH-04 (admin row edit extends allowlist)
- [ ] `worker/tests/test_heartbeat.py` — stub for ANALYTICS-04 (heartbeat row pattern)
- [ ] `worker/tests/test_worker_loop.py` — stub for worker pgmq long-poll integration
- [ ] `web/vitest.config.ts` — vitest setup
- [ ] `web/tests/middleware-allowlist.test.ts` — stub for AUTH-02 (middleware rejects non-@syr.edu)
- [ ] `web/tests/auth-magic-link.spec.ts` — playwright/vitest stub for AUTH-01 (/me round-trip)
- [ ] `scripts/check-drift.sh` — drizzle-kit pull + datamodel-codegen diff against committed schema
- [ ] `scripts/eval-ci.sh` — run gold-set eval, compare to baseline, fail on regression or n_examples shrink
- [ ] `scripts/phase0-demo.sh` — exercises the 6-item exit demo end-to-end

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Resend DNS ticket filed with IT for IVMF subdomain | (demo item 6) | Org-side ticketing system, not in repo | Filed ticket URL pasted into `.planning/phases/00-foundation/00-EVIDENCE.md` with timestamp |
| Drift-trip PR fails CI in GitHub UI | CANON-03 | Requires opening a real PR | Create branch with intentional schema mismatch, push, screenshot failing check |
| Eval-CI regression PR fails CI in GitHub UI | CANON-03 | Same | Create branch lowering accuracy, push, screenshot failing check |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
