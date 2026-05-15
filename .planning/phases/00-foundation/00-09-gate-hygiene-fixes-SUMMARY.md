---
phase: 00-foundation
plan: 09
subsystem: gap-closure (eval-CI gate hygiene + auth open-redirect)
tags: [gap-closure, eval-ci, auth-callback, security, regression-tests]
gap_closure: true
dependency_graph:
  requires:
    - 00-04 (web/app/api/auth/callback/route.ts existed)
    - 00-06 (scripts/eval-ci.sh + baseline.json existed)
  provides:
    - "scripts/eval-ci.sh that enforces baseline comparison unconditionally (GAP-3 closed)"
    - "web/app/api/auth/callback/route.ts with sanitizeNext() helper (GAP-4 closed)"
    - "scripts/tests/eval-ci-dry-run.sh regression test (bash)"
    - "web/tests/auth-callback-sanitize.test.ts regression test (vitest, 14 cases)"
  affects:
    - "ANALYTICS-04 contract: eval-CI gate no longer produces false negatives when PERPLEXITY_API_KEY_EVAL is absent"
    - "AUTH-01 contract: callback no longer enables open-redirect phishing primitive"
tech_stack:
  added: []
  patterns:
    - "Exported helper + regex constant for unit-testable input validation (sanitizeNext / SAFE_NEXT_PATTERN)"
    - "Env-var passing into Python heredocs instead of shell substitution"
key_files:
  created:
    - scripts/tests/eval-ci-dry-run.sh
    - web/tests/auth-callback-sanitize.test.ts
  modified:
    - scripts/eval-ci.sh
    - web/app/api/auth/callback/route.ts
decisions:
  - "Switched the GAP-4 whitelist regex from the plan's `/^\\/(?!\\/)/` to `/^\\/[^/]/`. The lookahead version trivially admits bare `/` because end-of-string satisfies the `not-a-slash` lookahead. The character-class version explicitly requires a non-slash char to exist, which matches the documented invariant (caught live by the vitest case for bare `/`)."
  - "Eval-CI script now uses `python3` everywhere (was `python`). Closes the Phase 0 polish flag from 00-VERIFICATION.md anti-patterns table re macOS local runs."
  - "Heredoc receives paths via env vars (`BASELINE_PATH=... OUT_PATH=...`) instead of shell interpolation — defense against paths containing quotes."
metrics:
  duration_minutes: 4
  completed_date: 2026-05-15
  task_count: 2
  files_created: 2
  files_modified: 2
  commits: 2
  vitest_cases_added: 14
  bash_test_cases_added: 2
---

# Phase 0 Plan 9: Gate Hygiene Fixes Summary

## One-liner

Closes Codex peer-review **GAP-3** (MEDIUM, eval-CI dry-run bypassed baseline) and **GAP-4** (MEDIUM, auth callback open-redirect via unsanitized `next` query param) — the last two gaps from the Phase 0 peer review. Adds bash + vitest regressions that prevent reintroduction.

## What Shipped

### Task 1 — Refactor `scripts/eval-ci.sh` (GAP-3 fix) — commit `fcf5c2c`

**Before:** When `PERPLEXITY_API_KEY_EVAL` was absent (default for fork PRs), the script set `DRY_RUN_FLAG=--dry-run`, ran the offline scorer, printed `dry-run OK`, then `sys.exit(0)` — skipping the baseline comparison entirely. ANALYTICS-04's regression gate was informational, not enforcing.

**After:** The dry-run flag now controls *only* whether the scorer hits the external Perplexity API. The `n_examples >= 20` assertion AND the `accuracy >= baseline - 0.01` comparison run unconditionally. The graceful `WARN: baseline.json not found` path is preserved.

Structural changes:
1. Removed the early-exit branch after the dry-run print; baseline comparison now executes on every run.
2. Replaced bare `python` with `python3` everywhere (works on both GitHub Actions and macOS local).
3. Paths into the inline Python heredoc go through env vars (`BASELINE_PATH`, `OUT_PATH`) instead of shell interpolation, hardening against shell-quoting bugs.
4. Header comment cites GAP-3 + path to VERIFICATION.md for traceability.

### Task 1b — `scripts/tests/eval-ci-dry-run.sh` (GAP-3 regression test) — same commit

A standalone bash test that:
1. Synthesizes a tampered `gold.json` in a `mktemp` dir where every `predicted_status` is flipped to a wrong canonical label (Active↔Likely Closed; others↔Active). Net effect: accuracy collapses well below `baseline − 0.01`.
2. Unsets `PERPLEXITY_API_KEY_EVAL`, runs `EVAL_GOLD=$TAMPERED bash scripts/eval-ci.sh`, asserts non-zero exit.
3. Re-runs with the standard gold.json, asserts zero exit.
4. Trap-cleans `$TMP_DIR` on exit — idempotent across re-runs; never touches the real `gold.json`.

**Live verified:** `unset PERPLEXITY_API_KEY_EVAL; bash scripts/tests/eval-ci-dry-run.sh` exits 0 with both `PASS` lines.

### Task 2 — Sanitize `next` in `web/app/api/auth/callback/route.ts` (GAP-4 fix) — commit `d471049`

**Before:** `url.searchParams.get('next') ?? '/me'` flowed directly into `new URL(next, req.url)`. The WHATWG `URL` constructor uses the first argument *as-is* if it is itself absolute, ignoring the base. A crafted `?next=https://evil.example.com/` redirected off-origin after a valid auth round-trip.

**After:** A `sanitizeNext()` helper is called once on the raw query value. The whitelist regex `SAFE_NEXT_PATTERN = /^\/[^/]/` admits only paths starting with `/` followed by a non-slash character. Anything else (absolute URL, protocol-relative `//host`, `javascript:`, `data:`, bare `/`, null, empty) returns `/me`. Helper + regex are exported so tests can target them directly.

### Task 2b — `web/tests/auth-callback-sanitize.test.ts` (GAP-4 regression test) — same commit

14 vitest cases covering:
- 2 sentinel cases: `null`, `''` → `/me`
- 5 attacker shapes: `https://evil.example.com/path`, `http://evil.example.com/`, `//evil.example.com/path`, `javascript:alert(1)`, `data:text/html,evil` → all `/me`
- 1 edge case: bare `/` → `/me`
- 3 legitimate paths: `/admin`, `/runs/abc-123`, `/me/profile` → preserved unchanged
- 3 regex-direct assertions: `/foo` matches; `//foo` doesn't; `https://x` doesn't

**Live verified:** `pnpm vitest run tests/auth-callback-sanitize.test.ts` → 14/14 pass. Full web/ vitest suite still green at 22/22 (middleware-allowlist + auth-magic-link + this new spec).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Whitelist regex too permissive on bare `/`**
- **Found during:** Task 2, on the first vitest run.
- **Issue:** The plan specified `SAFE_NEXT_PATTERN = /^\/(?!\/)/`, but the negative lookahead trivially succeeds at end-of-string. So `sanitizeNext('/')` returned `'/'`, contradicting the plan's behavior 8 ("bare `/` (no second segment) → `/me`") and the test case the plan dictated.
- **Fix:** Switched to `/^\/[^/]/` — anchor + literal slash + a character class explicitly excluding slash. This requires a second char to exist and to not be a slash, matching the documented invariant. All 14 cases pass under the new regex.
- **Files modified:** `web/app/api/auth/callback/route.ts` (1-line regex change; comment expanded to explain why the lookahead version is wrong)
- **Commit:** `d471049` (part of Task 2 commit, not a separate fix commit)

No other deviations. No checkpoints encountered.

## Verification

| Gate                                                            | Result                                |
| --------------------------------------------------------------- | ------------------------------------- |
| `bash -n scripts/eval-ci.sh`                                    | PASS                                  |
| `bash -n scripts/tests/eval-ci-dry-run.sh`                      | PASS                                  |
| `test -x scripts/tests/eval-ci-dry-run.sh`                      | PASS                                  |
| `! grep -E 'dry-run OK.*sys.exit\(0\)' scripts/eval-ci.sh`      | PASS (broken pattern gone)            |
| `grep -q 'delta = r\["accuracy"\]' scripts/eval-ci.sh`          | PASS (baseline comparison unconditional) |
| `grep -q python3 scripts/eval-ci.sh && ! grep -q '^python ' …`  | PASS                                  |
| `grep -c "GAP-3\|GAP-4" {all 4 files}`                          | 8 references (expect ≥ 4)             |
| `unset PERPLEXITY_API_KEY_EVAL; bash scripts/tests/eval-ci-dry-run.sh` | exit 0 (both sub-cases PASS) |
| `pnpm vitest run tests/auth-callback-sanitize.test.ts`          | 14/14 pass                            |
| `pnpm vitest run` (full web/ suite)                             | 22/22 pass (no regressions)           |

## Closes

- **GAP-3** (MEDIUM) — eval-CI dry-run skips baseline comparison. **Closed.** Regression covered by `scripts/tests/eval-ci-dry-run.sh`.
- **GAP-4** (MEDIUM) — open-redirect in auth callback. **Closed.** Regression covered by `web/tests/auth-callback-sanitize.test.ts`.

With this plan + Plan 00-07 (GAP-1 + GAP-2) + Plan 00-08 (GAP-5), all 5 Codex peer-review gaps are closed.

## Self-Check: PASSED

Verified:
- `scripts/eval-ci.sh` FOUND (modified, contains "GAP-3" and "python3", no broken early-exit)
- `scripts/tests/eval-ci-dry-run.sh` FOUND (executable, contains "GAP-3", live PASS)
- `web/app/api/auth/callback/route.ts` FOUND (contains "sanitizeNext", "SAFE_NEXT_PATTERN", "GAP-4", re-exports both)
- `web/tests/auth-callback-sanitize.test.ts` FOUND (14 `it(` cases, contains "evil.example.com", "GAP-4")
- Commit `fcf5c2c` FOUND in git log (Task 1)
- Commit `d471049` FOUND in git log (Task 2)
- All 22 web vitest cases pass; bash GAP-3 test PASS end-to-end.
