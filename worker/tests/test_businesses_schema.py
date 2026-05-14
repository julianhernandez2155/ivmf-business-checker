"""CANON-05: businesses table has required canonical columns."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

REQUIRED_COLUMNS = {"id", "name", "normalized_name", "ein", "created_at"}


def test_required_columns(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name from information_schema.columns
            where table_schema='public' and table_name='businesses'
            """
        )
        cols = {r[0] for r in cur.fetchall()}
    missing = REQUIRED_COLUMNS - cols
    assert not missing, f"businesses missing columns: {missing}"


def test_name_is_not_null(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select is_nullable from information_schema.columns
            where table_schema='public' and table_name='businesses'
              and column_name='name'
            """
        )
        is_nullable = cur.fetchone()[0]
    assert is_nullable == "NO", f"businesses.name must be NOT NULL; got {is_nullable}"
