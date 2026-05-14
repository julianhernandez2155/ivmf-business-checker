"""CANON-05: businesses table accepts new canonical row with required NOT NULLs."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending")
def test_businesses_required_columns(conn):
    raise NotImplementedError(
        "Wave 1: introspect; assert id, name, created_at NOT NULL"
    )
