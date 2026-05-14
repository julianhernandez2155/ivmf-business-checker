"""D-00-11 item 5: worker_heartbeats row written by heartbeat module.

Integration test — requires SUPABASE_DEV_DB_URL pointing at the dev project.
"""
from __future__ import annotations

import importlib
import time

import pytest

pytestmark = pytest.mark.integration


def test_write_row_inserts_heartbeat(conn, monkeypatch):
    """heartbeat._write_row() must UPSERT a row keyed on WORKER_ID."""
    # Use a unique WORKER_ID for this test so we do not collide with the live worker.
    test_id = f"test-{int(time.time())}"
    monkeypatch.setenv("WORKER_ID", test_id)
    # The heartbeat module reads DATABASE_URL via get_pool(); reuse db_url.
    monkeypatch.setenv("DATABASE_URL", conn.info.dsn)

    # Re-import so module-level WORKER_ID reflects the patched env var.
    from workers import heartbeat as hb
    importlib.reload(hb)

    hb._write_row()

    # Verify the row landed.
    with conn.cursor() as cur:
        cur.execute(
            """
            select worker_id, last_seen_at
            from public.worker_heartbeats
            where worker_id = %s
            """,
            (test_id,),
        )
        row = cur.fetchone()
    assert row is not None, f"no heartbeat row for {test_id}"
    assert row[0] == test_id

    # Cleanup
    with conn.cursor() as cur:
        cur.execute(
            "delete from public.worker_heartbeats where worker_id = %s",
            (test_id,),
        )
        conn.commit()
