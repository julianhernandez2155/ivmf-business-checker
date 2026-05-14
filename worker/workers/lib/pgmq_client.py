"""tembo-pgmq-python 0.10 wrapper.

D-00-09: visibility timeout (vt) is configured at the consumer call site, NOT at
queue creation. The migration in 0005_pgmq_queues.sql calls pgmq.create('q_verify')
with no vt; vt=300s flows in here via read_with_poll(vt=300, ...).

Pitfall P11 mitigation: vt is 300s (5 min) — long enough for Phase 2 per-row jobs,
short enough that a worker crash does not stall the queue for hours.

The PGMQueue constructor in 0.10 accepts either dsn=... OR host/port/username/
password/database kwargs depending on the published build. The try/except
fallback lets the wrapper survive both call shapes without forcing a downstream
release pin.
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

from tembo_pgmq_python import PGMQueue


class QueueClient:
    """Thin wrapper over tembo-pgmq-python that enforces D-00-09 (vt-per-read)."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or os.environ["DATABASE_URL"]
        try:
            self._q = PGMQueue(dsn=self._dsn)
        except TypeError:
            # Fallback for builds that require kwargs instead of dsn=.
            p = urlparse(self._dsn)
            self._q = PGMQueue(
                host=p.hostname or "localhost",
                port=p.port or 5432,
                username=p.username or "postgres",
                password=p.password or "",
                database=(p.path or "/postgres").lstrip("/"),
            )

    def read_one(self, queue: str, vt_seconds: int = 300, poll_seconds: int = 20):
        """Long-poll one message off `queue` with vt-per-read (D-00-09).

        Returns the first message returned by read_with_poll, or None if the
        long-poll window elapsed with no messages.
        """
        msgs = self._q.read_with_poll(
            queue=queue,
            vt=vt_seconds,
            qty=1,
            max_poll_seconds=poll_seconds,
        )
        return msgs[0] if msgs else None

    def archive(self, queue: str, msg_id: int) -> None:
        """Move a message to the queue's archive table (terminal success)."""
        self._q.archive(queue, msg_id)

    def delete(self, queue: str, msg_id: int) -> None:
        """Delete a message outright (terminal — no archive row)."""
        self._q.delete(queue, msg_id)

    def extend_vt(self, queue: str, msg_id: int, additional_seconds: int) -> None:
        """Extend the visibility timeout for an in-flight message (P11 mitigation)."""
        self._q.set_vt(queue, msg_id, additional_seconds)
