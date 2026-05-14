"""Phase 00 Plan 04 — AUTH-02/03 RLS allowlist + role helper assertions.

Exercises both Postgres functions used as defense layer 2 of the email domain
allowlist:

  - auth.is_allowed_domain(email)   — created in 0006_app_config_seed.sql
  - auth.current_role_claim()       — created in 0008_rbac_role_default.sql

Tests skip cleanly when SUPABASE_DEV_DB_URL is unset (via conftest db_url
fixture); the dev project is not yet provisioned per STATE.md.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


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
