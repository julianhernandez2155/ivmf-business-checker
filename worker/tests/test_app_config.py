"""AUTH-02 + D-00-10: app_config seed rows + auth.is_allowed_domain() function."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_email_domain_allowlist_seeded(conn):
    with conn.cursor() as cur:
        cur.execute(
            "select value from public.app_config where key='email_domain_allowlist'"
        )
        row = cur.fetchone()
    assert row is not None
    assert "syr.edu" in row[0]


def test_column_allowlist_seeded(conn):
    with conn.cursor() as cur:
        cur.execute(
            "select value from public.app_config where key='column_allowlist'"
        )
        row = cur.fetchone()
    assert row is not None
    # >5 entries — defends against accidental truncation of the allowlist seed.
    assert len(row[0]) > 5


def test_is_allowed_domain_function(conn):
    with conn.cursor() as cur:
        cur.execute("select auth.is_allowed_domain('alice@syr.edu')")
        assert cur.fetchone()[0] is True
        cur.execute("select auth.is_allowed_domain('alice@gmail.com')")
        assert cur.fetchone()[0] is False
