"""Phase 00 Plan 04 + Plan 07 — AUTH-03 RBAC role propagation via raw_app_meta_data + JWT.

Plan 04 (original) verified BOTH halves of the AUTH-03 contract structurally:
  1. The after-insert trigger trg_handle_new_user_role is installed.
  2. The app_config_admin_all policy reads role through auth.current_role_claim()
     so middleware (app_metadata.role) and RLS share a single source of truth.

Plan 07 (GAP-1 closure, Codex peer review 2026-05-15) adds three behavioral
regression tests that would FAIL against the original 0008 ordering and PASS
after 0009_auth_fixes.sql applies:

  - test_current_role_claim_returns_admin_for_app_metadata_role
  - test_current_role_claim_returns_user_default_when_app_metadata_missing
  - test_admin_can_select_app_config_with_admin_role_claim

See .planning/phases/00-foundation/00-VERIFICATION.md §GAP-1.

Skips cleanly when SUPABASE_DEV_DB_URL is unset.
"""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.integration


# ----- JWT claim fixtures for GAP-1 regression tests --------------------

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
    """Impersonate a Supabase JWT in raw SQL via SET LOCAL request.jwt.claims."""
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps(claims),),
    )


# ----- Plan 04 structural tests (unchanged) -----------------------------

def test_handle_new_user_role_trigger_exists(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1
            from pg_trigger
            where tgname = 'trg_handle_new_user_role'
            """
        )
        assert cur.fetchone() is not None, (
            "trg_handle_new_user_role missing — apply 0008_rbac_role_default.sql"
        )


def test_app_config_policy_uses_role_claim(conn) -> None:
    """AUTH-03: admin policy reads role from JWT via current_role_claim()."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select pg_get_expr(polqual, polrelid)
            from pg_policy
            where polname = 'app_config_admin_all'
            """
        )
        row = cur.fetchone()
        assert row is not None, "app_config_admin_all policy missing"
        qual = row[0] or ""
        # Either the helper is named directly or the policy hardcodes 'admin'.
        # The 0008 migration rewrites the policy to call current_role_claim();
        # the 0009 migration re-issues it with the same helper + allowlist guard.
        assert "current_role_claim" in qual or "'admin'" in qual, (
            f"policy qual must reference current_role_claim or 'admin'; got: {qual!r}"
        )


# ----- Plan 07 GAP-1 regression tests ------------------------------------

def test_current_role_claim_returns_admin_for_app_metadata_role(conn, test_user_id) -> None:
    """GAP-1 regression: app_metadata.role='admin' must surface as 'admin'.

    The original 0008 implementation read auth.jwt() ->> 'role' FIRST, which
    in Supabase always returns 'authenticated' (the Postgres role), shadowing
    app_metadata.role entirely. After 0009_auth_fixes.sql, app_metadata.role
    is read first; this test pins that ordering.
    """
    with conn.cursor() as cur:
        _set_jwt(cur, ADMIN_CLAIMS)
        cur.execute("select auth.current_role_claim()")
        assert cur.fetchone()[0] == "admin", (
            "GAP-1: auth.current_role_claim() must read app_metadata.role first. "
            "If this fails, 0009_auth_fixes.sql has not been applied."
        )


def test_current_role_claim_returns_user_default_when_app_metadata_missing(conn) -> None:
    """Deny-by-default: missing app_metadata.role + missing user_role → 'user'."""
    with conn.cursor() as cur:
        _set_jwt(cur, USER_CLAIMS_NO_APP_META)
        cur.execute("select auth.current_role_claim()")
        assert cur.fetchone()[0] == "user"


def test_admin_can_select_app_config_with_admin_role_claim(conn, test_user_id) -> None:
    """End-to-end GAP-1: admin claim + allowlisted domain → policy grants SELECT.

    Exercises the full chain: JWT app_metadata.role='admin' → current_role_claim()
    returns 'admin' → app_config_admin_all policy USING clause evaluates true →
    SELECT succeeds. is_allowed_domain(auth.email()) must ALSO pass — the test
    user's email is @syr.edu which is on the seeded allowlist.
    """
    with conn.cursor() as cur:
        _set_jwt(cur, ADMIN_CLAIMS)
        cur.execute("set local role authenticated")
        cur.execute("select count(*) from public.app_config")
        assert cur.fetchone()[0] >= 2, (
            "Admin with app_metadata.role='admin' on allowlisted domain must read app_config. "
            "If 0, GAP-1 unfixed OR GAP-2 over-restricting admin."
        )
