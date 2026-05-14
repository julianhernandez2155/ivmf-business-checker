"""FastAPI app for the Railway worker.

Lifespan responsibilities:
    1. Open the psycopg ConnectionPool.
    2. Install SIGINT/SIGTERM handlers that set the shutdown event.
    3. Spawn the dispatcher + heartbeat loops as background asyncio tasks.
    4. On shutdown: set the event, cancel tasks, await final drain, close pool.

HTTP surface:
    GET /health     — liveness probe used by Railway healthcheck.
    GET /heartbeat  — reads the worker's own row from public.worker_heartbeats
                      so the Phase 0 demo (D-00-11 item 5) can verify the row
                      lifecycle end-to-end without psql.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from workers.dispatcher import dispatcher_loop
from workers.heartbeat import WORKER_ID, heartbeat_loop
from workers.lib.db import close_pool, get_pool
from workers.lib.shutdown import install_signal_handlers, shutdown

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: pool + signals + background tasks. Shutdown: cancel + drain + close."""
    log.info("worker.lifespan.start worker_id=%s", WORKER_ID)
    get_pool()
    install_signal_handlers()
    tasks = [
        asyncio.create_task(dispatcher_loop(), name="dispatcher"),
        asyncio.create_task(heartbeat_loop(), name="heartbeat"),
    ]
    try:
        yield
    finally:
        log.info("worker.lifespan.shutdown")
        shutdown.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        close_pool()


app = FastAPI(lifespan=lifespan, title="IVMF Business Checker Worker")


@app.get("/health")
def health() -> dict[str, Any]:
    """Railway healthcheck target. 200 = process is up; does not touch the DB."""
    return {"status": "ok", "worker_id": WORKER_ID}


@app.get("/heartbeat")
def heartbeat() -> dict[str, Any]:
    """Return the latest worker_heartbeats row for THIS worker.

    Used by the Phase 0 demo (D-00-11 item 5) to prove the row is being written.
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select worker_id, last_seen_at, hostname, version "
                "from public.worker_heartbeats where worker_id = %s",
                (WORKER_ID,),
            )
            row = cur.fetchone()
    if row is None:
        return {"status": "not_yet_written", "worker_id": WORKER_ID}
    return {
        "status": "ok",
        "worker_id": row[0],
        "last_seen_at": row[1].isoformat() if row[1] else None,
        "hostname": row[2],
        "version": row[3],
    }
