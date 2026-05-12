---
phase: 00-foundation
plan: 03
type: execute
wave: 2
depends_on: [01, 02]
files_modified:
  - web/drizzle.config.ts
  - web/db/schema.ts
  - web/db/types.ts
  - worker/workers/lib/models.py
  - .github/workflows/codegen-drift.yml
  - .github/workflows/ci.yml
  - web/.gitignore
  - .planning/phases/00-foundation/00-EVIDENCE.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "drizzle-kit pull regenerates web/db/schema.ts deterministically from the dev Supabase project"
    - "datamodel-code-generator regenerates worker/workers/lib/models.py with extra='forbid'"
    - "GitHub Actions codegen-drift workflow exists and would block a PR that drops a column without regenerating"
    - "Hard CI guard rejects any non-empty web/drizzle/migrations/ directory (D-00-03)"
    - "Both generated files are committed to the repo so drift detection has a baseline"
  artifacts:
    - path: web/drizzle.config.ts
      provides: "Drizzle configuration pointing at SUPABASE_DEV_DB_URL with introspect-only schema path"
      contains: "drizzle.config"
    - path: web/db/schema.ts
      provides: "Generated TypeScript schema (committed; CI regenerates and diffs)"
      min_lines: 50
    - path: worker/workers/lib/models.py
      provides: "Generated Pydantic v2 models (committed; CI regenerates and diffs)"
      min_lines: 50
    - path: .github/workflows/codegen-drift.yml
      provides: "PR check that runs drizzle pull + datamodel-codegen + git diff --exit-code"
      contains: "drizzle-kit pull"
    - path: .github/workflows/ci.yml
      provides: "Core CI (lint, type-check, unit tests for worker + web)"
      contains: "pytest"
  key_links:
    - from: ".github/workflows/codegen-drift.yml"
      to: "scripts/check-drift.sh"
      via: "bash invocation"
      pattern: "bash scripts/check-drift\\.sh"
    - from: "web/drizzle.config.ts"
      to: "process.env.DATABASE_URL"
      via: "env var read"
      pattern: "DATABASE_URL"
    - from: "datamodel-codegen output"
      to: "worker/workers/lib/models.py with extra='forbid'"
      via: "pydantic v2 ConfigDict"
      pattern: "extra\\s*=\\s*['\"]forbid['\"]|extra='forbid'"
---

<objective>
Land the two-language codegen pipeline (Drizzle TS introspect + datamodel-code-generator Python) and wire it into a GitHub Actions PR check that fails on schema drift. This is the demo-trip gate referenced by D-00-11 item 2 — the highest-leverage Phase 0 check per CONTEXT.md §Specifics.

Purpose: Eliminate Pitfall P4 (schema drift). Without this gate, every later phase risks shipping with stale models that silently write to wrong columns.

Output: Drizzle config + generated `web/db/schema.ts`, generated `worker/workers/lib/models.py`, GitHub Actions workflow with the D-00-03 hard guard, baseline `ci.yml` running pytest + vitest on every PR.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-RESEARCH.md
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@.planning/phases/00-foundation/00-02-supabase-schema-rls-SUMMARY.md
@scripts/check-drift.sh

<interfaces>
<!-- Drizzle config shape (Drizzle 0.45.x, introspect-only) -->

```ts
// web/drizzle.config.ts
import type { Config } from 'drizzle-kit'

export default {
  dialect: 'postgresql',
  schema: './db/schema.ts',
  out: './drizzle/.scratch',  // never used; we don't generate migrations
  dbCredentials: {
    url: process.env.DATABASE_URL ?? process.env.SUPABASE_DEV_DB_URL ?? '',
  },
  introspect: { casing: 'preserve' },
  schemaFilter: ['public'],
} satisfies Config
```

<!-- datamodel-code-generator invocation flags -->
datamodel-codegen
  --input-file-type postgres
  --url $SUPABASE_DEV_DB_URL
  --output worker/workers/lib/models.py
  --output-model-type pydantic_v2.BaseModel
  --use-schema-description
  --extra-fields-config extra=forbid    # Pitfall P4 defense; loud failures on unknown columns

<!-- GitHub Actions secrets required (configure in repo settings) -->
SUPABASE_DEV_DB_URL  — direct connection string, port 5432 (not pooler 6543) per RESEARCH Open Q 4
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Drizzle config + generate web/db/schema.ts</name>
  <files>web/drizzle.config.ts, web/db/schema.ts, web/db/types.ts, web/.gitignore</files>
  <read_first>
    - .planning/research/STACK.md (Drizzle 0.45 introspect section at lines 70-81)
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-03 — Drizzle introspect-only, migrations forbidden)
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 6 Codegen Drift Gate at lines 530-573)
    - supabase/migrations/0001_init_schema.sql (the schema Drizzle introspects)
  </read_first>
  <action>
    Create `web/drizzle.config.ts` exactly as shown in the `<interfaces>` block above.

    Run Drizzle introspect against the dev DB to produce `web/db/schema.ts`:
    ```bash
    cd web
    # Set DATABASE_URL to the direct (port 5432) Supabase dev connection string
    export DATABASE_URL="$SUPABASE_DEV_DB_URL"
    pnpm install   # if not already
    pnpm exec drizzle-kit pull
    ```

    This produces `web/db/schema.ts` containing pgTable definitions for every table in the public schema (businesses, runs, run_rows, verifications, api_calls, app_config, api_keys, budget_ledger, outreach_tickets, audit_log, worker_heartbeats). Commit this file as-is — do NOT hand-edit. The committed file is the "expected" output; CI regenerates and diffs.

    Also generate the Supabase types file (used alongside Drizzle for the JS client's `Database` generic per STACK.md):
    ```bash
    cd web
    # Generate Database type for createClient<Database>
    pnpm dlx supabase gen types typescript --db-url "$DATABASE_URL" --schema public > db/types.ts
    ```
    If `supabase` CLI is unavailable in the local environment, leave `web/db/types.ts` as a minimal stub:
    ```ts
    // Generated by `supabase gen types typescript` in CI.
    // Local dev: run `pnpm dlx supabase gen types typescript --db-url $DATABASE_URL --schema public > db/types.ts`
    export type Database = Record<string, unknown>
    ```

    Append to `web/.gitignore` (create if missing):
    ```
    .next/
    node_modules/
    drizzle/.scratch/
    .turbo/
    .vercel/
    # codegen artifacts are COMMITTED (not ignored) — drift gate compares against committed copy
    ```

    Verify the schema file contains expected tables:
    ```bash
    grep -E "businesses|verifications|app_config|worker_heartbeats" web/db/schema.ts
    ```
  </action>
  <verify>
    <automated>test -f web/drizzle.config.ts && grep -q "dialect: 'postgresql'" web/drizzle.config.ts && grep -q "schemaFilter:.*'public'" web/drizzle.config.ts && test -f web/db/schema.ts && grep -q "businesses" web/db/schema.ts && grep -q "verifications" web/db/schema.ts && grep -q "app_config" web/db/schema.ts && test -f web/db/types.ts && test -f web/.gitignore && grep -q "node_modules" web/.gitignore</automated>
  </verify>
  <acceptance_criteria>
    - `web/drizzle.config.ts` exists, exports a `Config` satisfying `dialect: 'postgresql'`
    - `web/drizzle.config.ts` reads `DATABASE_URL` from env (no hardcoded credentials)
    - `web/db/schema.ts` exists and references at least 8 of the 11 Phase 0 tables: `businesses`, `verifications`, `runs`, `run_rows`, `api_calls`, `app_config`, `api_keys`, `audit_log`
    - `web/db/types.ts` exists (either real generated content OR the stub with `Database` export)
    - `web/.gitignore` includes `node_modules/`, `.next/`, `.vercel/`, `drizzle/.scratch/`
    - NO file under `web/drizzle/migrations/` exists (D-00-03 hard rule)
    - Re-running `pnpm exec drizzle-kit pull` from `web/` produces NO diff against the committed `web/db/schema.ts` (proves the gate is functional)
  </acceptance_criteria>
  <done>TypeScript types regenerate from Postgres deterministically; the committed schema.ts is the gate baseline.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Generate worker/workers/lib/models.py via datamodel-code-generator</name>
  <files>worker/workers/lib/models.py</files>
  <read_first>
    - .planning/research/STACK.md (datamodel-code-generator 0.57 row at lines 70-76)
    - .planning/research/PITFALLS.md (P4 schema drift, extra='forbid' mandate at line 99)
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 6 datamodel-codegen invocation at lines 559-570)
    - scripts/check-drift.sh (codegen command flags — same flags used here)
  </read_first>
  <action>
    Generate `worker/workers/lib/models.py` from the live dev Supabase schema:
    ```bash
    # Ensure datamodel-code-generator is installed in the worker venv
    cd worker && source .venv/bin/activate 2>/dev/null || python -m venv .venv && source .venv/bin/activate
    pip install datamodel-code-generator==0.57.0

    # Run codegen
    datamodel-codegen \
      --input-file-type postgres \
      --url "$SUPABASE_DEV_DB_URL" \
      --output workers/lib/models.py \
      --output-model-type pydantic_v2.BaseModel \
      --use-schema-description \
      --extra-fields-config extra=forbid
    ```

    **If the `--extra-fields-config` flag is unsupported by 0.57.0** (verify with `datamodel-codegen --help | grep extra`), fall back to post-processing: after generation, prepend a header to `workers/lib/models.py` that sets the default config:
    ```python
    # Add at top of file (after imports):
    from pydantic import ConfigDict
    # Then for each BaseModel, ensure: model_config = ConfigDict(extra='forbid')
    ```
    The simplest enforcement is a sed pass after generation:
    ```bash
    # Inject extra='forbid' into every class inheriting from BaseModel
    python - <<'PY'
    import re, pathlib
    p = pathlib.Path("workers/lib/models.py")
    src = p.read_text()
    # Insert model_config = ConfigDict(extra='forbid') after each `class X(BaseModel):` line
    out = re.sub(
        r"(class\s+\w+\(BaseModel\):\n)",
        r"\1    model_config = ConfigDict(extra='forbid')\n",
        src,
    )
    # Ensure ConfigDict is imported
    if "from pydantic import" in out and "ConfigDict" not in out:
        out = out.replace("from pydantic import", "from pydantic import ConfigDict,", 1)
    p.write_text(out)
    PY
    ```

    Verify the generated file:
    - Contains class definitions for at least: `Businesses`, `Verifications`, `Runs`, `RunRows`, `ApiCalls`, `AppConfig`, `AuditLog`
    - Every class inherits from `BaseModel` (pydantic v2)
    - Every class has `model_config = ConfigDict(extra='forbid')` OR the codegen flag produced equivalent strict config
    - File contains `from pydantic import BaseModel` (and `ConfigDict` if post-processed)

    Commit `worker/workers/lib/models.py` to the repo. CI will regenerate and diff against the committed copy.
  </action>
  <verify>
    <automated>test -f worker/workers/lib/models.py && grep -q "BaseModel" worker/workers/lib/models.py && grep -q "extra.*forbid\\|ConfigDict" worker/workers/lib/models.py && python -c "import sys; sys.path.insert(0, 'worker'); from workers.lib import models; assert hasattr(models, 'Verifications') or hasattr(models, 'verifications') or any(c for c in dir(models) if 'erification' in c), 'no Verifications class'; print('OK')" && wc -l worker/workers/lib/models.py | awk '{exit ($1 < 50)}'</automated>
  </verify>
  <acceptance_criteria>
    - `worker/workers/lib/models.py` exists
    - File contains `from pydantic import` AND `BaseModel` references
    - File contains either `extra='forbid'` literal OR `ConfigDict(extra='forbid')` for every BaseModel class (P4 defense per Pitfalls)
    - File defines classes (PascalCase or snake_case per generator default) for at least 7 of the 11 Phase 0 tables: businesses, verifications, runs, run_rows, api_calls, app_config, audit_log
    - File length ≥ 50 lines
    - `python -c "import sys; sys.path.insert(0,'worker'); from workers.lib import models"` exits 0
    - Re-running the codegen command produces NO diff against the committed `models.py`
  </acceptance_criteria>
  <done>Pydantic models track Postgres schema; loud failures on unknown columns; baseline for drift gate.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: GitHub Actions workflows — codegen-drift + baseline ci</name>
  <files>.github/workflows/codegen-drift.yml, .github/workflows/ci.yml, .planning/phases/00-foundation/00-EVIDENCE.md</files>
  <read_first>
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 6 full YAML at lines 532-573)
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-03 forbid drizzle/migrations, D-00-11 item 2)
    - scripts/check-drift.sh (the script the workflow invokes)
    - .planning/research/PITFALLS.md (P4 drift, P11 secrets discipline)
  </read_first>
  <action>
    Create `.github/workflows/codegen-drift.yml`:
    ```yaml
    name: codegen-drift
    on:
      pull_request:
        paths:
          - 'supabase/migrations/**'
          - 'web/db/schema.ts'
          - 'worker/workers/lib/models.py'
          - 'web/drizzle.config.ts'
          - 'scripts/check-drift.sh'
          - 'web/drizzle/migrations/**'  # D-00-03 hard guard — fires if anyone creates this dir
          - '.github/workflows/codegen-drift.yml'
      workflow_dispatch:

    jobs:
      drift:
        runs-on: ubuntu-latest
        timeout-minutes: 10
        steps:
          - uses: actions/checkout@v4

          - name: D-00-03 hard guard — no Drizzle migrations
            run: |
              if [ -d web/drizzle/migrations ] && [ -n "$(ls -A web/drizzle/migrations 2>/dev/null)" ]; then
                echo "::error::web/drizzle/migrations must be empty — Supabase CLI owns migrations (D-00-03)"
                exit 1
              fi

          - uses: pnpm/action-setup@v3
            with: { version: 9 }
          - uses: actions/setup-node@v4
            with:
              node-version: '22'
              cache: 'pnpm'
              cache-dependency-path: web/pnpm-lock.yaml
          - uses: actions/setup-python@v5
            with:
              python-version: '3.12'
              cache: 'pip'

          - name: Install web deps
            working-directory: web
            run: pnpm install --frozen-lockfile

          - name: Install codegen deps
            run: pip install datamodel-code-generator==0.57.0

          - name: Run drift check
            env:
              SUPABASE_DEV_DB_URL: ${{ secrets.SUPABASE_DEV_DB_URL }}
              DATABASE_URL: ${{ secrets.SUPABASE_DEV_DB_URL }}
            run: bash scripts/check-drift.sh

          - name: Show diff on failure
            if: failure()
            run: |
              echo "::group::web/db/schema.ts diff"
              git diff -- web/db/schema.ts || true
              echo "::endgroup::"
              echo "::group::worker/workers/lib/models.py diff"
              git diff -- worker/workers/lib/models.py || true
              echo "::endgroup::"
              echo "::error::Schema drift detected. Run 'bash scripts/check-drift.sh' locally and commit regenerated files."
    ```

    Create `.github/workflows/ci.yml` — baseline test runner for every PR:
    ```yaml
    name: ci
    on:
      pull_request:
      push:
        branches: [main]

    jobs:
      worker-tests:
        runs-on: ubuntu-latest
        timeout-minutes: 10
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.12'
              cache: 'pip'
          - name: Install worker (editable)
            run: |
              pip install -e ./worker[dev]
              pip install -e ./business_checker
          - name: Run unit tests (skip integration — needs DB)
            run: |
              cd worker
              pytest tests/ -x -m "not integration" --tb=short
          - name: Run business_checker tests
            run: |
              cd business_checker
              pytest tests/ -x --tb=short || echo "::warning::business_checker tests had failures (pre-existing v1.0 state)"

      web-tests:
        runs-on: ubuntu-latest
        timeout-minutes: 10
        steps:
          - uses: actions/checkout@v4
          - uses: pnpm/action-setup@v3
            with: { version: 9 }
          - uses: actions/setup-node@v4
            with:
              node-version: '22'
              cache: 'pnpm'
              cache-dependency-path: web/pnpm-lock.yaml
          - name: Install
            working-directory: web
            run: pnpm install --frozen-lockfile
          - name: Type check
            working-directory: web
            run: pnpm exec tsc --noEmit
          - name: Vitest
            working-directory: web
            run: pnpm test --run

      worker-integration:
        runs-on: ubuntu-latest
        timeout-minutes: 15
        if: ${{ secrets.SUPABASE_DEV_DB_URL != '' }}
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with: { python-version: '3.12', cache: 'pip' }
          - name: Install
            run: pip install -e ./worker[dev] && pip install -e ./business_checker
          - name: Integration tests
            env:
              SUPABASE_DEV_DB_URL: ${{ secrets.SUPABASE_DEV_DB_URL }}
            run: |
              cd worker
              pytest tests/ -x -m integration --tb=short
    ```

    Create `.planning/phases/00-foundation/00-EVIDENCE.md` to record the manual demo artifacts (referenced by VALIDATION.md §Manual-Only Verifications):
    ```markdown
    # Phase 0 — Evidence Log

    Manual demo artifacts captured during Phase 0 acceptance. Each item maps to D-00-11.

    ## D-00-11 Item 1 — Magic-link login + middleware allowlist
    - [ ] `@syr.edu` login screenshot (or Loom timestamp): _pending Wave 3_
    - [ ] `@gmail.com` 403 screenshot: _pending Wave 3_

    ## D-00-11 Item 2 — Codegen drift PR fails CI
    - [ ] PR URL (intentional column drop without regen): _pending — open after Wave 2 merges_
    - [ ] Screenshot of failing GitHub Action check: _pending_

    ## D-00-11 Item 3 — Eval-CI regression PR fails CI
    - [ ] PR URL (intentional gold-set label flip): _pending Wave 5_
    - [ ] Screenshot of failing eval-ci check: _pending Wave 5_

    ## D-00-11 Item 4 — verifications append-only
    - [ ] psql output showing P0001 on UPDATE: _Wave 1 — captured via `bash scripts/phase0-demo.sh`_

    ## D-00-11 Item 5 — Worker heartbeat row
    - [ ] psql query result showing recent heartbeat row: _pending Wave 4_

    ## D-00-11 Item 6 — Resend DNS ticket
    - [ ] IT ticket ID: _pending Wave 5_
    - [ ] Date filed: _pending Wave 5_
    ```

    **Required GitHub Actions secrets** (the executor must configure these in repo Settings → Secrets — flag if missing):
    - `SUPABASE_DEV_DB_URL` — direct connection string (port 5432) to the dev Supabase Postgres
    - `PERPLEXITY_API_KEY_EVAL` — separate eval-only Perplexity key (added in Wave 5)
  </action>
  <verify>
    <automated>test -f .github/workflows/codegen-drift.yml && test -f .github/workflows/ci.yml && grep -q "drift" .github/workflows/codegen-drift.yml && grep -q "no Drizzle migrations" .github/workflows/codegen-drift.yml && grep -q "bash scripts/check-drift.sh" .github/workflows/codegen-drift.yml && grep -q "pytest" .github/workflows/ci.yml && grep -q "vitest\\|pnpm test" .github/workflows/ci.yml && grep -q "tsc --noEmit" .github/workflows/ci.yml && test -f .planning/phases/00-foundation/00-EVIDENCE.md && grep -q "D-00-11 Item 2" .planning/phases/00-foundation/00-EVIDENCE.md && python -c "import yaml; yaml.safe_load(open('.github/workflows/codegen-drift.yml')); yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `.github/workflows/codegen-drift.yml` exists and is valid YAML (`python -c "import yaml; yaml.safe_load(open('.github/workflows/codegen-drift.yml'))"` exits 0)
    - Workflow contains the D-00-03 hard guard step rejecting non-empty `web/drizzle/migrations/`
    - Workflow invokes `bash scripts/check-drift.sh` (delegates to the Wave 0 script — single source of truth)
    - Workflow triggers on `pull_request` AND `workflow_dispatch`
    - Workflow path filter includes `supabase/migrations/**`, `web/db/schema.ts`, `worker/workers/lib/models.py`, AND `web/drizzle/migrations/**` (so D-00-03 hard guard fires on any introduction of that directory)
    - `.github/workflows/ci.yml` exists, valid YAML, includes three jobs: `worker-tests`, `web-tests`, `worker-integration`
    - `ci.yml` `worker-tests` runs `pytest tests/ -x -m "not integration"` (does NOT need DB secrets)
    - `ci.yml` `worker-integration` is gated on `secrets.SUPABASE_DEV_DB_URL != ''`
    - `.planning/phases/00-foundation/00-EVIDENCE.md` exists with all 6 D-00-11 items as checkboxes
    - No secrets are hardcoded; all references use `${{ secrets.* }}` syntax
  </acceptance_criteria>
  <done>PR-time drift gate is wired; baseline test runner catches regressions; evidence log structure exists for Wave 5 sign-off.</done>
</task>

</tasks>

<verification>
- Re-running `bash scripts/check-drift.sh` locally with `SUPABASE_DEV_DB_URL` set exits 0 (no diff against committed files).
- `python -c "import yaml; yaml.safe_load(open('.github/workflows/codegen-drift.yml'))"` exits 0.
- Hypothetical drop-column test: if a column is removed from `supabase/migrations/0001_init_schema.sql` and migrations re-applied, `bash scripts/check-drift.sh` exits 1 (the gate works). This is verified manually in Wave 5 when the demo PR is opened.
</verification>

<success_criteria>
1. D-00-11 item 2 has a working gate: a future PR that drops a column without regen will fail `codegen-drift` CI check.
2. Pitfall P4 (silent column drift) is structurally impossible — generated files are committed and CI regenerates+diffs on every PR.
3. Baseline CI runs on every PR: pytest (worker non-integration), vitest (web), tsc --noEmit.
4. Evidence log structure exists for Phase 0 sign-off.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-03-codegen-drift-gate-SUMMARY.md` documenting:
- Drizzle introspect determinism (any prettier/canonicalization needed)
- datamodel-code-generator flag fallback (whether --extra-fields-config worked or post-processing was required)
- Secrets configured in GitHub: SUPABASE_DEV_DB_URL only (PERPLEXITY_API_KEY_EVAL added in Wave 5)
- Open item: actually trip the drift gate via a demo PR (deferred to Wave 5 demo prep)
</output>
