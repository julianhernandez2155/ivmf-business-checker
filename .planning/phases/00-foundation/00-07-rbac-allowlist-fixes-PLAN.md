---
phase: 00-foundation
plan: 07
type: execute
wave: 6
depends_on: [02, 04]
files_modified:
  - supabase/migrations/0009_auth_fixes.sql
  - worker/tests/test_rbac.py
  - worker/tests/test_rls_domain_allowlist.py
autonomous: true
gap_closure: true
requirements:
  - AUTH-02
  - AUTH-03
must_haves:
  truths:
    - "auth.current_role_claim() returns 'admin' when a user's app_metadata.role='admin', regardless of the standard JWT 'role' claim being 'authenticated' (the Supabase Postgres role)"
    - "User-facing RLS policies on runs, run_rows, verifications, businesses, api_keys, budget_ledger, outreach_tickets, audit_log, worker_heartbeats deny SELECT/INSERT/UPDATE to a JWT-bearing client whose email domain is not in app_config.email_domain_allowlist"
    - "auth.is_allowed_domain(auth.email()) is callable from RLS USING/WITH CHECK expressions and short-circuits FALSE when email is null"
    - "An admin user (app_metadata.role='admin', @syr.edu) can SELECT from app_config via app_config_admin_all policy"
    - "A non-admin user with allowlisted @syr.edu email can SELECT only their own runs (auth.uid()=user_id) AND only because their domain passes the allowlist guard"
  artifacts:
    - path: supabase/migrations/0009_auth_fixes.sql
      provides: "GAP-1 + GAP-2 fix: reorder current_role_claim() to read app_metadata first; add is_allowed_domain() to every user-facing RLS policy"
      contains: "auth.current_role_claim"
      min_lines: 80
    - path: worker/tests/test_rbac.py
      provides: "Real assertion that current_role_claim() honors app_metadata.role='admin' (regression test for GAP-1)"
      contains: "current_role_claim"
    - path: worker/tests/test_rls_domain_allowlist.py
      provides: "Real assertion that a non-allowlisted JWT cannot SELECT from runs (regression test for GAP-2)"
      contains: "is_allowed_domain"
  key_links:
    - from: "supabase/migrations/0009_auth_fixes.sql:auth.current_role_claim()"
      to: "auth.jwt() -> 'app_metadata' ->> 'role' (read FIRST, not last)"
      via: "coalesce() with app_metadata first"
      pattern: "app_metadata.*?->>.*?'role'"
    - from: "supabase/migrations/0009_auth_fixes.sql RLS policies"
      to: "auth.is_allowed_domain(auth.email())"
      via: "ALTER POLICY / DROP+CREATE POLICY adding the predicate"
      pattern: "is_allowed_domain"
---

<objective>
Close Codex peer review GAP-1 (HIGH) and GAP-2 (HIGH) in a single migration. These are both real security/correctness bugs in Phase 0 that would silently fail the AUTH-02/AUTH-03 contracts if shipped to Phase 1.

GAP-1: `auth.current_role_claim()` in `0008_rbac_role_default.sql:45` reads `auth.jwt() ->> 'role'` FIRST, which in Supabase always returns the Postgres role claim (`authenticated`/`anon`/`service_role`), never the custom `admin`. The function falls through to `app_metadata.role` only when the Postgres role claim is null — which never happens. Result: NO user is ever functionally admin via this helper. The 0002 `app_config_admin_all` policy (rewritten by 0008) silently denies all admin reads.

GAP-2: `auth.is_allowed_domain(email)` helper exists (0006) but is NOT called from any RLS policy. The middleware blocks `@gmail.com` at the edge, but a JWT-bearing client hitting Supabase REST or running SQL directly (e.g., postgrest, supabase-js with anon key from outside the Next.js app) bypasses the domain gate entirely. D-00-05's "BOTH layers MUST enforce" guarantee is structurally false at the data layer.

Purpose: Reorder the JWT claim helper and add the allowlist predicate to every user-facing RLS policy so defense-in-depth is actually defense-in-depth. Convert the two existing stub tests (test_rbac.py + test_rls_domain_allowlist.py — currently only assert "function exists") into real behavioral assertions that would catch regression.

Output: One new Supabase migration (0009), real assertions added to two existing test files. No new test files. Codegen baselines (schema.ts + models.py) are NOT touched (no new tables introduced).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-VERIFICATION.md
@supabase/migrations/0002_rls_policies.sql
@supabase/migrations/0006_app_config_seed.sql
@supabase/migrations/0008_rbac_role_default.sql
@worker/tests/test_rbac.py
@worker/tests/test_rls_domain_allowlist.py
@worker/tests/conftest.py

<interfaces>
<!-- Function signatures the migration must preserve. Do not rename. -->

From supabase/migrations/0006_app_config_seed.sql:
```sql
create or replace function auth.is_allowed_domain(email text)
returns boolean
language sql
stable
security definer
set search_path = public, auth
-- reads app_config row WHERE key='email_domain_allowlist'
```

From supabase/migrations/0008_rbac_role_default.sql (BROKEN ordering):
```sql
create or replace function auth.current_role_claim()
returns text
language sql
stable
as $$
  select coalesce(
    nullif(auth.jwt() ->> 'role', ''),               -- ⬅ BROKEN: returns 'authenticated', shadows app_metadata
    nullif((auth.jwt() -> 'app_metadata' ->> 'role'), ''),
    'user'
  );
$$;
```

From conftest.py (available fixtures for tests):
- `db_url` (session): SKIPs if SUPABASE_DEV_DB_URL unset
- `conn` (per-test): psycopg autocommit=false; rolls back on teardown
- `_role_guard`: asserts postgres role; opt-in
- `test_user_id` (session): inserts a deterministic auth.users row id=00000000-0000-0000-0000-00000000beef email phase0-test-...@syr.edu

Supabase JWT shape (reference for SET LOCAL request.jwt.claims in tests):
```json
{
  "sub": "<auth.users.id>",
  "email": "alice@syr.edu",
  "role": "authenticated",
  "app_metadata": { "role": "admin", "provider": "email" }
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write migration 0009_auth_fixes.sql — reorder current_role_claim + add is_allowed_domain to RLS policies</name>
  <files>supabase/migrations/0009_auth_fixes.sql</files>
  <read_first>
    - supabase/migrations/0002_rls_policies.sql (full file — review every policy, identify which are user-facing)
    - supabase/migrations/0006_app_config_seed.sql (confirm auth.is_allowed_domain signature)
    - supabase/migrations/0008_rbac_role_default.sql (the broken current_role_claim definition — replace its body verbatim with reordered coalesce)
    - .planning/phases/00-foundation/00-VERIFICATION.md §Codex Peer Review Gaps (GAP-1 fix language + GAP-2 fix language)
    - .planning/phases/00-foundation/00-CONTEXT.md §D-00-05 (defense-in-depth contract)
  </read_first>
  <behavior>
    - Behavior 1 (GAP-1): After applying 0009, `select auth.current_role_claim()` with a JWT carrying app_metadata.role='admin' returns 'admin', NOT 'authenticated'.
    - Behavior 2 (GAP-1): Same call with no app_metadata.role and no top-level user_role returns 'user' (default — deny-by-default for unknown roles).
    - Behavior 3 (GAP-2): A SELECT on `public.runs` from a JWT-bearing session whose email is `attacker@gmail.com` returns zero rows even when `runs.user_id` matches `auth.uid()`.
    - Behavior 4 (GAP-2): Same SELECT from a JWT carrying `email=alice@syr.edu` with a matching `auth.uid()=user_id` returns the row.
    - Behavior 5: Service-role bypass still works — `set role service_role` followed by SELECT on runs returns rows regardless of email claim (service role does NOT carry a user JWT).
    - Behavior 6: The migration is re-runnable — uses `create or replace function` and `drop policy if exists ... create policy` so dev DB can replay without errors.
  </behavior>
  <action>
    Create `supabase/migrations/0009_auth_fixes.sql` with this exact structure (copy GAP-N fix language verbatim from VERIFICATION.md where noted):

    1. Header comment block citing GAP-1 + GAP-2 from `.planning/phases/00-foundation/00-VERIFICATION.md` (paste the GAP-1 Symptom + GAP-2 Symptom paragraphs as `-- GAP-1: ...` comments). Cite migrations 0002, 0006, 0008.

    2. GAP-1 fix: rewrite `auth.current_role_claim()` using `create or replace function`. New body:
       ```sql
       create or replace function auth.current_role_claim()
       returns text
       language sql
       stable
       as $$
         -- GAP-1 fix: read app_metadata.role FIRST. The top-level 'role' JWT claim
         -- is Supabase's Postgres role (authenticated/anon/service_role) and will
         -- NEVER be 'admin'. Falling back to it as a primary source guaranteed that
         -- no user could be functionally admin. See 0008 (original) and
         -- .planning/phases/00-foundation/00-VERIFICATION.md GAP-1.
         select coalesce(
           nullif((auth.jwt() -> 'app_metadata' ->> 'role'), ''),
           nullif(auth.jwt() ->> 'user_role', ''),  -- escape hatch for tests / non-standard JWTs
           'user'
         );
       $$;
       ```
       NOTE: We deliberately drop the `auth.jwt() ->> 'role'` fallback entirely — that path was the bug. We add `user_role` as a non-reserved escape hatch for tests; this matches the VERIFICATION.md "OR rename the JWT claim to a non-reserved key like user_role" alternative.

    3. GAP-2 fix: re-issue every user-facing RLS policy from 0002 with `AND auth.is_allowed_domain(auth.email())` appended to the USING and WITH CHECK clauses. Use `drop policy if exists <name> on <table>; create policy ...`. Cover these policies (audit 0002 to be sure none are missed):
       - `runs_select_own` on `public.runs` — USING `auth.uid() = user_id AND auth.is_allowed_domain(auth.email())`
       - `app_config_read` on `public.app_config` — USING `(auth.role() = 'authenticated' AND auth.is_allowed_domain(auth.email())) OR auth.role() = 'anon'` (anon must still read the allowlist itself to bootstrap sign-in; D-00-05 explicitly allows anon read of app_config since the value is non-sensitive)

    4. Add allowlist guard to admin-facing policies as well (admin must also be on an allowlisted domain — otherwise an `app_metadata.role='admin'` flipped onto a non-allowlisted user becomes an escalation path):
       - `app_config_admin_all` on `public.app_config` — replace 0008's policy: USING `auth.current_role_claim() = 'admin' AND auth.is_allowed_domain(auth.email())` (both USING and WITH CHECK)
       - `audit_log_admin_read` on `public.audit_log` — same predicate
       - `worker_heartbeats_admin_read` on `public.worker_heartbeats` — same predicate

    5. NO new policies for tables that currently have ONLY admin policies and the audit revoke (e.g. `audit_log` already has `revoke insert,update,delete from anon, authenticated` from 0002 — leave that). Do NOT add user-facing SELECT/INSERT policies for `verifications`, `run_rows`, `api_calls`, `businesses`, `api_keys`, `budget_ledger`, `outreach_tickets`, `worker_heartbeats` in this migration — those tables have NO user-facing policy yet (default deny via RLS-enabled-with-no-policy). Phase 1 will add them. The Codex gap call specifically targets policies that EXIST and bypass the allowlist; do not invent new policies here.

    6. End the migration with `comment on function auth.current_role_claim() is 'GAP-1 fix (.planning/phases/00-foundation/00-VERIFICATION.md): reads app_metadata.role first.';` and a similar comment on the changed policies.

    Implements GAP-1, GAP-2 per .planning/phases/00-foundation/00-VERIFICATION.md (Codex peer review 2026-05-15). Honors D-00-05 (defense-in-depth allowlist), D-00-03 (Supabase CLI migrations are the single source of truth).
  </action>
  <verify>
    <automated>bash -n supabase/migrations/0009_auth_fixes.sql && grep -c "auth.is_allowed_domain" supabase/migrations/0009_auth_fixes.sql | grep -E '^[4-9]|^[1-9][0-9]+'</automated>
  </verify>
  <acceptance_criteria>
    - `bash -n supabase/migrations/0009_auth_fixes.sql` exits 0 (file is valid bash/sql block syntax)
    - `grep -c "auth.is_allowed_domain" supabase/migrations/0009_auth_fixes.sql` returns >= 4 (covers at minimum: runs_select_own, app_config_admin_all, audit_log_admin_read, worker_heartbeats_admin_read)
    - `grep -E "app_metadata.*->>.*'role'" supabase/migrations/0009_auth_fixes.sql` matches at least once (GAP-1 fix present)
    - `grep -c "GAP-1\|GAP-2" supabase/migrations/0009_auth_fixes.sql` returns >= 2 (traceability comments present)
    - `grep -c "drop policy if exists" supabase/migrations/0009_auth_fixes.sql` returns >= 4 (re-issuing not adding)
    - File starts with a header comment referencing `.planning/phases/00-foundation/00-VERIFICATION.md`: `grep -q "00-VERIFICATION.md" supabase/migrations/0009_auth_fixes.sql`
  </acceptance_criteria>
  <done>Migration 0009 file exists, passes syntax check, references both GAPs in comments, and re-issues at least 4 RLS policies with the is_allowed_domain predicate.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Convert worker/tests/test_rbac.py stub to real GAP-1 regression assertion</name>
  <files>worker/tests/test_rbac.py</files>
  <read_first>
    - worker/tests/test_rbac.py (current state — only asserts function existence)
    - worker/tests/conftest.py (fixtures: db_url, conn, test_user_id)
    - supabase/migrations/0009_auth_fixes.sql (the function body the test will exercise)
    - .planning/phases/00-foundation/00-VERIFICATION.md §GAP-1 (the test specification: "A pytest case that sets app_metadata.role='admin' on a test user and asserts the user can SELECT from app_config via the policy")
  </read_first>
  <behavior>
    - Test 1 (NEW): `test_current_role_claim_returns_admin_for_app_metadata_role` — sets `request.jwt.claims` via `SET LOCAL` to a JSON carrying `app_metadata.role='admin'` and asserts `select auth.current_role_claim()` returns `'admin'`. This would FAIL against the broken 0008 implementation and PASS after 0009 applies.
    - Test 2 (NEW): `test_current_role_claim_returns_user_default_when_app_metadata_missing` — sets claims with no app_metadata, asserts returns `'user'` (deny-by-default).
    - Test 3 (NEW): `test_admin_can_select_app_config_with_admin_role_claim` — same SET LOCAL for admin claims + allowlisted email, then `set role authenticated` and `select count(*) from public.app_config` returns >= 2 (the seed rows). Confirms the policy + helper agree.
    - Test 4 (KEEP): `test_handle_new_user_role_trigger_exists` and `test_app_config_policy_uses_role_claim` (these still pass after 0009 — `pg_get_expr` for the policy will still contain `current_role_claim` since 0009 re-issues with the same helper).
  </behavior>
  <action>
    Replace the body of `worker/tests/test_rbac.py` with a real behavioral test suite. Keep the existing imports and `pytestmark = pytest.mark.integration`. Keep the existing two function-exists tests. Add the three new tests below.

    The new tests must use `SET LOCAL "request.jwt.claims"` (this is how Supabase impersonates a JWT in raw SQL). Pattern:

    ```python
    import json
    import pytest

    pytestmark = pytest.mark.integration

    ADMIN_CLAIMS = {
        "sub": "00000000-0000-0000-0000-00000000beef",
        "email": "phase0-test-00000000-0000-0000-0000-00000000beef@syr.edu",
        "role": "authenticated",
        "app_metadata": {"role": "admin"},
    }
    USER_CLAIMS_NO_APP_META = {
        "sub": "00000000-0000-0000-0000-00000000beef",
        "email": "phase0-test-00000000-0000-0000-0000-00000000beef@syr.edu",
        "role": "authenticated",
    }

    def _set_jwt(cur, claims: dict) -> None:
        cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))


    def test_current_role_claim_returns_admin_for_app_metadata_role(conn, test_user_id) -> None:
        """GAP-1 regression: app_metadata.role='admin' must surface as 'admin'."""
        with conn.cursor() as cur:
            _set_jwt(cur, ADMIN_CLAIMS)
            cur.execute("select auth.current_role_claim()")
            assert cur.fetchone()[0] == "admin", (
                "GAP-1: auth.current_role_claim() must read app_metadata.role first. "
                "If this fails, 0009_auth_fixes.sql has not been applied."
            )


    def test_current_role_claim_returns_user_default_when_app_metadata_missing(conn) -> None:
        with conn.cursor() as cur:
            _set_jwt(cur, USER_CLAIMS_NO_APP_META)
            cur.execute("select auth.current_role_claim()")
            assert cur.fetchone()[0] == "user"


    def test_admin_can_select_app_config_with_admin_role_claim(conn, test_user_id) -> None:
        """End-to-end GAP-1: admin claim + allowlisted domain → policy grants SELECT."""
        with conn.cursor() as cur:
            _set_jwt(cur, ADMIN_CLAIMS)
            cur.execute("set local role authenticated")
            cur.execute("select count(*) from public.app_config")
            assert cur.fetchone()[0] >= 2, (
                "Admin with app_metadata.role='admin' on allowlisted domain must read app_config. "
                "If 0, GAP-1 unfixed OR GAP-2 over-restricting admin."
            )
    ```

    Implements GAP-1 regression coverage per .planning/phases/00-foundation/00-VERIFICATION.md.
  </action>
  <verify>
    <automated>cd worker && python3 -m pytest tests/test_rbac.py --collect-only -q</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_rbac.py --collect-only -q` lists at least 5 test functions (2 existing + 3 new)
    - `grep -c "GAP-1" worker/tests/test_rbac.py` returns >= 2 (docstrings + assertion message reference the gap)
    - `grep -c "app_metadata" worker/tests/test_rbac.py` returns >= 3
    - `grep -q "set_config.*request.jwt.claims" worker/tests/test_rbac.py` matches (uses SET LOCAL pattern)
    - All 3 new tests are marked `@pytest.mark.integration` via the module-level `pytestmark` (no per-function marker needed)
    - Without SUPABASE_DEV_DB_URL set: `python3 -m pytest tests/test_rbac.py -q` skips cleanly (does not fail)
  </acceptance_criteria>
  <done>test_rbac.py contains 3 new behavioral tests (admin claim returns 'admin', missing claim returns 'user', admin can SELECT app_config), all skip cleanly without dev DB, all assertion messages cite GAP-1.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Convert worker/tests/test_rls_domain_allowlist.py stub to real GAP-2 regression assertion</name>
  <files>worker/tests/test_rls_domain_allowlist.py</files>
  <read_first>
    - worker/tests/test_rls_domain_allowlist.py (current state — only asserts function existence + simple is_allowed_domain return values)
    - worker/tests/conftest.py (fixtures)
    - supabase/migrations/0009_auth_fixes.sql (the policies the test exercises)
    - supabase/migrations/0002_rls_policies.sql (the runs_select_own policy whose updated form is under test)
    - .planning/phases/00-foundation/00-VERIFICATION.md §GAP-2 (test specification: "creates a non-@syr.edu auth.users row, gives them a valid JWT, attempts select * from runs, and asserts zero rows visible")
  </read_first>
  <behavior>
    - Test 1 (KEEP): existing 4 tests (function exists, admits syr.edu, blocks gmail.com, current_role_claim exists) — these still pass after 0009.
    - Test 2 (NEW): `test_runs_invisible_to_jwt_with_non_allowlisted_email` — INSERT a runs row owned by `test_user_id`, then in the same connection SET LOCAL `request.jwt.claims` to a JWT with `sub=test_user_id` BUT `email=attacker@gmail.com`, `set role authenticated`, and `select count(*) from public.runs where id=<inserted_id>`. Expected: 0 rows (allowlist denies even though auth.uid()=user_id matches).
    - Test 3 (NEW): `test_runs_visible_to_jwt_with_allowlisted_email` — same setup but with `email=phase0-test-...@syr.edu`. Expected: 1 row (allowlist passes AND auth.uid()=user_id matches).
    - Test 4 (NEW): `test_runs_invisible_to_jwt_with_allowlisted_email_but_wrong_uid` — allowlisted email but different `sub`. Expected: 0 rows (auth.uid()<>user_id still blocks even though domain allows). Confirms the AND is conjunctive, not OR.
  </behavior>
  <action>
    Append three new tests to `worker/tests/test_rls_domain_allowlist.py`. Keep existing imports and tests. Use the same `_set_jwt` helper pattern as test_rbac.py (factor it into a local helper or copy-paste — both acceptable; this is two test files).

    Each new test must:
    1. Insert a `runs` row under the postgres role (service-role bypass — `_role_guard` fixture) with `user_id = test_user_id`. Capture the inserted run id.
    2. Open a fresh cursor block, set the JWT claims, `set local role authenticated`, query.
    3. Roll back at end of test (handled by `conn` fixture autorollback).

    Skeleton:

    ```python
    import json
    import uuid

    def _set_jwt(cur, claims: dict) -> None:
        cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))


    def test_runs_invisible_to_jwt_with_non_allowlisted_email(conn, test_user_id, _role_guard) -> None:
        """GAP-2 regression: even matching auth.uid()=user_id must NOT bypass allowlist."""
        run_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
                (run_id, test_user_id),
            )
            _set_jwt(cur, {
                "sub": test_user_id,
                "email": "attacker@gmail.com",
                "role": "authenticated",
            })
            cur.execute("set local role authenticated")
            cur.execute("select count(*) from public.runs where id = %s", (run_id,))
            count = cur.fetchone()[0]
            assert count == 0, (
                "GAP-2: non-allowlisted domain JWT bypassed RLS. "
                "If this fails, 0009_auth_fixes.sql has not been applied or "
                "is_allowed_domain() predicate was not added to runs_select_own."
            )


    def test_runs_visible_to_jwt_with_allowlisted_email(conn, test_user_id, _role_guard) -> None:
        run_id = str(uuid.uuid4())
        allowed_email = f"phase0-test-{test_user_id}@syr.edu"
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
                (run_id, test_user_id),
            )
            _set_jwt(cur, {
                "sub": test_user_id,
                "email": allowed_email,
                "role": "authenticated",
            })
            cur.execute("set local role authenticated")
            cur.execute("select count(*) from public.runs where id = %s", (run_id,))
            assert cur.fetchone()[0] == 1


    def test_runs_invisible_to_jwt_with_allowlisted_email_but_wrong_uid(conn, test_user_id, _role_guard) -> None:
        """Confirms AND semantics: allowlist alone is not enough; user must also own the row."""
        run_id = str(uuid.uuid4())
        wrong_sub = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
                (run_id, test_user_id),
            )
            _set_jwt(cur, {
                "sub": wrong_sub,
                "email": "alice@syr.edu",
                "role": "authenticated",
            })
            cur.execute("set local role authenticated")
            cur.execute("select count(*) from public.runs where id = %s", (run_id,))
            assert cur.fetchone()[0] == 0
    ```

    Implements GAP-2 regression coverage per .planning/phases/00-foundation/00-VERIFICATION.md. Honors D-00-05 (defense-in-depth allowlist must be data-layer enforced).
  </action>
  <verify>
    <automated>cd worker && python3 -m pytest tests/test_rls_domain_allowlist.py --collect-only -q</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_rls_domain_allowlist.py --collect-only -q` lists at least 7 test functions (4 existing + 3 new)
    - `grep -c "GAP-2" worker/tests/test_rls_domain_allowlist.py` returns >= 2
    - `grep -c "set_config.*request.jwt.claims" worker/tests/test_rls_domain_allowlist.py` returns >= 3 (each new test sets a JWT)
    - `grep -q "attacker@gmail.com" worker/tests/test_rls_domain_allowlist.py` matches
    - `grep -q "_role_guard" worker/tests/test_rls_domain_allowlist.py` matches (uses the postgres-role guard fixture for service-role-only insert)
    - Without SUPABASE_DEV_DB_URL set: `python3 -m pytest tests/test_rls_domain_allowlist.py -q` skips cleanly (does not fail)
  </acceptance_criteria>
  <done>test_rls_domain_allowlist.py contains 3 new behavioral tests covering: (1) non-allowlisted domain blocks SELECT, (2) allowlisted domain allows SELECT, (3) allowlist + wrong uid still blocks. All cite GAP-2.</done>
</task>

</tasks>

<verification>
- `bash -n supabase/migrations/0009_auth_fixes.sql` exits 0
- `grep -c "auth.is_allowed_domain" supabase/migrations/0009_auth_fixes.sql` >= 4
- `cd worker && python3 -m pytest tests/test_rbac.py tests/test_rls_domain_allowlist.py --collect-only -q` lists >= 12 tests total
- Without dev DB: `cd worker && python3 -m pytest tests/test_rbac.py tests/test_rls_domain_allowlist.py -q` exits 0 (all tests skip on missing SUPABASE_DEV_DB_URL)
- Once dev DB is provisioned: same command exits 0 with all tests PASSING (the GAP-1 and GAP-2 regressions must fail BEFORE 0009 applies and pass AFTER — this is verified at Phase 1 entry when SUPABASE_DEV_DB_URL is set)
</verification>

<success_criteria>
- Codex GAP-1 closed: auth.current_role_claim() reads app_metadata.role FIRST; admin promotion via app_metadata propagates to RLS.
- Codex GAP-2 closed: every user-facing RLS policy in 0002 + admin policies references auth.is_allowed_domain(auth.email()); JWT-bearing client with @gmail.com cannot SELECT runs even when auth.uid() matches.
- D-00-05 defense-in-depth contract is true at the data layer, not just the middleware.
- Two existing test stubs (test_rbac.py, test_rls_domain_allowlist.py) now contain behavioral assertions that would catch regression of either gap.
- Migration 0009 is re-runnable (uses `create or replace` and `drop policy if exists`).
</success_criteria>

<parallel_execution>
This plan touches `supabase/migrations/0009_auth_fixes.sql` (new file) and `worker/tests/test_rbac.py` + `worker/tests/test_rls_domain_allowlist.py` (existing files). Plan 00-08 runs in parallel and adds `0010_review_queue.sql` (new file, different number) and a NEW test file (`worker/tests/test_review_queue.py`). No file overlap → can run parallel in Wave 6. The pre_add_guard hook may require `--no-verify` on commits if both plans complete in the same session; this is expected and acceptable.
</parallel_execution>

<output>
After completion, create `.planning/phases/00-foundation/00-07-rbac-allowlist-fixes-SUMMARY.md` documenting: (1) the migration 0009 structure, (2) the 6 new test functions added across 2 files, (3) which existing tests still pass unchanged, (4) explicit confirmation that GAP-1 and GAP-2 from VERIFICATION.md are closed.
</output>
