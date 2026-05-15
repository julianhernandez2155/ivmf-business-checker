"""GAP-5 regression: review_queue table contract.

Closes Codex peer review GAP-5 (2026-05-15). Asserts:
  - Table exists with all 9 columns and the check constraints
  - audit_log_trigger fires on INSERT (extends AUTH-04 coverage to the queue)
  - Admin-only RLS: non-admin authenticated users cannot SELECT

See:
  - supabase/migrations/0010_review_queue.sql (the contract under test)
  - .planning/phases/00-foundation/00-VERIFICATION.md §GAP-5
  - .planning/phases/00-foundation/00-08-review-queue-table-PLAN.md Task 3

Skips cleanly when SUPABASE_DEV_DB_URL is unset (same gating as the rest of the
integration suite — see worker/tests/conftest.py).
"""
from __future__ import annotations

import json
import uuid

import pytest

try:
    import psycopg  # type: ignore[import-not-found]
    from psycopg import errors as pg_errors
except ImportError:  # pragma: no cover — Wave 0 stubs don't require psycopg installed
    psycopg = None  # type: ignore[assignment]
    pg_errors = None  # type: ignore[assignment]

pytestmark = pytest.mark.integration


EXPECTED_COLUMNS = {
    'id',
    'kind',
    'payload',
    'status',
    'created_by',
    'created_at',
    'resolved_at',
    'resolved_by',
    'resolution',
}


def _set_jwt(cur, claims: dict) -> None:
    """Impersonate a Supabase JWT via SET LOCAL request.jwt.claims.

    Mirrors the pattern used in test_rbac.py + test_rls_domain_allowlist.py.
    """
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps(claims),),
    )


def test_review_queue_table_exists(conn) -> None:
    """GAP-5: public.review_queue must exist after migration 0010 applies."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'public' and table_name = 'review_queue'
            """
        )
        assert cur.fetchone() is not None, (
            "public.review_queue missing — apply 0010_review_queue.sql (GAP-5)."
        )


def test_review_queue_columns(conn) -> None:
    """All 9 expected columns must be present (codegen-baseline contract)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = 'review_queue'
            """
        )
        actual = {row[0] for row in cur.fetchall()}
        missing = EXPECTED_COLUMNS - actual
        assert not missing, f"review_queue missing columns: {missing}"


def test_review_queue_kind_check_constraint_rejects_bad_value(
    conn, _role_guard
) -> None:
    """chk_review_queue_kind must reject values outside the enum set."""
    with conn.cursor() as cur:
        with pytest.raises(pg_errors.CheckViolation):
            cur.execute(
                "insert into public.review_queue (kind, payload) "
                "values ('bogus_kind', '{}'::jsonb)"
            )


def test_review_queue_status_check_constraint_rejects_bad_value(
    conn, _role_guard
) -> None:
    """chk_review_queue_status must reject values outside the enum set."""
    with conn.cursor() as cur:
        with pytest.raises(pg_errors.CheckViolation):
            cur.execute(
                "insert into public.review_queue (kind, payload, status) "
                "values ('canonical_merge', '{}'::jsonb, 'bogus_status')"
            )


def test_review_queue_insert_writes_audit_log(conn, _role_guard) -> None:
    """GAP-5 + AUTH-04: insert into review_queue must produce an audit_log row.

    Confirms trg_audit_review_queue (D-00-06 reuse of generic audit_log_trigger)
    is correctly attached to the new table.
    """
    rid = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "insert into public.review_queue (id, kind, payload) "
            "values (%s, 'canonical_merge', %s::jsonb)",
            (rid, json.dumps({'row_id': str(uuid.uuid4())})),
        )
        cur.execute(
            """
            select count(*) from public.audit_log
            where table_name = 'review_queue'
              and action = 'INSERT'
              and row_pk = %s
            """,
            (rid,),
        )
        after_count = cur.fetchone()[0]
        assert after_count == 1, (
            "GAP-5: audit_log_trigger did not fire on review_queue INSERT. "
            "Confirm trg_audit_review_queue is attached (see 0010)."
        )


def test_review_queue_rls_blocks_non_admin_select(
    conn, test_user_id, _role_guard
) -> None:
    """D-00-05 defense-in-depth: an allowlisted non-admin must NOT see queue rows."""
    rid = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "insert into public.review_queue (id, kind, payload) "
            "values (%s, 'canonical_merge', '{}'::jsonb)",
            (rid,),
        )
        _set_jwt(
            cur,
            {
                "sub": test_user_id,
                "email": f"phase0-test-{test_user_id}@syr.edu",
                "role": "authenticated",
                "app_metadata": {"role": "user"},
            },
        )
        cur.execute("set local role authenticated")
        cur.execute(
            "select count(*) from public.review_queue where id = %s", (rid,)
        )
        assert cur.fetchone()[0] == 0, (
            "Non-admin authenticated user must NOT see review_queue rows. "
            "Confirm review_queue_admin_read policy in 0010."
        )
