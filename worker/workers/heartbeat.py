"""D-00-11 item 5: write a row to worker_heartbeats every 30s.

Doubles as the basis for the watchdog Phase 2 needs for resumability.

Schema target (created in supabase/migrations/0001_init_schema.sql):
    public.worker_heartbeats (
        worker_id text PRIMARY KEY,
        last_seen_at timestamptz not null,
        hostname text,
        version text
    )
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket

from workers.lib.db import get_pool
from workers.lib.shutdown import shutdown

log = logging.getLogger(__name__)

WORKER_ID: str = (
    os.environ.get("WORKER_ID")
    or os.environ.get("RAILWAY_SERVICE_ID")
    or "local-dev"
)
GIT_SHA: str = os.environ.get("GIT_SHA", "dev")
HEARTBEAT_INTERVAL_S: int = 30


def _write_row() -> None:
    """UPSERT a single heartbeat row for this worker. Synchronous (called via to_thread)."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.worker_heartbeats (worker_id, last_seen_at, hostname, version)
                values (%s, now(), %s, %s)
                on conflict (worker_id) do update set
                    last_seen_at = now(),
                    hostname = excluded.hostname,
                    version = excluded.version
                """,
                (WORKER_ID, socket.gethostname(), GIT_SHA),
            )
            conn.commit()


async def heartbeat_loop() -> None:
    """Write a heartbeat immediately, then every HEARTBEAT_INTERVAL_S until shutdown."""
    log.info("heartbeat_loop.start worker_id=%s", WORKER_ID)
    try:
        await asyncio.to_thread(_write_row)
    except Exception:
        log.exception("heartbeat.initial_write_failed")
    while not shutdown.is_set():
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=HEARTBEAT_INTERVAL_S)
            # If wait() returned without timeout, shutdown was set — exit.
            break
        except asyncio.TimeoutError:
            # Normal path: 30s elapsed without shutdown, write another row.
            pass
        try:
            await asyncio.to_thread(_write_row)
        except Exception:
            log.exception("heartbeat.write_failed")
    log.info("heartbeat_loop.stop")
