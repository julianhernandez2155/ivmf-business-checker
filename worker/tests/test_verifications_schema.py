"""CANON-08: verifications has provenance jsonb, method text NOT NULL, match_signals jsonb.

Schema introspection — proves the column shape exists for Phase 1+ to write into.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

REQUIRED_COLUMNS = {
    "id",
    "business_id",
    "run_id",
    "row_index",
    "pass",
    "method",
    "status",
    "provenance",
    "match_signals",
}


def test_required_columns(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name from information_schema.columns
            where table_schema='public' and table_name='verifications'
            """
        )
        cols = {r[0] for r in cur.fetchall()}
    missing = REQUIRED_COLUMNS - cols
    assert not missing, f"verifications missing columns: {missing}"


def test_method_is_not_null(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select is_nullable from information_schema.columns
            where table_schema='public' and table_name='verifications'
              and column_name='method'
            """
        )
        is_nullable = cur.fetchone()[0]
    assert is_nullable == "NO", f"verifications.method must be NOT NULL; got {is_nullable}"
