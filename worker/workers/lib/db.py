"""psycopg3 connection pool for the worker.

Single shared pool, lazily initialized on first get_pool() call. Closed via
close_pool() during FastAPI lifespan shutdown.

DATABASE_URL must be a direct postgres-role DSN (port 5432) — the pooler URL
(port 6543) cannot toggle session_replication_role or bypass RLS. See
worker/.env.example.
"""
from __future__ import annotations

import os
from typing import Optional

from psycopg_pool import ConnectionPool

_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """Return the singleton ConnectionPool, opening it on first call.

    Raises:
        RuntimeError: when DATABASE_URL is not set in the environment.
    """
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is required")
        _pool = ConnectionPool(
            conninfo=dsn,
            min_size=1,
            max_size=4,
            open=True,
            kwargs={"autocommit": False},
        )
    return _pool


def close_pool() -> None:
    """Close the pool if it has been opened. Idempotent."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
