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


# ---- Phase 0 / Plan 02 schema-test fixtures ----
import uuid  # noqa: E402  (placement intentional — fixtures append after primitives)


@pytest.fixture
def _role_guard(conn) -> None:
    """Fail loudly if the test DB connection is not the postgres role.

    Required because schema tests must bypass RLS and toggle
    session_replication_role for cleanup. Catches the "pooler URL accidentally
    used" footgun. Not autouse — applied per-fixture that needs the postgres
    role (so non-DB tests like normalize remain unaffected).
    """
    with conn.cursor() as cur:
        cur.execute("select current_user")
        role = cur.fetchone()[0]
    assert role == "postgres", (
        f"Test connection must use postgres role; got {role!r}. "
        "Set SUPABASE_DEV_DB_URL to the direct port-5432 connection string, "
        "not the pooler (port 6543). See worker/.env.example."
    )


@pytest.fixture(scope="session")
def test_user_id(db_url: str) -> str:
    """Create (or reuse) a stable test user in auth.users for FK targets.

    Uses a deterministic UUID so repeated runs converge on the same row.
    Inserts directly via service-role (bypasses RLS); avoids dependency on the
    Supabase admin REST API. Session-scoped so the row is upserted once per
    test run.
    """
    if psycopg is None:
        pytest.skip("psycopg not installed; install worker[dev] to run integration tests")
    uid = uuid.UUID("00000000-0000-0000-0000-00000000beef")
    email = f"phase0-test-{uid}@syr.edu"
    with psycopg.connect(db_url, autocommit=False) as c:
        with c.cursor() as cur:
            cur.execute(
                """
                insert into auth.users (
                    id, instance_id, aud, role, email,
                    encrypted_password, email_confirmed_at,
                    raw_app_meta_data, raw_user_meta_data,
                    created_at, updated_at
                ) values (
                    %s,
                    '00000000-0000-0000-0000-000000000000',
                    'authenticated', 'authenticated', %s,
                    '', now(),
                    '{"role":"user"}'::jsonb, '{}'::jsonb,
                    now(), now()
                )
                on conflict (id) do nothing
                """,
                (str(uid), email),
            )
            c.commit()
    return str(uid)
