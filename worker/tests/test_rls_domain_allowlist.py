"""Phase 00 Plan 04 + Plan 07 — AUTH-02/03 RLS allowlist + role helper assertions.

Plan 04 (original) exercises both Postgres functions used as defense layer 2 of
the email domain allowlist:

  - auth.is_allowed_domain(email)   — created in 0006_app_config_seed.sql
  - auth.current_role_claim()       — created in 0008_rbac_role_default.sql

Plan 07 (GAP-2 closure, Codex peer review 2026-05-15) adds three behavioral
regression tests that confirm the allowlist predicate is now enforced inside
RLS policies — not just at the middleware layer (D-00-05 defense-in-depth):

  - test_runs_invisible_to_jwt_with_non_allowlisted_email
  - test_runs_visible_to_jwt_with_allowlisted_email
  - test_runs_invisible_to_jwt_with_allowlisted_email_but_wrong_uid

See .planning/phases/00-foundation/00-VERIFICATION.md §GAP-2.

Tests skip cleanly when SUPABASE_DEV_DB_URL is unset (via conftest db_url
fixture); the dev project is not yet provisioned per STATE.md.
"""
from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.integration


def _set_jwt(cur, claims: dict) -> None:
    """Impersonate a Supabase JWT in raw SQL via SET LOCAL request.jwt.claims."""
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps(claims),),
    )


# ----- Plan 04 structural tests (unchanged) -----------------------------

def test_is_allowed_domain_function_exists(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1
            from pg_proc
            where proname = 'is_allowed_domain'
              and pronamespace = 'auth'::regnamespace
            """
        )
        assert cur.fetchone() is not None, "auth.is_allowed_domain missing"


def test_is_allowed_domain_admits_syr_edu(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("select auth.is_allowed_domain(%s)", ("alice@syr.edu",))
        assert cur.fetchone()[0] is True


def test_is_allowed_domain_blocks_gmail(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("select auth.is_allowed_domain(%s)", ("alice@gmail.com",))
        assert cur.fetchone()[0] is False


def test_current_role_claim_function_exists(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1
            from pg_proc
            where proname = 'current_role_claim'
              and pronamespace = 'auth'::regnamespace
            """
        )
        assert cur.fetchone() is not None, (
            "auth.current_role_claim missing — apply 0008_rbac_role_default.sql"
        )


# ----- Plan 07 GAP-2 regression tests ------------------------------------

def test_runs_invisible_to_jwt_with_non_allowlisted_email(
    conn, test_user_id, _role_guard
) -> None:
    """GAP-2 regression: even matching auth.uid()=user_id must NOT bypass allowlist.

    The original runs_select_own policy was `auth.uid() = user_id` only — a
    JWT-bearing client with a non-allowlisted domain could SELECT their own
    runs via Supabase REST, bypassing the middleware-only domain gate. After
    0009_auth_fixes.sql the policy gains AND auth.is_allowed_domain(auth.email());
    this test pins that conjunction.
    """
    run_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
            (run_id, test_user_id),
        )
        _set_jwt(
            cur,
            {
                "sub": test_user_id,
                "email": "attacker@gmail.com",
                "role": "authenticated",
            },
        )
        cur.execute("set local role authenticated")
        cur.execute("select count(*) from public.runs where id = %s", (run_id,))
        count = cur.fetchone()[0]
        assert count == 0, (
            "GAP-2: non-allowlisted domain JWT bypassed RLS. "
            "If this fails, 0009_auth_fixes.sql has not been applied or "
            "is_allowed_domain() predicate was not added to runs_select_own."
        )


def test_runs_visible_to_jwt_with_allowlisted_email(
    conn, test_user_id, _role_guard
) -> None:
    """Positive case: allowlisted domain + matching auth.uid() → row is visible."""
    run_id = str(uuid.uuid4())
    allowed_email = f"phase0-test-{test_user_id}@syr.edu"
    with conn.cursor() as cur:
        cur.execute(
            "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
            (run_id, test_user_id),
        )
        _set_jwt(
            cur,
            {
                "sub": test_user_id,
                "email": allowed_email,
                "role": "authenticated",
            },
        )
        cur.execute("set local role authenticated")
        cur.execute("select count(*) from public.runs where id = %s", (run_id,))
        assert cur.fetchone()[0] == 1


def test_runs_invisible_to_jwt_with_allowlisted_email_but_wrong_uid(
    conn, test_user_id, _role_guard
) -> None:
    """Confirms AND semantics: allowlist alone is not enough; user must also own the row.

    A different `sub` claim breaks the auth.uid()=user_id half of runs_select_own
    even though the @syr.edu email passes the allowlist half. This proves the
    predicates are conjunctive (not OR'd).
    """
    run_id = str(uuid.uuid4())
    wrong_sub = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
            (run_id, test_user_id),
        )
        _set_jwt(
            cur,
            {
                "sub": wrong_sub,
                "email": "alice@syr.edu",
                "role": "authenticated",
            },
        )
        cur.execute("set local role authenticated")
        cur.execute("select count(*) from public.runs where id = %s", (run_id,))
        assert cur.fetchone()[0] == 0
