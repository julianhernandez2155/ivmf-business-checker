---
phase: 00-foundation
plan: 09
type: execute
wave: 7
depends_on: [04, 06, 07, 08]
files_modified:
  - scripts/eval-ci.sh
  - web/app/api/auth/callback/route.ts
  - web/tests/auth-callback-sanitize.test.ts
  - scripts/tests/eval-ci-dry-run.sh
autonomous: true
gap_closure: true
requirements:
  - AUTH-01
  - ANALYTICS-04
must_haves:
  truths:
    - "scripts/eval-ci.sh in dry-run mode (no PERPLEXITY_API_KEY_EVAL) still loads baseline.json and compares accuracy; tampered gold.json with regressed accuracy makes the script exit non-zero"
    - "Only the external-API path within eval-ci.sh requires PERPLEXITY_API_KEY_EVAL; the regression comparison runs unconditionally"
    - "web/app/api/auth/callback/route.ts rejects absolute `next` values (URLs starting with http://, https://, //, or anything other than '/' followed by a non-slash) and falls back to /me"
    - "web/app/api/auth/callback/route.ts continues to honor relative `next` values like '/admin' and '/runs/<id>'"
    - "A vitest case proves callback with `next=https://evil.com/` redirects to /me, not evil.com"
    - "A bash test proves eval-ci.sh exits non-zero on regressed gold without PERPLEXITY_API_KEY_EVAL set"
  artifacts:
    - path: scripts/eval-ci.sh
      provides: "GAP-3 fix: dry-run mode still compares against baseline.json"
      contains: "baseline"
    - path: web/app/api/auth/callback/route.ts
      provides: "GAP-4 fix: sanitize `next` to relative-only paths"
      contains: "sanitizeNext"
    - path: web/tests/auth-callback-sanitize.test.ts
      provides: "GAP-4 regression test"
      contains: "evil"
    - path: scripts/tests/eval-ci-dry-run.sh
      provides: "GAP-3 regression test (bash)"
      contains: "PERPLEXITY_API_KEY_EVAL"
  key_links:
    - from: "scripts/eval-ci.sh dry-run branch"
      to: "business_checker/eval/baseline.json"
      via: "always load and compare"
      pattern: "baseline"
    - from: "web/app/api/auth/callback/route.ts"
      to: "sanitizeNext() helper"
      via: "rejects http://, https://, // patterns"
      pattern: "sanitizeNext"
---

<objective>
Close Codex peer review GAP-3 (MEDIUM) and GAP-4 (MEDIUM) — gate-hygiene bugs that produce false-negative CI passes and a low-severity phishing primitive.

GAP-3: `scripts/eval-ci.sh:24` exits 0 in dry-run mode (when `PERPLEXITY_API_KEY_EVAL` is absent — the default for fork PRs and any push without explicit env setup) WITHOUT loading baseline.json or comparing accuracy. The GitHub workflow gate is effectively informational rather than enforcing — exactly the failure mode ANALYTICS-04 is supposed to prevent. A PR that regresses the scorer in any way passes CI as long as the secret happens to be absent.

GAP-4: `web/app/api/auth/callback/route.ts:21` consumes the `next` query parameter unsanitized into `new URL(next, req.url)`. If `next` is an absolute URL (`next=https://evil.example.com/`), the URL constructor uses the absolute URL and ignores the base, redirecting offsite after a valid auth round-trip. Classic open-redirect — low-severity but trivial to fix.

Purpose: Make the eval-CI gate actually enforce on every PR (not just on PRs with the Perplexity secret). Patch the open-redirect with a minimal regex guard and a vitest regression. These are the smallest of the 5 gaps but both have non-zero security/correctness impact.

Output: Refactored eval-ci.sh, sanitized callback route, one new vitest file, one new bash test. No new dependencies. No schema changes. Both fixes touch existing files; no codegen baseline impact.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-VERIFICATION.md
@scripts/eval-ci.sh
@web/app/api/auth/callback/route.ts
@business_checker/eval/baseline.json

<interfaces>
<!-- Current eval-ci.sh structure (the file under test) -->

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ -z "${PERPLEXITY_API_KEY_EVAL:-}" ]; then
  echo "WARN: PERPLEXITY_API_KEY_EVAL unset; running in --dry-run mode" >&2
  DRY_RUN_FLAG="--dry-run"
else
  DRY_RUN_FLAG=""
fi

GOLD="${EVAL_GOLD:-business_checker/eval/gold.json}"
OUT="eval_result.json"
BASELINE="${EVAL_BASELINE:-business_checker/eval/baseline.json}"

python -m business_checker.eval.score --gold "$GOLD" --out "$OUT" $DRY_RUN_FLAG

python - <<PY
import json, sys
r = json.load(open("$OUT"))
n = r.get("n_examples", 0)
assert n >= 20, ...
if "$DRY_RUN_FLAG" == "--dry-run":
    print(f"dry-run OK: n_examples={n}")
    sys.exit(0)                            # ⬅ BROKEN: bypasses baseline comparison
try:
    b = json.load(open("$BASELINE"))
except FileNotFoundError:
    ...
delta = r["accuracy"] - b["accuracy"]
assert delta >= -0.01, ...
PY
```

<!-- Current callback route shape (the file under test) -->

```typescript
export async function GET(req: NextRequest): Promise<NextResponse> {
  const url = new URL(req.url)
  const code = url.searchParams.get('code')
  const next = url.searchParams.get('next') ?? '/me'      // ⬅ UNSANITIZED
  // ...
  const res = NextResponse.redirect(new URL(next, req.url))   // ⬅ absolute URLs win
  // ...
}
```

<!-- Vitest config (Plan 00-04 standard) -->
Tests live in web/tests/*.test.ts. Run via `pnpm test` or `vitest`.
Existing tests use NextRequest from `next/server` and assert response.headers.get('location').

<!-- baseline.json shape (frozen Phase 0) -->
```json
{ "accuracy": 0.6897, "n_examples": 58, "routing_distribution": {...} }
```

<!-- scorer dry-run contract (verify with --help) -->
`python -m business_checker.eval.score --gold <path> --out <path> [--dry-run]`
In --dry-run mode, the scorer reads gold.json, scores offline (no API calls), and writes
eval_result.json with n_examples + accuracy + routing_distribution. Verify by inspection
before refactoring eval-ci.sh.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Refactor scripts/eval-ci.sh so dry-run still compares against baseline</name>
  <files>scripts/eval-ci.sh, scripts/tests/eval-ci-dry-run.sh</files>
  <read_first>
    - scripts/eval-ci.sh (full current state — the dry-run branch on line 24 is what's broken)
    - business_checker/eval/baseline.json (the frozen baseline — confirm shape: accuracy float + n_examples int)
    - .planning/phases/00-foundation/00-VERIFICATION.md §GAP-3 (Fix paragraph + Test specification)
    - .planning/phases/00-foundation/00-06-eval-ci-demo-SUMMARY.md (the eval-CI plan summary — confirm the script is invoked from .github/workflows/eval-ci.yml exactly as `bash scripts/eval-ci.sh`, so the new behavior must remain workflow-compatible)
    - business_checker/eval/score.py (confirm --dry-run produces an eval_result.json with accuracy + n_examples — same shape as live mode)
  </read_first>
  <behavior>
    - Behavior 1: With `PERPLEXITY_API_KEY_EVAL` UNSET and `EVAL_GOLD` pointing at a tampered gold.json that scores 0.5000 (regression > 0.01 below baseline 0.6897): script exits non-zero with a message mentioning "regression" and the delta.
    - Behavior 2: With `PERPLEXITY_API_KEY_EVAL` UNSET and the standard gold.json (scores 0.6897, exact baseline): script exits 0 with `OK: accuracy=0.690 (baseline 0.690, delta +0.000, ...)`.
    - Behavior 3: With `PERPLEXITY_API_KEY_EVAL` SET: script still runs the live scorer path AND still compares against baseline (existing behavior preserved).
    - Behavior 4: With `PERPLEXITY_API_KEY_EVAL` UNSET and no baseline.json (delete file): script exits 0 with the "WARN: baseline.json not found" path (preserves existing graceful behavior on first run).
    - Behavior 5: n_examples < 20 assertion (Pitfall P8 defense) still fires in BOTH modes.
  </behavior>
  <action>
    **A. Refactor scripts/eval-ci.sh** to separate "should we call Perplexity" from "should we compare to baseline." The dry-run flag controls only the former.

    Replace the entire file with:

    ```bash
    #!/usr/bin/env bash
    # GAP-3 fix (.planning/phases/00-foundation/00-VERIFICATION.md):
    # Dry-run mode (no PERPLEXITY_API_KEY_EVAL) still asserts n_examples >= 20 AND
    # still compares accuracy against baseline.json. Only the external-API call
    # path is skipped when the secret is absent.
    #
    # Consumed by .github/workflows/eval-ci.yml.
    set -euo pipefail

    if [ -z "${PERPLEXITY_API_KEY_EVAL:-}" ]; then
      echo "INFO: PERPLEXITY_API_KEY_EVAL unset; running offline scorer (--dry-run)" >&2
      DRY_RUN_FLAG="--dry-run"
    else
      DRY_RUN_FLAG=""
    fi

    GOLD="${EVAL_GOLD:-business_checker/eval/gold.json}"
    OUT="eval_result.json"
    BASELINE="${EVAL_BASELINE:-business_checker/eval/baseline.json}"

    python3 -m business_checker.eval.score --gold "$GOLD" --out "$OUT" $DRY_RUN_FLAG

    BASELINE_PATH="$BASELINE" OUT_PATH="$OUT" python3 - <<'PY'
    import json, os, sys
    out_path = os.environ["OUT_PATH"]
    baseline_path = os.environ["BASELINE_PATH"]

    r = json.load(open(out_path))
    n = r.get("n_examples", 0)
    if n < 20:
        print(f"FAIL: gold set too small: {n} < 20 (Pitfall P8 defense)", file=sys.stderr)
        sys.exit(1)

    try:
        b = json.load(open(baseline_path))
    except FileNotFoundError:
        print(f"WARN: {baseline_path} not found; recording current run as baseline candidate")
        sys.exit(0)

    delta = r["accuracy"] - b["accuracy"]
    if delta < -0.01:
        print(
            f"FAIL: eval regression: {r['accuracy']:.4f} < baseline {b['accuracy']:.4f} - 0.01 "
            f"(delta {delta:+.4f}, n={n})",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"OK: accuracy={r['accuracy']:.4f} (baseline {b['accuracy']:.4f}, delta {delta:+.4f}, n={n})")
    PY
    ```

    Three structural changes vs the original:
    1. The dry-run early-exit branch is GONE. n_examples assertion + baseline comparison run unconditionally.
    2. `python` → `python3` (closes a Phase 0 polish flag from VERIFICATION.md anti-patterns table — works in GitHub Actions AND on macOS local).
    3. Variables passed into the inline Python heredoc via env vars (`BASELINE_PATH=... OUT_PATH=...`) instead of shell substitution. This prevents shell escaping issues in the heredoc and is the recommended pattern (the original `json.load(open("$OUT"))` works but is brittle if paths contain quotes).

    **B. Create scripts/tests/eval-ci-dry-run.sh** — a bash test that proves the fix works.

    First, ensure parent dir exists: `mkdir -p scripts/tests`. (Use Bash to verify the parent exists before writing.)

    Then create the test:

    ```bash
    #!/usr/bin/env bash
    # GAP-3 regression test: eval-ci.sh dry-run path must still compare against baseline.
    #
    # Strategy: create a tampered gold.json that the offline scorer will rate at ~0.5
    # accuracy (well below the 0.6897 baseline minus 0.01 tolerance), then unset
    # PERPLEXITY_API_KEY_EVAL and confirm scripts/eval-ci.sh exits non-zero.
    #
    # Two cases:
    #   1. Tampered gold + no secret + standard baseline → MUST exit non-zero
    #   2. Standard gold + no secret + standard baseline → MUST exit zero
    set -uo pipefail

    REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
    cd "$REPO_ROOT"

    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT

    GOLD_REAL="business_checker/eval/gold.json"
    GOLD_TAMPERED="$TMP_DIR/gold-tampered.json"

    # Tamper: flip every gold record's expected verdict to a wrong value so accuracy
    # collapses. Uses python so the test does not require jq.
    python3 - <<PY
    import json, pathlib
    src = json.load(open("$GOLD_REAL"))
    # Flip every expected verdict to its opposite (works whether gold is list or dict-of-records).
    def flip(v):
        return "closed" if v == "active" else "active"
    if isinstance(src, list):
        for r in src:
            if isinstance(r, dict) and "expected" in r:
                exp = r["expected"]
                if isinstance(exp, dict) and "verdict" in exp:
                    exp["verdict"] = flip(exp["verdict"])
                elif isinstance(exp, str):
                    r["expected"] = flip(exp)
    pathlib.Path("$GOLD_TAMPERED").write_text(json.dumps(src))
    PY

    # Case 1: tampered gold must FAIL even with no secret
    unset PERPLEXITY_API_KEY_EVAL
    if EVAL_GOLD="$GOLD_TAMPERED" bash scripts/eval-ci.sh > "$TMP_DIR/out-tampered.txt" 2>&1; then
      echo "FAIL: tampered gold did not regress; eval-ci.sh exited 0 in dry-run mode"
      cat "$TMP_DIR/out-tampered.txt"
      exit 1
    else
      echo "PASS: tampered gold correctly failed eval-ci.sh in dry-run mode"
    fi

    # Case 2: standard gold should still PASS without the secret
    unset PERPLEXITY_API_KEY_EVAL
    if EVAL_GOLD="$GOLD_REAL" bash scripts/eval-ci.sh > "$TMP_DIR/out-standard.txt" 2>&1; then
      echo "PASS: standard gold succeeded eval-ci.sh in dry-run mode"
    else
      echo "FAIL: standard gold should pass dry-run; instead got:"
      cat "$TMP_DIR/out-standard.txt"
      exit 1
    fi

    echo "GAP-3 regression test PASS"
    ```

    Make it executable: `chmod +x scripts/tests/eval-ci-dry-run.sh`.

    Implements GAP-3 fix + regression coverage per .planning/phases/00-foundation/00-VERIFICATION.md.
  </action>
  <verify>
    <automated>bash -n scripts/eval-ci.sh && bash -n scripts/tests/eval-ci-dry-run.sh && test -x scripts/tests/eval-ci-dry-run.sh && grep -c "DRY_RUN_FLAG.*--dry-run" scripts/eval-ci.sh</automated>
  </verify>
  <acceptance_criteria>
    - `bash -n scripts/eval-ci.sh` exits 0 (valid bash syntax)
    - `bash -n scripts/tests/eval-ci-dry-run.sh` exits 0
    - `test -x scripts/tests/eval-ci-dry-run.sh` succeeds
    - The early-exit `sys.exit(0)` after dry-run print is GONE: `! grep -E 'dry-run OK.*sys.exit' scripts/eval-ci.sh` (must NOT match — this was the broken pattern)
    - The baseline comparison block runs unconditionally: `grep -q "delta = r..accuracy.. - b..accuracy.." scripts/eval-ci.sh` matches
    - `grep -q "python3" scripts/eval-ci.sh` matches (no bare `python`); `grep -c "^python " scripts/eval-ci.sh` returns 0
    - `grep -q "GAP-3" scripts/eval-ci.sh` matches (traceability comment in header)
    - `grep -q "GAP-3" scripts/tests/eval-ci-dry-run.sh` matches
    - When the live scorer is runnable locally: `unset PERPLEXITY_API_KEY_EVAL; bash scripts/tests/eval-ci-dry-run.sh` exits 0 (both sub-cases pass). [Acceptable to defer this live run if pytest is unavailable; the bash -n + grep gates above prove structural correctness.]
  </acceptance_criteria>
  <done>scripts/eval-ci.sh refactored so dry-run still compares baseline; python3 used throughout; new bash regression test exists and is executable; both files reference GAP-3.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Sanitize the `next` parameter in web/app/api/auth/callback/route.ts + add vitest regression</name>
  <files>web/app/api/auth/callback/route.ts, web/tests/auth-callback-sanitize.test.ts</files>
  <read_first>
    - web/app/api/auth/callback/route.ts (current 42-line implementation — line 15 is the unsanitized read, line 21 is the redirect)
    - web/tests/auth-magic-link.spec.ts (existing vitest spec — confirm import patterns and NextRequest construction style)
    - web/tests/middleware-allowlist.test.ts (another existing vitest file in the same dir — match the import + describe/it idiom)
    - .planning/phases/00-foundation/00-VERIFICATION.md §GAP-4 (Fix paragraph: "Reject any `next` that doesn't start with `/` followed by a non-slash character. Whitelist regex: `/^\/(?!\/)/`. On rejection, redirect to `/me` instead.")
  </read_first>
  <behavior>
    - Behavior 1: GET callback with `?code=valid&next=https://evil.example.com/` → response.headers.get('location') ends with `/me` (NOT evil.example.com).
    - Behavior 2: GET callback with `?code=valid&next=//evil.example.com/path` → response.headers.get('location') ends with `/me` (protocol-relative URLs are also absolute; URL constructor would otherwise resolve to evil.example.com).
    - Behavior 3: GET callback with `?code=valid&next=/admin` → location ends with `/admin` (legitimate relative path preserved).
    - Behavior 4: GET callback with `?code=valid&next=/runs/abc-123` → location ends with `/runs/abc-123`.
    - Behavior 5: GET callback with `?code=valid` (no `next`) → location ends with `/me` (default path unchanged).
    - Behavior 6: GET callback with `?code=valid&next=` (empty) → location ends with `/me`.
    - Behavior 7: GET callback with `?code=valid&next=javascript:alert(1)` → location ends with `/me` (the regex rejects anything not starting with `/`).
    - Behavior 8: GET callback with no `code` query param → location ends with `/sign-in?error=missing_code` (existing behavior preserved).
  </behavior>
  <action>
    **A. Patch web/app/api/auth/callback/route.ts** to introduce a `sanitizeNext` helper and use its return value in the redirect URL construction.

    Replace the entire file with:

    ```typescript
    // Phase 00 Plan 04 — AUTH-01 magic-link callback.
    // GAP-4 fix (.planning/phases/00-foundation/00-VERIFICATION.md): the `next`
    // query param is now sanitized via sanitizeNext() so absolute URLs cannot
    // hijack the post-auth redirect. Whitelist: must start with '/' followed by
    // a non-slash character (rejects '//evil', 'https://evil', 'javascript:', '').
    /**
     * Exchanges the magic-link `?code=` for a Supabase session, then redirects to
     * the original (sanitized) `next` path or /me by default.
     *
     * Cookies set by `exchangeCodeForSession` are routed through the response
     * object so the browser receives them with the redirect.
     */
    import { NextRequest, NextResponse } from 'next/server'
    import { createServerClient } from '@supabase/ssr'

    const SAFE_NEXT_PATTERN = /^\/(?!\/)/  // GAP-4: '/foo' OK; '//evil' '/' alone or 'https://evil' rejected

    function sanitizeNext(raw: string | null): string {
      if (!raw) return '/me'
      // Reject anything that doesn't start with '/' followed by a non-slash char.
      // This rules out absolute URLs (http://, https://), protocol-relative (//host),
      // bare '/' (intercepted because regex requires a second char), and schemes
      // like 'javascript:' or 'data:'.
      if (!SAFE_NEXT_PATTERN.test(raw)) return '/me'
      return raw
    }

    export async function GET(req: NextRequest): Promise<NextResponse> {
      const url = new URL(req.url)
      const code = url.searchParams.get('code')
      const next = sanitizeNext(url.searchParams.get('next'))

      if (!code) {
        return NextResponse.redirect(new URL('/sign-in?error=missing_code', req.url))
      }

      const res = NextResponse.redirect(new URL(next, req.url))
      const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
          cookies: {
            getAll: () => req.cookies.getAll(),
            setAll: (toSet) =>
              toSet.forEach(({ name, value, options }) =>
                res.cookies.set(name, value, options)),
          },
        },
      )

      const { error } = await supabase.auth.exchangeCodeForSession(code)
      if (error) {
        return NextResponse.redirect(
          new URL(`/sign-in?error=${encodeURIComponent(error.message)}`, req.url),
        )
      }
      return res
    }

    // Exported for unit-testing the sanitizer in isolation (GAP-4 regression test).
    export { sanitizeNext, SAFE_NEXT_PATTERN }
    ```

    Two structural changes:
    1. `sanitizeNext` helper introduced. Called once with `searchParams.get('next')`. Return value is used in the redirect URL.
    2. The helper + regex are re-exported so the vitest spec can test them directly without spinning up the full route handler with Supabase mocks.

    **B. Create web/tests/auth-callback-sanitize.test.ts** with the regression cases:

    ```typescript
    // GAP-4 regression: callback route must reject absolute `next` URLs.
    // Tests the sanitizeNext() helper directly (faster than full-route mocking)
    // AND verifies the regex behavior end-to-end via NextRequest.
    import { describe, expect, it } from 'vitest'
    import { sanitizeNext, SAFE_NEXT_PATTERN } from '@/app/api/auth/callback/route'

    describe('sanitizeNext (GAP-4)', () => {
      it('falls back to /me when next is null', () => {
        expect(sanitizeNext(null)).toBe('/me')
      })

      it('falls back to /me when next is empty string', () => {
        expect(sanitizeNext('')).toBe('/me')
      })

      it('rejects absolute https URL (open-redirect attempt)', () => {
        expect(sanitizeNext('https://evil.example.com/path')).toBe('/me')
      })

      it('rejects absolute http URL', () => {
        expect(sanitizeNext('http://evil.example.com/')).toBe('/me')
      })

      it('rejects protocol-relative URL', () => {
        expect(sanitizeNext('//evil.example.com/path')).toBe('/me')
      })

      it('rejects javascript: scheme', () => {
        expect(sanitizeNext('javascript:alert(1)')).toBe('/me')
      })

      it('rejects data: scheme', () => {
        expect(sanitizeNext('data:text/html,evil')).toBe('/me')
      })

      it('rejects bare slash (no second segment)', () => {
        // `/` alone fails the (?!\/) lookahead only if followed by another slash;
        // here it's followed by end-of-string which the regex also requires a
        // non-slash char next. Confirms the regex is "/ followed by a non-slash CHAR",
        // not just "starts with /".
        expect(sanitizeNext('/')).toBe('/me')
      })

      it('preserves /admin', () => {
        expect(sanitizeNext('/admin')).toBe('/admin')
      })

      it('preserves /runs/abc-123', () => {
        expect(sanitizeNext('/runs/abc-123')).toBe('/runs/abc-123')
      })

      it('preserves /me/profile', () => {
        expect(sanitizeNext('/me/profile')).toBe('/me/profile')
      })

      it('regex directly: matches /foo', () => {
        expect(SAFE_NEXT_PATTERN.test('/foo')).toBe(true)
      })

      it('regex directly: does not match //foo', () => {
        expect(SAFE_NEXT_PATTERN.test('//foo')).toBe(false)
      })

      it('regex directly: does not match https://x', () => {
        expect(SAFE_NEXT_PATTERN.test('https://x')).toBe(false)
      })
    })
    ```

    NOTE: Path alias `@/app/...` requires `tsconfig.json` paths to be set. Plan 00-04 already configured this (`web/middleware.ts` uses `@/lib/auth/allowlist` and works). If the import fails at vitest collection, fall back to a relative path: `import { sanitizeNext } from '../app/api/auth/callback/route'`.

    Implements GAP-4 fix + regression coverage per .planning/phases/00-foundation/00-VERIFICATION.md.
  </action>
  <verify>
    <automated>grep -c "sanitizeNext" web/app/api/auth/callback/route.ts && test -f web/tests/auth-callback-sanitize.test.ts && grep -c "GAP-4" web/tests/auth-callback-sanitize.test.ts</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "sanitizeNext" web/app/api/auth/callback/route.ts` matches (helper exists)
    - `grep -q "export.*sanitizeNext.*SAFE_NEXT_PATTERN" web/app/api/auth/callback/route.ts` matches (re-export for testing)
    - `grep -q "SAFE_NEXT_PATTERN.*=.*/\^\\\\/" web/app/api/auth/callback/route.ts` OR `grep -q "/\^.../(?!" web/app/api/auth/callback/route.ts` (the whitelist regex is present)
    - `grep -q "GAP-4" web/app/api/auth/callback/route.ts` matches (traceability)
    - `test -f web/tests/auth-callback-sanitize.test.ts` succeeds
    - `grep -c "it(" web/tests/auth-callback-sanitize.test.ts` returns >= 13 (at least 13 test cases — null, empty, https, http, //, javascript:, data:, /, /admin, /runs/abc, /me/profile, 3 regex-direct)
    - `grep -q "evil.example.com" web/tests/auth-callback-sanitize.test.ts` matches (the specific test from VERIFICATION.md)
    - If vitest is installed in the repo: `cd web && pnpm test -- --run auth-callback-sanitize 2>&1` exits 0 with all tests passing. (If vitest not yet wired locally, the grep gates above prove structural correctness; the CI workflow web-tests job will run the spec.)
  </acceptance_criteria>
  <done>Callback route exports sanitizeNext + SAFE_NEXT_PATTERN; whitelist regex rejects absolute URLs; vitest file exists with >= 13 cases covering all the documented attack shapes from VERIFICATION.md.</done>
</task>

</tasks>

<verification>
- `bash -n scripts/eval-ci.sh scripts/tests/eval-ci-dry-run.sh` exits 0 for both
- `grep -c "GAP-3\|GAP-4" scripts/eval-ci.sh scripts/tests/eval-ci-dry-run.sh web/app/api/auth/callback/route.ts web/tests/auth-callback-sanitize.test.ts` returns >= 4 (each fix file references its gap)
- `! grep -E 'dry-run OK.*sys.exit\(0\)' scripts/eval-ci.sh` — broken early-exit pattern is gone
- The eval-ci dry-run regression test runnable when Python + business_checker are installed: `unset PERPLEXITY_API_KEY_EVAL; bash scripts/tests/eval-ci-dry-run.sh` exits 0
- The vitest sanitize spec runnable when web/ pnpm install has completed: `cd web && pnpm test -- --run auth-callback-sanitize` exits 0
</verification>

<success_criteria>
- Codex GAP-3 closed: eval-CI gate enforces unconditionally; absent PERPLEXITY_API_KEY_EVAL no longer produces false-negative passes. ANALYTICS-04 contract restored.
- Codex GAP-4 closed: the auth callback rejects open-redirect attempts via a minimal whitelist regex. AUTH-01 hardened against the documented phishing primitive.
- Two regression tests exist (bash + vitest) that would catch reintroduction of either bug.
- No new dependencies. No schema changes. No codegen baseline impact. Smallest of the 3 gap-closure plans by surface area.
</success_criteria>

<parallel_execution>
This plan runs in Wave 7 — AFTER Plans 00-07 and 00-08 (Wave 6) so the security-relevant migrations land first and the diff stays clean. Wave 7 ordering is structural, not technical — 00-09 has no actual code dependency on 0009/0010, but landing security fixes first keeps the commit history readable.

File ownership: scripts/eval-ci.sh (edit), web/app/api/auth/callback/route.ts (edit), web/tests/auth-callback-sanitize.test.ts (new), scripts/tests/eval-ci-dry-run.sh (new). No overlap with Wave 6 plans.

This plan is intentionally autonomous (no checkpoints) — both fixes are mechanical patches with structural acceptance gates.
</parallel_execution>

<output>
After completion, create `.planning/phases/00-foundation/00-09-gate-hygiene-fixes-SUMMARY.md` documenting: (1) the eval-ci.sh refactor (broken dry-run branch removed; python→python3), (2) the sanitizeNext helper + whitelist regex, (3) the 2 new regression test files (bash + vitest), (4) explicit confirmation that GAP-3 and GAP-4 from VERIFICATION.md are closed.
</output>
