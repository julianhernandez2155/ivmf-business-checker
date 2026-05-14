"""Shared pytest fixtures for worker integration tests.

Tests requiring a live database SKIP automatically when SUPABASE_DEV_DB_URL is
unset, so local `pytest --collect-only` and CI runs without secrets stay green.
"""
from __future__ import annotations

import os

import pytest

try:
    import psycopg  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — Wave 0 stubs don't require psycopg installed
    psycopg = None  # type: ignore[assignment]


@pytest.fixture(scope="session")
def db_url() -> str:
    """Resolve the dev Postgres URL, or skip if missing.

    Tests that touch the database mark themselves @pytest.mark.integration
    and depend on this fixture. Without SUPABASE_DEV_DB_URL the whole
    integration suite is skipped (Wave 0 scaffolding policy).
    """
    url = os.environ.get("SUPABASE_DEV_DB_URL")
    if not url:
        pytest.skip("SUPABASE_DEV_DB_URL not set; skipping integration tests")
    return url


@pytest.fixture
def conn(db_url: str):
    """Yield a transactional psycopg connection that rolls back on teardown."""
    if psycopg is None:
        pytest.skip("psycopg not installed; install worker[dev] to run integration tests")
    with psycopg.connect(db_url, autocommit=False) as c:
        yield c
        c.rollback()
