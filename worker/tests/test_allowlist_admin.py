"""Phase 00 Plan 04 — AUTH-02 admin extends allowlist via app_config UPDATE.

Proves that auth.is_allowed_domain() reads the LIVE app_config row (not a
hardcoded list): updating the row admits a new domain immediately, while
non-allowlisted domains remain blocked. Original value is restored in a
finally block so the test is rerunnable.

Skips cleanly when SUPABASE_DEV_DB_URL is unset.
"""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.integration


def test_allowlist_extend_admits_new_domain(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "select value from public.app_config where key = 'email_domain_allowlist'"
        )
        row = cur.fetchone()
        assert row is not None, "email_domain_allowlist seed row missing (0006)"
        original = row[0]

        try:
            cur.execute(
                """
                update public.app_config
                set value = '["syr.edu", "example.com"]'::jsonb,
                    updated_at = now()
                where key = 'email_domain_allowlist'
                """
            )
            conn.commit()

            # AUTH-02 round-trip: new domain admitted after row UPDATE alone.
            cur.execute("select auth.is_allowed_domain(%s)", ("a@example.com",))
            assert cur.fetchone()[0] is True

            # Original domain still admitted.
            cur.execute("select auth.is_allowed_domain(%s)", ("a@syr.edu",))
            assert cur.fetchone()[0] is True

            # Domains NOT in the list remain blocked (proves the function reads
            # the table rather than a hardcoded list).
            cur.execute("select auth.is_allowed_domain(%s)", ("a@other.com",))
            assert cur.fetchone()[0] is False
        finally:
            cur.execute(
                "update public.app_config set value = %s::jsonb "
                "where key = 'email_domain_allowlist'",
                (json.dumps(original),),
            )
            conn.commit()
