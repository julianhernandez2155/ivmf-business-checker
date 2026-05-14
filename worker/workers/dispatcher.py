"""D-00-09 + Pitfall P11: long-poll q_verify with vt=300 at the consumer call site.

Phase 0 STUB: reads messages and immediately archives them — NO business logic.
Phase 2 will replace archive() with verify_row processing (Perplexity/FireCrawl
+ verification ledger writes). The infra contract proven here:

    1. Worker reaches Postgres+pgmq.
    2. read_with_poll receives vt=300 at every call site (D-00-09).
    3. Messages drain cleanly when shutdown event is set (SIGTERM-safe).
"""
from __future__ import annotations

import asyncio
import logging

from workers.lib.pgmq_client import QueueClient
from workers.lib.shutdown import shutdown

log = logging.getLogger(__name__)

QUEUE = "q_verify"
VT_SECONDS = 300          # D-00-09: per-read vt, NOT per-queue.
POLL_SECONDS = 20


def _read_one(q: QueueClient):
    """Run the blocking long-poll inside a worker thread. Returns msg or None."""
    return q.read_one(QUEUE, vt_seconds=VT_SECONDS, poll_seconds=POLL_SECONDS)


async def dispatcher_loop() -> None:
    """Long-poll q_verify and archive whatever it finds until shutdown is set."""
    log.info("dispatcher_loop.start queue=%s vt=%s", QUEUE, VT_SECONDS)
    q = QueueClient()
    while not shutdown.is_set():
        try:
            msg = await asyncio.to_thread(_read_one, q)
        except Exception:
            log.exception("dispatcher.read_failed")
            await asyncio.sleep(2)
            continue
        if msg is None:
            continue
        try:
            msg_id = getattr(msg, "msg_id", msg)
            log.info("dispatcher.message msg_id=%s", msg_id)
            # Phase 0 stub: archive immediately. Phase 2 replaces this with
            # verify_row(msg) + extend_vt() during long-running calls.
            await asyncio.to_thread(q.archive, QUEUE, msg_id)
        except Exception:
            log.exception("dispatcher.process_failed")
    log.info("dispatcher_loop.stop")
