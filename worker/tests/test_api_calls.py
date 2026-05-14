"""CANON-07 (api_calls side): duplicate (provider, request_hash) raises 23505.

No FK to runs — simpler cleanup than verifications. api_calls has no append-only
trigger; standard DELETE works on its own.
"""
from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.integration


def test_unique_violation(conn, _role_guard):
    request_hash = "test-hash-plan02-unique"
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.api_calls (provider, request_hash) values (%s, %s)",
                ("perplexity", request_hash),
            )
            conn.commit()
        with pytest.raises(psycopg.errors.UniqueViolation) as exc:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into public.api_calls (provider, request_hash) values (%s, %s)",
                    ("perplexity", request_hash),
                )
                conn.commit()
        assert exc.value.sqlstate == "23505"
        conn.rollback()
    finally:
        with conn.cursor() as cur:
            cur.execute(
                "delete from public.api_calls where request_hash = %s",
                (request_hash,),
            )
            conn.commit()
