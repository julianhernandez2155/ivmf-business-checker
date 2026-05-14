"""D-00-09 + Pitfall P11: dispatcher uses vt=300 at the consumer call site.

These tests are deterministic — they do NOT touch the database. PGMQueue is
mocked at the import boundary so the test suite stays green without
SUPABASE_DEV_DB_URL.
"""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import MagicMock, patch

import pytest


def test_vt_seconds_is_300():
    """D-00-09 contract: dispatcher passes vt=300 to read_with_poll."""
    from workers import dispatcher
    assert dispatcher.VT_SECONDS == 300, (
        f"D-00-09 violation: vt must be 300, got {dispatcher.VT_SECONDS}"
    )


def test_dispatcher_loop_is_async():
    """dispatcher_loop must be a coroutine function so the FastAPI lifespan can spawn it."""
    from workers.dispatcher import dispatcher_loop
    assert inspect.iscoroutinefunction(dispatcher_loop)


def test_queue_client_read_one_passes_vt_300():
    """QueueClient.read_one must forward vt=300 verbatim to PGMQueue.read_with_poll."""
    from workers.lib.pgmq_client import QueueClient

    with patch("workers.lib.pgmq_client.PGMQueue") as MockQ:
        mock_q = MagicMock()
        mock_q.read_with_poll.return_value = []
        MockQ.return_value = mock_q

        client = QueueClient(dsn="postgres://fake")
        client.read_one("q_verify", vt_seconds=300, poll_seconds=20)

        mock_q.read_with_poll.assert_called_once_with(
            queue="q_verify",
            vt=300,
            qty=1,
            max_poll_seconds=20,
        )


@pytest.mark.asyncio
async def test_dispatcher_loop_exits_on_shutdown(monkeypatch):
    """SIGTERM contract: dispatcher_loop returns cleanly when shutdown event is set."""
    from workers import dispatcher as d
    from workers.lib.shutdown import shutdown as shutdown_evt

    # Replace QueueClient with a stub that returns no messages.
    class FakeClient:
        def read_one(self, *a, **kw):
            return None

        def archive(self, *a, **kw):
            pass

    monkeypatch.setattr(d, "QueueClient", lambda: FakeClient())

    # Replace asyncio.to_thread with a shim that yields to the event loop after
    # running the function synchronously. The yield is critical — in production
    # `read_with_poll` blocks for up to 20s and naturally yields; the test stub
    # would otherwise CPU-spin and starve `cancel_soon`'s timer.
    async def fake_to_thread(fn, *a, **kw):
        result = fn(*a, **kw)
        await asyncio.sleep(0)
        return result

    monkeypatch.setattr(d.asyncio, "to_thread", fake_to_thread)

    shutdown_evt.clear()

    async def cancel_soon():
        await asyncio.sleep(0.1)
        shutdown_evt.set()

    await asyncio.gather(
        d.dispatcher_loop(),
        cancel_soon(),
    )
    # Reaching this line proves dispatcher_loop returned cleanly post-shutdown.
    # Reset for any later tests in the session.
    shutdown_evt.clear()
