"""Phase 0 schema gate: all 11 expected tables exist in public.

Verifies the Plan 02 migration suite has been applied to the dev DB.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "businesses",
    "runs",
    "run_rows",
    "verifications",
    "api_calls",
    "app_config",
    "api_keys",
    "budget_ledger",
    "outreach_tickets",
    "audit_log",
    "worker_heartbeats",
}


def test_all_phase0_tables_exist(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select table_name from information_schema.tables
            where table_schema='public'
            """
        )
        present = {r[0] for r in cur.fetchall()}
    missing = EXPECTED_TABLES - present
    assert not missing, f"public tables missing after migration: {missing}"
