"""AUTH-02 + D-00-10: app_config seed rows exist."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending — seed not yet applied")
def test_email_domain_allowlist_seeded(conn):
    with conn.cursor() as cur:
        cur.execute(
            "select value from app_config where key='email_domain_allowlist'"
        )
        row = cur.fetchone()
        assert row is not None
        assert "syr.edu" in row[0]
    raise NotImplementedError(
        "Wave 1: also assert column_allowlist row exists per D-00-10"
    )
