"""CANON-05: businesses table exists with required columns."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending — businesses table not yet migrated")
def test_businesses_table_exists(conn):
    with conn.cursor() as cur:
        cur.execute(
            "select count(*) from information_schema.tables "
            "where table_schema='public' and table_name='businesses'"
        )
        assert cur.fetchone()[0] == 1, "businesses table missing"
    raise NotImplementedError(
        "Wave 1: assert full column shape per ARCHITECTURE.md table inventory"
    )
