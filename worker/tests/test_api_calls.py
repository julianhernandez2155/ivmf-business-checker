"""CANON-07: api_calls table with UNIQUE (provider, request_hash)."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending")
def test_unique_violation(conn):
    raise NotImplementedError(
        "Wave 1: insert duplicate api_calls row, assert psycopg.errors.UniqueViolation (23505)"
    )
