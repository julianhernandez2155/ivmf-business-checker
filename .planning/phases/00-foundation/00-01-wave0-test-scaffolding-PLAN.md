---
phase: 00-foundation
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - worker/pyproject.toml
  - worker/tests/conftest.py
  - worker/tests/test_schema.py
  - worker/tests/test_append_only.py
  - worker/tests/test_audit_trigger.py
  - worker/tests/test_pgmq.py
  - worker/tests/test_rls_domain_allowlist.py
  - worker/tests/test_allowlist_admin.py
  - worker/tests/test_heartbeat.py
  - worker/tests/test_worker_loop.py
  - worker/tests/test_normalize.py
  - worker/tests/test_verifications_schema.py
  - worker/tests/test_businesses_schema.py
  - worker/tests/test_api_calls.py
  - worker/tests/test_rbac.py
  - worker/tests/test_app_config.py
  - web/package.json
  - web/vitest.config.ts
  - web/tests/middleware-allowlist.test.ts
  - web/tests/auth-magic-link.spec.ts
  - scripts/check-drift.sh
  - scripts/eval-ci.sh
  - scripts/phase0-demo.sh
  - Makefile
  - .gitignore
autonomous: true
requirements: []
must_haves:
  truths:
    - "Test scaffolding exists for every requirement covered in Phase 0"
    - "Every later-wave task has an automated <verify> target file that already exists"
    - "Tests fail loudly (xfail / pending markers) until later waves wire real assertions"
  artifacts:
    - path: worker/pyproject.toml
      provides: "pytest 8.x config + dev deps (pytest, psycopg[binary], pytest-postgresql)"
      contains: "[tool.pytest.ini_options]"
    - path: worker/tests/conftest.py
      provides: "Shared psycopg fixture pointed at SUPABASE_DEV_DB_URL"
      min_lines: 20
    - path: web/vitest.config.ts
      provides: "vitest configuration with jsdom and @/ alias"
      min_lines: 10
    - path: scripts/phase0-demo.sh
      provides: "Bash script exercising D-00-11 demo items 1, 4, 5"
      min_lines: 30
    - path: Makefile
      provides: "make test, make test-quick, make drift, make eval targets"
      contains: "test:"
  key_links:
    - from: "all 14 worker/tests/*.py files"
      to: "worker/tests/conftest.py"
      via: "psycopg fixture import"
      pattern: "from\\s+conftest|@pytest\\.fixture"
    - from: "scripts/phase0-demo.sh"
      to: "scripts/check-drift.sh AND scripts/eval-ci.sh"
      via: "shell invocation"
      pattern: "bash scripts/(check-drift|eval-ci)\\.sh"
---

<objective>
Create the Wave 0 test scaffolding referenced by every later wave's `<verify>` field. This plan does not implement schema, auth, codegen, worker, or CI — it creates the empty test files, fixtures, configs, and helper scripts so subsequent waves can fail loudly when their work isn't done. Per the Nyquist rule in `.planning/phases/00-foundation/00-VALIDATION.md`, every `<automated>` reference in later plans MUST point to a file created here.

Purpose: Block Wave 1+ from shipping untested code. The validation strategy doc (VALIDATION.md §Wave 0 Requirements) enumerates 16 files this plan creates.

Output: 14 pytest stub files, 2 vitest stubs, vitest+pytest configs, 3 CI helper scripts, Makefile.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-VALIDATION.md
@.planning/phases/00-foundation/00-RESEARCH.md
@business_checker/pyproject.toml

<interfaces>
<!-- Test fixture shape every test file imports -->

Expected fixture in worker/tests/conftest.py:
```python
import os
import pytest
import psycopg

@pytest.fixture(scope="session")
def db_url() -> str:
    url = os.environ.get("SUPABASE_DEV_DB_URL")
    if not url:
        pytest.skip("SUPABASE_DEV_DB_URL not set; skipping integration tests")
    return url

@pytest.fixture
def conn(db_url):
    with psycopg.connect(db_url, autocommit=False) as c:
        yield c
        c.rollback()
```

Stub test pattern (every test file follows this):
```python
import pytest

@pytest.mark.xfail(reason="Wave N pending — will be enabled when {feature} ships", strict=False)
def test_{behavior}():
    raise NotImplementedError("Wave N: implement assertion against {table/policy/file}")
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: pytest + vitest configs and shared fixtures</name>
  <files>worker/pyproject.toml, worker/tests/conftest.py, worker/tests/__init__.py, web/package.json, web/vitest.config.ts, web/tsconfig.json, .gitignore</files>
  <read_first>
    - .planning/phases/00-foundation/00-VALIDATION.md (Wave 0 Requirements section, lines 60-78)
    - .planning/phases/00-foundation/00-RESEARCH.md (Validation Architecture section, especially the Per-Task Verification Map)
    - .planning/research/STACK.md (Installation block, lines 86-110)
    - business_checker/pyproject.toml (existing Python package shape — mirror conventions)
  </read_first>
  <action>
    Create `worker/` as a NEW directory at repo root. Create `worker/pyproject.toml` with:
    ```toml
    [project]
    name = "ivmf-worker"
    version = "0.0.1"
    requires-python = ">=3.12"
    dependencies = [
      "fastapi==0.136.1",
      "uvicorn[standard]>=0.35.0,<0.36",
      "psycopg[binary,pool]==3.3.4",
      "tembo-pgmq-python==0.10.0",
      "tenacity==9.1.4",
      "structlog>=25.0",
      "pydantic==2.12.5",
    ]

    [project.optional-dependencies]
    dev = [
      "pytest>=8.0,<9.0",
      "pytest-asyncio>=0.24",
      "datamodel-code-generator==0.57.0",
    ]

    [tool.pytest.ini_options]
    testpaths = ["tests"]
    addopts = "-x -ra --strict-markers"
    markers = [
      "integration: requires SUPABASE_DEV_DB_URL",
      "ci_only: only runs in CI with secrets",
    ]
    ```

    Create `worker/tests/__init__.py` as empty file.

    Create `worker/tests/conftest.py` with the exact fixture shape from the `<interfaces>` block above (db_url + conn).

    Create `web/` directory. Create `web/package.json` with:
    ```json
    {
      "name": "ivmf-web",
      "version": "0.0.1",
      "private": true,
      "scripts": {
        "test": "vitest run",
        "test:watch": "vitest",
        "test:e2e": "vitest run --config vitest.e2e.config.ts"
      },
      "dependencies": {
        "next": "16.2.6",
        "react": "19.2.6",
        "react-dom": "19.2.6",
        "@supabase/supabase-js": "2.105.4",
        "@supabase/ssr": "0.10.3",
        "zod": "4.4.3",
        "drizzle-orm": "0.45.2",
        "postgres": "^3.4.0"
      },
      "devDependencies": {
        "drizzle-kit": "^0.45.0",
        "vitest": "^2.0.0",
        "@vitest/ui": "^2.0.0",
        "jsdom": "^25.0.0",
        "typescript": "^5.6.0",
        "@types/node": "^22.0.0",
        "@types/react": "^19.0.0",
        "tailwindcss": "4.3.0"
      },
      "engines": { "node": ">=22.0.0" }
    }
    ```

    Create `web/vitest.config.ts`:
    ```ts
    import { defineConfig } from 'vitest/config'
    import path from 'node:path'

    export default defineConfig({
      test: {
        environment: 'jsdom',
        globals: true,
        include: ['tests/**/*.{test,spec}.{ts,tsx}'],
      },
      resolve: {
        alias: { '@': path.resolve(__dirname, '.') },
      },
    })
    ```

    Create `web/tsconfig.json`:
    ```json
    {
      "compilerOptions": {
        "target": "ES2022",
        "lib": ["dom", "dom.iterable", "esnext"],
        "module": "esnext",
        "moduleResolution": "bundler",
        "jsx": "preserve",
        "strict": true,
        "esModuleInterop": true,
        "skipLibCheck": true,
        "resolveJsonModule": true,
        "isolatedModules": true,
        "noEmit": true,
        "incremental": true,
        "baseUrl": ".",
        "paths": { "@/*": ["./*"] }
      },
      "include": ["**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
      "exclude": ["node_modules"]
    }
    ```

    Append to `.gitignore` (create if missing) at repo root:
    ```
    # web/
    web/node_modules/
    web/.next/
    web/.vercel/
    # worker/
    worker/.venv/
    worker/__pycache__/
    worker/**/*.egg-info/
    worker/.pytest_cache/
    # codegen artifacts (committed but ignored during local regen scratch)
    # supabase
    supabase/.temp/
    .env
    .env.local
    ```
  </action>
  <verify>
    <automated>cd worker && python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); assert d['tool']['pytest']['ini_options']['testpaths']==['tests']" && test -f tests/conftest.py && grep -q "def db_url" tests/conftest.py && cd ../web && test -f vitest.config.ts && grep -q "jsdom" vitest.config.ts && grep -q '"next": "16.2.6"' package.json</automated>
  </verify>
  <acceptance_criteria>
    - `worker/pyproject.toml` exists; `python -c "import tomllib; tomllib.load(open('worker/pyproject.toml','rb'))"` exits 0
    - `worker/pyproject.toml` contains `psycopg[binary,pool]==3.3.4`, `tembo-pgmq-python==0.10.0`, `fastapi==0.136.1`, `pytest>=8.0`
    - `worker/tests/conftest.py` contains `def db_url` and `def conn` and references `SUPABASE_DEV_DB_URL`
    - `worker/tests/__init__.py` exists (zero bytes acceptable)
    - `web/package.json` contains `"next": "16.2.6"`, `"@supabase/ssr": "0.10.3"`, `"drizzle-orm": "0.45.2"`, `"vitest"`, `"engines"`
    - `web/vitest.config.ts` contains `jsdom` and `@` alias
    - `web/tsconfig.json` contains `"jsx": "preserve"` and `"strict": true`
    - `.gitignore` contains `web/node_modules/`, `worker/.venv/`, `.env.local`
  </acceptance_criteria>
  <done>Configs and fixtures exist; later test stubs can import from conftest; pytest discovers the worker/tests directory; vitest discovers web/tests directory.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: 14 pytest stub files (xfail) covering every Phase 0 requirement</name>
  <files>worker/tests/test_schema.py, worker/tests/test_append_only.py, worker/tests/test_audit_trigger.py, worker/tests/test_pgmq.py, worker/tests/test_rls_domain_allowlist.py, worker/tests/test_allowlist_admin.py, worker/tests/test_heartbeat.py, worker/tests/test_worker_loop.py, worker/tests/test_normalize.py, worker/tests/test_verifications_schema.py, worker/tests/test_businesses_schema.py, worker/tests/test_api_calls.py, worker/tests/test_rbac.py, worker/tests/test_app_config.py, web/tests/middleware-allowlist.test.ts, web/tests/auth-magic-link.spec.ts</name>
  <read_first>
    - .planning/phases/00-foundation/00-VALIDATION.md (Per-Task Verification Map table)
    - .planning/phases/00-foundation/00-RESEARCH.md (Phase Requirements → Test Map table at lines 805-823)
    - worker/tests/conftest.py (just created in Task 1 — fixture names to reference)
  </read_first>
  <action>
    Create each test file as an XFAIL stub. Each file MUST contain at least one test function decorated with `@pytest.mark.xfail(strict=False, reason="Wave N pending")` that raises `NotImplementedError`. This makes the test files discoverable by pytest collection (so later waves' `<verify>` commands resolve) while loudly failing if executed without implementation.

    File-by-file content:

    **worker/tests/test_schema.py** (CANON-05):
    ```python
    """CANON-05: businesses table exists with required columns."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending — businesses table not yet migrated")
    def test_businesses_table_exists(conn):
        with conn.cursor() as cur:
            cur.execute("select count(*) from information_schema.tables where table_schema='public' and table_name='businesses'")
            assert cur.fetchone()[0] == 1, "businesses table missing"
        raise NotImplementedError("Wave 1: assert full column shape per ARCHITECTURE.md table inventory")
    ```

    **worker/tests/test_append_only.py** (CANON-06):
    ```python
    """CANON-06: verifications BEFORE UPDATE/DELETE triggers + UNIQUE constraint."""
    import pytest
    import psycopg

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending — append-only triggers not yet installed")
    def test_update_raises_p0001(conn):
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.RaiseException):
                cur.execute("update verifications set status='active' where id = gen_random_uuid()")
        raise NotImplementedError("Wave 1: insert a real verifications row first, then assert UPDATE raises P0001")

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending")
    def test_delete_raises_p0001(conn):
        raise NotImplementedError("Wave 1: assert DELETE raises P0001")

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending")
    def test_unique_violation_run_row_pass(conn):
        raise NotImplementedError("Wave 1: assert duplicate (run_id, row_index, pass) raises 23505")
    ```

    **worker/tests/test_audit_trigger.py** (AUTH-04):
    ```python
    """AUTH-04: audit_log row with before/after diff on admin write."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending — audit_log_trigger not yet installed")
    def test_app_config_update_writes_diff(conn):
        raise NotImplementedError("Wave 1: update app_config, assert audit_log row with non-null diff jsonb")
    ```

    **worker/tests/test_pgmq.py** (D-00-09):
    ```python
    """D-00-09: q_verify and q_aggregator queues exist."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending — pgmq queues not yet created")
    def test_queues_exist(conn):
        with conn.cursor() as cur:
            cur.execute("select queue_name from pgmq.meta where queue_name in ('q_verify','q_aggregator')")
            names = {r[0] for r in cur.fetchall()}
            assert names == {'q_verify', 'q_aggregator'}
        raise NotImplementedError("Wave 4: verify worker long-poll uses vt=300 at call site")
    ```

    **worker/tests/test_rls_domain_allowlist.py** (AUTH-03):
    ```python
    """AUTH-03: auth.is_allowed_domain RLS function exists and blocks non-allowlisted."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 3 pending — RLS function not yet defined")
    def test_is_allowed_domain_function_exists(conn):
        with conn.cursor() as cur:
            cur.execute("select 1 from pg_proc where proname='is_allowed_domain' and pronamespace='auth'::regnamespace")
            assert cur.fetchone() is not None, "auth.is_allowed_domain missing"
        raise NotImplementedError("Wave 3: assert function returns true for @syr.edu and false for @gmail.com")
    ```

    **worker/tests/test_allowlist_admin.py** (AUTH-02):
    ```python
    """AUTH-02: admin can extend allowlist by editing app_config row."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending — app_config seed not yet shipped")
    def test_allowlist_extend(conn):
        raise NotImplementedError("Wave 1: update app_config row, assert auth.is_allowed_domain returns true for new domain")
    ```

    **worker/tests/test_heartbeat.py** (D-00-11 item 5):
    ```python
    """D-00-11 item 5: worker_heartbeats row written by worker."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 4 pending — worker not yet running")
    def test_heartbeat_row_within_30s(conn):
        raise NotImplementedError("Wave 4: query worker_heartbeats for row with last_seen_at within 30s of NOW()")
    ```

    **worker/tests/test_worker_loop.py** (D-00-09 long-poll):
    ```python
    """D-00-09: worker long-polls q_verify with vt=300 at call site."""
    import pytest

    @pytest.mark.xfail(strict=False, reason="Wave 4 pending — dispatcher not yet implemented")
    def test_dispatcher_uses_vt_300():
        raise NotImplementedError("Wave 4: import dispatcher; assert read_with_poll called with vt=300")
    ```

    **worker/tests/test_normalize.py** (CANON-03):
    ```python
    """CANON-03: normalize helpers for name/domain/phone/address."""
    import pytest

    @pytest.mark.xfail(strict=False, reason="Wave 1 pending — normalize helpers not yet shipped")
    def test_normalize_name_strips_suffix():
        raise NotImplementedError("Wave 1: assert normalize_name('Acme Corp, LLC') == 'acme corp'")

    @pytest.mark.xfail(strict=False, reason="Wave 1 pending")
    def test_normalize_phone_e164():
        raise NotImplementedError("Wave 1: assert normalize_phone('(315) 443-1234') == '+13154431234'")
    ```

    **worker/tests/test_verifications_schema.py** (CANON-08):
    ```python
    """CANON-08: verifications has provenance jsonb, method text NOT NULL, match_signals jsonb."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending")
    def test_verifications_columns(conn):
        raise NotImplementedError("Wave 1: introspect information_schema.columns for verifications; assert column set")
    ```

    **worker/tests/test_businesses_schema.py** (CANON-05):
    ```python
    """CANON-05: businesses table accepts new canonical row with required NOT NULLs."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending")
    def test_businesses_required_columns(conn):
        raise NotImplementedError("Wave 1: introspect; assert id, name, created_at NOT NULL")
    ```

    **worker/tests/test_api_calls.py** (CANON-07 api_calls UNIQUE):
    ```python
    """CANON-07: api_calls table with UNIQUE (provider, request_hash)."""
    import pytest
    import psycopg

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending")
    def test_unique_violation(conn):
        raise NotImplementedError("Wave 1: insert duplicate api_calls row, assert psycopg.errors.UniqueViolation (23505)")
    ```

    **worker/tests/test_rbac.py** (AUTH-03):
    ```python
    """AUTH-03: app_metadata.role claims propagate through middleware AND RLS."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 3 pending — RBAC policies not yet shipped")
    def test_role_in_jwt():
        raise NotImplementedError("Wave 3: mint a token with app_metadata.role='admin'; assert RLS policy admits")
    ```

    **worker/tests/test_app_config.py** (AUTH-02 + D-00-10):
    ```python
    """AUTH-02 + D-00-10: app_config seed rows exist."""
    import pytest

    @pytest.mark.integration
    @pytest.mark.xfail(strict=False, reason="Wave 1 pending — seed not yet applied")
    def test_email_domain_allowlist_seeded(conn):
        with conn.cursor() as cur:
            cur.execute("select value from app_config where key='email_domain_allowlist'")
            row = cur.fetchone()
            assert row is not None
            assert 'syr.edu' in row[0]
        raise NotImplementedError("Wave 1: also assert column_allowlist row exists per D-00-10")
    ```

    **web/tests/middleware-allowlist.test.ts** (AUTH-02):
    ```ts
    import { describe, it, expect } from 'vitest'

    describe('middleware allowlist (AUTH-02)', () => {
      it.fails('blocks @gmail.com with 403 + clear message', async () => {
        // Wave 3 pending — middleware not yet implemented.
        throw new Error('Wave 3: import middleware; mock @supabase/ssr getUser to return @gmail.com user; assert 403 + message contains allowlist')
      })

      it.fails('admits @syr.edu user', async () => {
        throw new Error('Wave 3: same as above with @syr.edu; assert NextResponse.next() called')
      })
    })
    ```

    **web/tests/auth-magic-link.spec.ts** (AUTH-01):
    ```ts
    import { describe, it, expect } from 'vitest'

    describe('magic-link login round-trip (AUTH-01)', () => {
      it.fails('redirects unauthenticated user from / to /sign-in', async () => {
        throw new Error('Wave 3: render middleware with no user; assert redirect to /sign-in')
      })

      it.fails('/me page shows email and role for authenticated user', async () => {
        throw new Error('Wave 3: mock authenticated session; render /me; assert email + role in DOM')
      })
    })
    ```
  </action>
  <verify>
    <automated>cd worker && python -m pytest tests/ --collect-only -q 2>&1 | grep -E "collected\\s+([2-9][0-9]|1[0-9])\\s+items" && cd ../web && test -f tests/middleware-allowlist.test.ts && test -f tests/auth-magic-link.spec.ts && grep -l "it.fails\\|xfail" web/tests/*.ts worker/tests/*.py | wc -l | awk '{exit ($1 < 16)}'</automated>
  </verify>
  <acceptance_criteria>
    - All 14 `worker/tests/test_*.py` files exist
    - `pytest worker/tests --collect-only -q` reports at least 18 collected tests (across all files)
    - Every test file contains `@pytest.mark.xfail` decorator with `strict=False`
    - Every test file references the requirement ID in its docstring (CANON-XX, AUTH-XX, etc.)
    - `web/tests/middleware-allowlist.test.ts` exists and uses `it.fails(...)` pattern
    - `web/tests/auth-magic-link.spec.ts` exists and uses `it.fails(...)` pattern
    - No test file is empty; minimum 6 lines each
    - `grep -c "NotImplementedError\\|throw new Error" worker/tests/*.py web/tests/*.ts` returns ≥ 16
  </acceptance_criteria>
  <done>Every later-wave `<automated>` reference resolves to a real file; pytest and vitest can collect tests; xfail markers prevent the suite from going red while the stubs remain unimplemented.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: CI helper scripts + Makefile</name>
  <files>scripts/check-drift.sh, scripts/eval-ci.sh, scripts/phase0-demo.sh, Makefile</files>
  <read_first>
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 6: Codegen Drift Gate lines 532-573; Pattern 7: Eval-CI Regression Gate lines 575-611)
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-11 exit demo items 1-6)
    - .planning/phases/00-foundation/00-VALIDATION.md (Manual-Only Verifications table lines 81-87)
  </read_first>
  <action>
    Create `scripts/check-drift.sh` (executable bash):
    ```bash
    #!/usr/bin/env bash
    # Runs Drizzle introspect + datamodel-codegen and fails if either produces a diff against committed files.
    # Consumed by .github/workflows/codegen-drift.yml (Wave 2) and locally via `make drift`.
    set -euo pipefail

    if [ -z "${SUPABASE_DEV_DB_URL:-}" ]; then
      echo "ERROR: SUPABASE_DEV_DB_URL is required" >&2
      exit 2
    fi

    # D-00-03 hard guard: web/drizzle/migrations must NOT exist or must be empty
    if [ -d web/drizzle/migrations ] && [ -n "$(ls -A web/drizzle/migrations 2>/dev/null || true)" ]; then
      echo "ERROR: web/drizzle/migrations must be empty — Supabase CLI owns migrations (D-00-03)" >&2
      exit 1
    fi

    echo "==> Drizzle introspect"
    (cd web && pnpm exec drizzle-kit pull)

    echo "==> Pydantic codegen"
    datamodel-codegen \
      --input-file-type postgres \
      --url "$SUPABASE_DEV_DB_URL" \
      --output worker/workers/lib/models.py \
      --output-model-type pydantic_v2.BaseModel \
      --use-schema-description \
      --extra-fields-config extra=forbid 2>/dev/null || \
    datamodel-codegen \
      --input-file-type postgres \
      --url "$SUPABASE_DEV_DB_URL" \
      --output worker/workers/lib/models.py \
      --output-model-type pydantic_v2.BaseModel \
      --use-schema-description

    echo "==> Diff check"
    git diff --exit-code -- web/db/schema.ts worker/workers/lib/models.py
    echo "OK: no drift"
    ```

    Create `scripts/eval-ci.sh` (executable bash):
    ```bash
    #!/usr/bin/env bash
    # Runs the v1.0 eval gold set and fails if accuracy regresses below baseline or n_examples < 20.
    # Consumed by .github/workflows/eval-ci.yml (Wave 5).
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
    assert n >= 20, f"gold set too small: {n} < 20 (Pitfall P8 defense)"
    if "$DRY_RUN_FLAG" == "--dry-run":
        print(f"dry-run OK: n_examples={n}")
        sys.exit(0)
    try:
        b = json.load(open("$BASELINE"))
    except FileNotFoundError:
        print("WARN: baseline.json not found; recording current run as baseline candidate")
        sys.exit(0)
    delta = r["accuracy"] - b["accuracy"]
    assert delta >= -0.01, f"eval regression: {r['accuracy']:.3f} < baseline {b['accuracy']:.3f} - 0.01"
    print(f"OK: accuracy={r['accuracy']:.3f} (baseline {b['accuracy']:.3f}, delta {delta:+.3f}, n={n})")
    PY
    ```

    Create `scripts/phase0-demo.sh` (executable bash) — exercises D-00-11 items 1, 4, 5:
    ```bash
    #!/usr/bin/env bash
    # Phase 0 exit demo — exercises D-00-11 items 1 (auth), 4 (immutability), 5 (heartbeat).
    # Items 2 (drift PR) and 3 (eval PR) are PR-based; item 6 (Resend ticket) is org-side.
    set -euo pipefail

    if [ -z "${SUPABASE_DEV_DB_URL:-}" ]; then
      echo "ERROR: SUPABASE_DEV_DB_URL required" >&2; exit 2
    fi

    echo "=== D-00-11 item 4: verifications append-only ==="
    psql "$SUPABASE_DEV_DB_URL" <<'SQL'
    do $$
    begin
      begin
        update verifications set status='active' where id is not null;
        raise exception 'EXPECTED FAILURE — UPDATE should have raised P0001';
      exception when others then
        if SQLSTATE = 'P0001' then
          raise notice 'OK: UPDATE raised P0001 as expected';
        else
          raise;
        end if;
      end;
    end$$;
    SQL

    echo "=== D-00-11 item 5: worker_heartbeats row within 60s ==="
    psql "$SUPABASE_DEV_DB_URL" -tAc \
      "select count(*) from worker_heartbeats where last_seen_at > now() - interval '60 seconds'" \
      | awk '{ if ($1 < 1) { print "FAIL: no recent heartbeat"; exit 1 } else print "OK: " $1 " recent heartbeat row(s)" }'

    echo "=== D-00-11 item 1: middleware allowlist (manual) ==="
    echo "  → Visit /sign-in in browser, attempt @gmail.com login; expect 403 message."
    echo "  → Then attempt @syr.edu magic link; expect /me page with email + role."
    echo "  (Recorded as evidence in .planning/phases/00-foundation/00-EVIDENCE.md)"

    echo "=== Phase 0 demo: automated checks passed ==="
    ```

    Create `Makefile` at repo root:
    ```makefile
    .PHONY: test test-quick test-worker test-web drift eval demo install

    install:
    	cd worker && python -m venv .venv && . .venv/bin/activate && pip install -e .[dev] && pip install -e ../business_checker
    	cd web && pnpm install

    test-worker:
    	cd worker && pytest -x

    test-web:
    	cd web && pnpm test --run

    test-quick: test-worker test-web

    test: test-worker test-web
    	@echo "Full suite green"

    drift:
    	bash scripts/check-drift.sh

    eval:
    	bash scripts/eval-ci.sh

    demo:
    	bash scripts/phase0-demo.sh
    ```

    Make all three scripts executable:
    ```bash
    chmod +x scripts/check-drift.sh scripts/eval-ci.sh scripts/phase0-demo.sh
    ```
  </action>
  <verify>
    <automated>test -x scripts/check-drift.sh && test -x scripts/eval-ci.sh && test -x scripts/phase0-demo.sh && grep -q "drizzle-kit pull" scripts/check-drift.sh && grep -q "n_examples" scripts/eval-ci.sh && grep -q "worker_heartbeats" scripts/phase0-demo.sh && grep -q "^test:" Makefile && grep -q "^drift:" Makefile && bash -n scripts/check-drift.sh && bash -n scripts/eval-ci.sh && bash -n scripts/phase0-demo.sh</automated>
  </verify>
  <acceptance_criteria>
    - `scripts/check-drift.sh` exists, is executable (`test -x`), passes `bash -n` syntax check
    - `scripts/check-drift.sh` contains `drizzle-kit pull`, `datamodel-codegen`, `git diff --exit-code`, AND the D-00-03 hard guard rejecting non-empty `web/drizzle/migrations/`
    - `scripts/eval-ci.sh` exists, executable, contains `n_examples`, `>= 20`, baseline comparison logic, and a `--dry-run` fallback path
    - `scripts/phase0-demo.sh` exists, executable, contains `worker_heartbeats`, `P0001`, and references items 1/4/5
    - `Makefile` exists at repo root with targets: `test`, `test-quick`, `test-worker`, `test-web`, `drift`, `eval`, `demo`, `install`
    - `make -n test` succeeds (dry-run no-op)
    - `grep -q "RAILWAY\\|VERCEL\\|GITHUB_TOKEN" scripts/*.sh` returns nothing (no secret leakage in script bodies)
  </acceptance_criteria>
  <done>All 3 scripts and the Makefile committed; subsequent waves' CI workflows just call these scripts; local `make test-quick` runs both test suites; phase exit demo has a single-command entrypoint.</done>
</task>

</tasks>

<verification>
- All 16 Wave 0 files from VALIDATION.md §Wave 0 Requirements exist.
- `pytest worker/tests --collect-only` finds ≥ 18 tests, all marked xfail.
- `bash -n` passes on all three scripts.
- No frontmatter requirement IDs (intentional — this is pure scaffolding).
- `make test-quick` runs without crashing (all tests xfail-pass).
</verification>

<success_criteria>
1. `pytest worker/tests --collect-only -q` succeeds and reports tests across 14 files.
2. `cd web && pnpm install` would succeed against the package.json (verified by JSON schema only — actual install happens in Wave 3).
3. Every test file referenced in any other Phase 0 plan's `<automated>` field exists on disk.
4. `bash scripts/phase0-demo.sh` would only fail on the database-dependent steps (which require Wave 1 + Wave 4 to ship) — the script itself has no syntax errors.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-01-wave0-test-scaffolding-SUMMARY.md` documenting:
- All 16 stub files created and their xfail markers
- Makefile targets and how subsequent waves invoke them
- Why no requirements field — this plan is pure scaffolding referenced by every other plan's verify step
</output>
