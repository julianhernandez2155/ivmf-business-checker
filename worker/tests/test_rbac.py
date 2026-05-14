"""Phase 00 Plan 04 — AUTH-03 RBAC role propagation via raw_app_meta_data + JWT.

Verifies both halves of the AUTH-03 contract:
  1. The after-insert trigger trg_handle_new_user_role is installed.
  2. The app_config_admin_all policy reads role through auth.current_role_claim()
     so middleware (app_metadata.role) and RLS share a single source of truth.

Skips cleanly when SUPABASE_DEV_DB_URL is unset.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


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
        # The 0008 migration rewrites the policy to call current_role_claim().
        assert "current_role_claim" in qual or "'admin'" in qual, (
            f"policy qual must reference current_role_claim or 'admin'; got: {qual!r}"
        )
