"""CANON-06 + CANON-07: verifications append-only + idempotency UNIQUE.

The conftest `conn` fixture yields a transactional connection that rolls back
on teardown. Tests below explicitly commit when they need a trigger to fire on
data the test itself wrote; cleanup happens in the per-test `try/finally` using
the cascade-delete pattern.

Cleanup pattern: DELETE the parent run; `verifications.run_id` has
`on delete cascade`. The BEFORE DELETE trigger on verifications fires for
direct DELETEs but is bypassed during cascade only when
`session_replication_role='replica'` — we set it for cleanup only.
"""
from __future__ import annotations

import uuid

import psycopg
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def seed_verification(conn, test_user_id, _role_guard):
    """Insert a verification row to UPDATE/DELETE against."""
    run_id = uuid.uuid4()
    row_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.runs (id, user_id, status)
            values (%s, %s, 'pending')
            on conflict (id) do nothing
            """,
            (str(run_id), test_user_id),
        )
        cur.execute(
            """
            insert into public.verifications (id, run_id, row_index, pass, method)
            values (%s, %s, 0, 1, 'cache')
            returning id
            """,
            (str(row_id), str(run_id)),
        )
        vid = cur.fetchone()[0]
        conn.commit()
    try:
        yield vid, run_id
    finally:
        with conn.cursor() as cur:
            cur.execute("set session_replication_role = replica")
            cur.execute("delete from public.runs where id = %s", (str(run_id),))
            cur.execute("set session_replication_role = origin")
            conn.commit()


def test_update_raises_p0001(conn, seed_verification):
    vid, _ = seed_verification
    with pytest.raises(psycopg.errors.RaiseException) as exc:
        with conn.cursor() as cur:
            cur.execute(
                "update public.verifications set status='active' where id = %s",
                (vid,),
            )
            conn.commit()
    assert exc.value.sqlstate == "P0001"
    assert "append-only" in str(exc.value)
    conn.rollback()


def test_delete_raises_p0001(conn, seed_verification):
    vid, _ = seed_verification
    with pytest.raises(psycopg.errors.RaiseException) as exc:
        with conn.cursor() as cur:
            cur.execute(
                "delete from public.verifications where id = %s",
                (vid,),
            )
            conn.commit()
    assert exc.value.sqlstate == "P0001"
    conn.rollback()


def test_unique_violation_run_row_pass(conn, test_user_id, _role_guard):
    """CANON-07: duplicate (run_id, row_index, pass) must raise 23505."""
    run_id = uuid.uuid4()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.runs (id, user_id, status) values (%s, %s, 'pending')",
                (str(run_id), test_user_id),
            )
            cur.execute(
                "insert into public.verifications (run_id, row_index, pass, method) "
                "values (%s, 0, 1, 'cache')",
                (str(run_id),),
            )
            conn.commit()
        with pytest.raises(psycopg.errors.UniqueViolation) as exc:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into public.verifications (run_id, row_index, pass, method) "
                    "values (%s, 0, 1, 'cache')",
                    (str(run_id),),
                )
                conn.commit()
        assert exc.value.sqlstate == "23505"
        conn.rollback()
    finally:
        with conn.cursor() as cur:
            cur.execute("set session_replication_role = replica")
            cur.execute("delete from public.runs where id = %s", (str(run_id),))
            cur.execute("set session_replication_role = origin")
            conn.commit()
