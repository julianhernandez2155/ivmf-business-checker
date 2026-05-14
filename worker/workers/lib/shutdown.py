"""Graceful shutdown signal coordination.

A single asyncio.Event shared by the dispatcher and heartbeat loops. SIGINT or
SIGTERM sets the event; loops poll `shutdown.is_set()` between iterations and
exit cleanly. This is the SIGTERM-drain handle for D-00-09 / Pitfall P11.
"""
from __future__ import annotations

import asyncio
import signal

shutdown: asyncio.Event = asyncio.Event()


def install_signal_handlers() -> None:
    """Register SIGINT + SIGTERM to set the shutdown event.

    Uses loop.add_signal_handler where supported; falls back to signal.signal
    on platforms that don't (e.g., Windows event loops). Safe to call at most
    once per running loop.
    """
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: shutdown.set())
