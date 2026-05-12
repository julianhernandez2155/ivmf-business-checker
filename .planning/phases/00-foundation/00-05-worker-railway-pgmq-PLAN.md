---
phase: 00-foundation
plan: 05
type: execute
wave: 4
depends_on: [01, 02, 03]
files_modified:
  - worker/.env.example
  - worker/Procfile
  - worker/railway.json
  - worker/workers/main.py
  - worker/workers/dispatcher.py
  - worker/workers/heartbeat.py
  - worker/workers/lib/db.py
  - worker/workers/lib/pgmq_client.py
  - worker/workers/lib/shutdown.py
  - worker/tests/test_heartbeat.py
  - worker/tests/test_worker_loop.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "Worker FastAPI app exposes /health and /heartbeat endpoints returning JSON"
    - "Worker on Railway long-polls q_verify with vt=300s configured at the consumer call site (NOT at queue creation)"
    - "Worker writes a row to worker_heartbeats every 30s; row visible via psql"
    - "SIGTERM handler triggers graceful shutdown; pgmq vt prevents redelivery during drain window"
    - "Worker can be imported with pip install -e ../business_checker and reuses the existing engine package"
    - "Worker reads DATABASE_URL from env; no hardcoded credentials"
  artifacts:
    - path: worker/workers/main.py
      provides: "FastAPI app + asyncio task spawning (dispatcher + heartbeat) via lifespan"
      contains: "FastAPI"
      min_lines: 50
    - path: worker/workers/dispatcher.py
      provides: "pgmq long-poll loop reading q_verify with vt=300 at call site"
      contains: "read_with_poll"
    - path: worker/workers/heartbeat.py
      provides: "UPSERT into worker_heartbeats every 30s"
      contains: "worker_heartbeats"
    - path: worker/workers/lib/pgmq_client.py
      provides: "tembo-pgmq-python 0.10 wrapper; vt=300 at call site (D-00-09)"
      contains: "vt"
    - path: worker/Procfile
      provides: "Railway start command: uvicorn workers.main:app"
      contains: "uvicorn"
    - path: worker/railway.json
      provides: "Railway service config (start command, healthcheck, restart policy)"
      contains: "startCommand"
  key_links:
    - from: "worker/workers/main.py"
      to: "dispatcher.loop AND heartbeat.heartbeat_loop"
      via: "asyncio.create_task on startup"
      pattern: "create_task|asyncio\\.gather"
    - from: "worker/workers/dispatcher.py"
      to: "pgmq.q_verify"
      via: "tembo-pgmq-python read_with_poll"
      pattern: "read_with_poll"
    - from: "worker/workers/heartbeat.py"
      to: "public.worker_heartbeats"
      via: "psycopg INSERT ON CONFLICT UPDATE"
      pattern: "on conflict.*worker_id"
---

<objective>
Deploy a minimal Railway-hosted FastAPI worker that long-polls `q_verify` with vt=300 per D-00-09, writes a heartbeat row every 30 seconds per D-00-11 item 5, and gracefully handles SIGTERM. Phase 0 worker scaffold only — NO business logic, NO Perplexity calls. Just proof that the infrastructure works end-to-end.

Purpose: Verify D-00-09 (pgmq vt per Pitfall P11) and D-00-11 item 5 (heartbeat row). Provides the deployment target Phase 2 will fill with real verification logic.

Output: 6 worker source files, Railway config, 2 test stubs converted to passing tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-RESEARCH.md
@.planning/research/STACK.md
@.planning/research/ARCHITECTURE.md
@.planning/research/PITFALLS.md
@.planning/phases/00-foundation/00-02-supabase-schema-rls-SUMMARY.md
@worker/pyproject.toml

<interfaces>
tembo-pgmq-python 0.10 API surface — verify with help(PGMQueue) at install time:

  from tembo_pgmq_python import PGMQueue
  q = PGMQueue(dsn=os.environ["DATABASE_URL"])         # or host/port kwargs
  msgs = q.read_with_poll(queue='q_verify', vt=300, qty=1, max_poll_seconds=20)
  q.archive('q_verify', msg.msg_id)
  q.delete('q_verify', msg.msg_id)
  q.set_vt('q_verify', msg.msg_id, additional_seconds=300)

psycopg3 pool pattern:

  from psycopg_pool import ConnectionPool
  pool = ConnectionPool(conninfo=os.environ["DATABASE_URL"], min_size=1, max_size=4, open=True)
  with pool.connection() as conn:
      with conn.cursor() as cur:
          cur.execute(...)

FastAPI lifespan pattern:

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      tasks = [asyncio.create_task(dispatcher_loop()), asyncio.create_task(heartbeat_loop())]
      yield
      for t in tasks: t.cancel()
      await asyncio.gather(*tasks, return_exceptions=True)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Worker library — db pool, pgmq client wrapper, shutdown handler</name>
  <files>worker/.env.example, worker/workers/lib/db.py, worker/workers/lib/pgmq_client.py, worker/workers/lib/shutdown.py</files>
  <read_first>
    - .planning/research/STACK.md (psycopg3 + tembo-pgmq-python rows at lines 49-50)
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-09 vt at consumer site)
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 4 lines 450-499)
    - .planning/research/PITFALLS.md (P11 vt misconfigured at lines 248-266)
    - worker/pyproject.toml (deps already pinned in Wave 0)
  </read_first>
  <action>
    Create `worker/.env.example`:
    ```
    DATABASE_URL=postgres://postgres:PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres
    SUPABASE_URL=https://YOUR_PROJECT.supabase.co
    SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
    WORKER_ID=local-dev
    GIT_SHA=dev
    LOG_LEVEL=info
    ```

    Create `worker/workers/lib/db.py`:
    ```python
    """psycopg3 connection pool for the worker."""
    from __future__ import annotations
    import os
    from psycopg_pool import ConnectionPool

    _pool: ConnectionPool | None = None


    def get_pool() -> ConnectionPool:
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
        global _pool
        if _pool is not None:
            _pool.close()
            _pool = None
    ```

    Create `worker/workers/lib/pgmq_client.py`:
    ```python
    """tembo-pgmq-python 0.10 wrapper.

    D-00-09: visibility timeout (vt) is configured at the consumer call site, NOT at
    queue creation. The migration in 0005_pgmq_queues.sql calls pgmq.create('q_verify')
    with no vt; vt=300s flows in here via read_with_poll(vt=300, ...).

    Pitfall P11 mitigation: vt is 300s (5 min) — long enough for Phase 2 per-row jobs,
    short enough that a worker crash does not stall the queue for hours.
    """
    from __future__ import annotations
    import os
    from typing import Optional
    from tembo_pgmq_python import PGMQueue


    class QueueClient:
        def __init__(self, dsn: Optional[str] = None) -> None:
            self._dsn = dsn or os.environ["DATABASE_URL"]
            try:
                self._q = PGMQueue(dsn=self._dsn)
            except TypeError:
                from urllib.parse import urlparse
                p = urlparse(self._dsn)
                self._q = PGMQueue(
                    host=p.hostname or "localhost",
                    port=p.port or 5432,
                    username=p.username or "postgres",
                    password=p.password or "",
                    database=(p.path or "/postgres").lstrip("/"),
                )

        def read_one(self, queue: str, vt_seconds: int = 300, poll_seconds: int = 20):
            """D-00-09: vt is per-read, not queue-level. Pitfall P11 mitigated here."""
            msgs = self._q.read_with_poll(
                queue=queue,
                vt=vt_seconds,
                qty=1,
                max_poll_seconds=poll_seconds,
            )
            return msgs[0] if msgs else None

        def archive(self, queue: str, msg_id: int) -> None:
            self._q.archive(queue, msg_id)

        def delete(self, queue: str, msg_id: int) -> None:
            self._q.delete(queue, msg_id)

        def extend_vt(self, queue: str, msg_id: int, additional_seconds: int) -> None:
            self._q.set_vt(queue, msg_id, additional_seconds)
    ```

    Create `worker/workers/lib/shutdown.py`:
    ```python
    """Graceful shutdown signal coordination."""
    from __future__ import annotations
    import asyncio
    import signal

    shutdown = asyncio.Event()


    def install_signal_handlers() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, shutdown.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: shutdown.set())
    ```
  </action>
  <verify>
    <automated>test -f worker/.env.example && test -f worker/workers/lib/db.py && test -f worker/workers/lib/pgmq_client.py && test -f worker/workers/lib/shutdown.py && grep -q "DATABASE_URL" worker/.env.example && grep -q "ConnectionPool" worker/workers/lib/db.py && grep -q "read_with_poll" worker/workers/lib/pgmq_client.py && grep -q "D-00-09" worker/workers/lib/pgmq_client.py && grep -q "asyncio.Event" worker/workers/lib/shutdown.py</automated>
  </verify>
  <acceptance_criteria>
    - All 4 files exist
    - `worker/.env.example` contains DATABASE_URL, SUPABASE_SERVICE_ROLE_KEY, WORKER_ID
    - `worker/workers/lib/db.py` exports get_pool() and close_pool(); uses psycopg_pool.ConnectionPool
    - `worker/workers/lib/pgmq_client.py` defines class QueueClient with methods read_one, archive, delete, extend_vt
    - `pgmq_client.py` read_one defaults vt_seconds=300 AND passes vt=vt_seconds to read_with_poll
    - `pgmq_client.py` contains docstring referencing D-00-09 and Pitfall P11
    - `worker/workers/lib/shutdown.py` exports shutdown asyncio.Event and install_signal_handlers()
    - All 4 modules importable from cd worker via python -c "from workers.lib.db import get_pool; from workers.lib.pgmq_client import QueueClient; from workers.lib.shutdown import shutdown"
    - No hardcoded credentials; all secrets via os.environ
  </acceptance_criteria>
  <done>Library primitives ready: connection pool, queue client with correct vt semantics, shutdown event.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: FastAPI app + dispatcher loop + heartbeat loop + Railway config</name>
  <files>worker/workers/main.py, worker/workers/dispatcher.py, worker/workers/heartbeat.py, worker/Procfile, worker/railway.json</files>
  <read_first>
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 4 dispatcher stub lines 488-499; Pattern 5 heartbeat lines 502-526)
    - .planning/research/ARCHITECTURE.md (Worker module inventory at lines 111-129)
    - worker/workers/lib/pgmq_client.py (just created — QueueClient API)
    - worker/workers/lib/db.py (just created — get_pool)
    - worker/workers/lib/shutdown.py (just created — shutdown event)
  </read_first>
  <action>
    Create `worker/workers/heartbeat.py`:
    ```python
    """D-00-11 item 5: write a row to worker_heartbeats every 30s.

    Doubles as the basis for the watchdog Phase 2 needs for resumability.
    """
    from __future__ import annotations
    import asyncio
    import os
    import socket
    import logging

    from workers.lib.db import get_pool
    from workers.lib.shutdown import shutdown

    log = logging.getLogger(__name__)
    WORKER_ID = os.environ.get("WORKER_ID") or os.environ.get("RAILWAY_SERVICE_ID") or "local-dev"
    GIT_SHA = os.environ.get("GIT_SHA", "dev")
    HEARTBEAT_INTERVAL_S = 30


    def _write_row() -> None:
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
        log.info("heartbeat_loop.start worker_id=%s", WORKER_ID)
        try:
            await asyncio.to_thread(_write_row)
        except Exception:
            log.exception("heartbeat.initial_write_failed")
        while not shutdown.is_set():
            try:
                await asyncio.wait_for(shutdown.wait(), timeout=HEARTBEAT_INTERVAL_S)
                break
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.to_thread(_write_row)
            except Exception:
                log.exception("heartbeat.write_failed")
        log.info("heartbeat_loop.stop")
    ```

    Create `worker/workers/dispatcher.py`:
    ```python
    """D-00-09 + Pitfall P11: long-poll q_verify with vt=300 at the consumer call site.

    Phase 0 STUB: reads messages and immediately archives them — no business logic.
    Phase 2 will replace archive() with verify_row processing.
    """
    from __future__ import annotations
    import asyncio
    import logging

    from workers.lib.pgmq_client import QueueClient
    from workers.lib.shutdown import shutdown

    log = logging.getLogger(__name__)
    QUEUE = "q_verify"
    VT_SECONDS = 300        # D-00-09
    POLL_SECONDS = 20


    def _read_one(q: QueueClient):
        return q.read_one(QUEUE, vt_seconds=VT_SECONDS, poll_seconds=POLL_SECONDS)


    async def dispatcher_loop() -> None:
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
                await asyncio.to_thread(q.archive, QUEUE, msg_id)
            except Exception:
                log.exception("dispatcher.process_failed")
        log.info("dispatcher_loop.stop")
    ```

    Create `worker/workers/main.py`:
    ```python
    """FastAPI app for the Railway worker."""
    from __future__ import annotations
    import asyncio
    import logging
    import os
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    from workers.dispatcher import dispatcher_loop
    from workers.heartbeat import heartbeat_loop, WORKER_ID
    from workers.lib.db import get_pool, close_pool
    from workers.lib.shutdown import install_signal_handlers, shutdown

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    log = logging.getLogger(__name__)


    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
    def health() -> dict:
        return {"status": "ok", "worker_id": WORKER_ID}


    @app.get("/heartbeat")
    def heartbeat() -> dict:
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
    ```

    Create `worker/Procfile`:
    ```
    web: uvicorn workers.main:app --host 0.0.0.0 --port $PORT
    ```

    Create `worker/railway.json`:
    ```json
    {
      "$schema": "https://railway.app/railway.schema.json",
      "build": {
        "builder": "NIXPACKS",
        "buildCommand": "pip install -e . && pip install -e ../business_checker"
      },
      "deploy": {
        "startCommand": "uvicorn workers.main:app --host 0.0.0.0 --port $PORT",
        "healthcheckPath": "/health",
        "healthcheckTimeout": 30,
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 5
      }
    }
    ```

    Deploy to Railway:
    1. Link the Railway project (interactive): `railway link` → pick `ivmf-checker-worker`
    2. Set env vars in Railway dashboard: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, WORKER_ID=railway-prod
    3. Set service root to `worker/` (Settings → Source → Root Directory)
    4. Deploy: `railway up` (or git push if GitHub-integrated)
    5. Verify: `curl https://YOUR_DOMAIN/health` returns `{"status":"ok",...}`
    6. After 30s: `curl https://YOUR_DOMAIN/heartbeat` returns a row with last_seen_at
    7. `psql $SUPABASE_DEV_DB_URL -tAc "select last_seen_at from public.worker_heartbeats order by last_seen_at desc limit 1"` returns a recent timestamp.
  </action>
  <verify>
    <automated>test -f worker/workers/main.py && test -f worker/workers/dispatcher.py && test -f worker/workers/heartbeat.py && test -f worker/Procfile && test -f worker/railway.json && grep -q "FastAPI" worker/workers/main.py && grep -q "lifespan" worker/workers/main.py && grep -q "dispatcher_loop" worker/workers/main.py && grep -q "heartbeat_loop" worker/workers/main.py && grep -q "VT_SECONDS = 300" worker/workers/dispatcher.py && grep -q "worker_heartbeats" worker/workers/heartbeat.py && grep -q "on conflict" worker/workers/heartbeat.py && grep -q "uvicorn" worker/Procfile && python -c "import json; json.load(open('worker/railway.json'))"</automated>
  </verify>
  <acceptance_criteria>
    - All 5 files exist
    - `worker/workers/main.py` defines `app = FastAPI(lifespan=lifespan, ...)` AND `/health` AND `/heartbeat` route
    - `main.py` spawns both `dispatcher_loop` and `heartbeat_loop` as asyncio tasks
    - `worker/workers/dispatcher.py` defines `VT_SECONDS = 300` AND calls `q.read_one(..., vt_seconds=VT_SECONDS, ...)`
    - `worker/workers/heartbeat.py` UPSERTs into `public.worker_heartbeats` with `on conflict (worker_id) do update`
    - `worker/Procfile` contains `uvicorn workers.main:app`
    - `worker/railway.json` is valid JSON AND contains `healthcheckPath: "/health"`
    - After deploy: `curl https://RAILWAY_DOMAIN/health` returns 200 with `worker_id`
    - After 30s: `psql -tAc "select count(*) from public.worker_heartbeats where last_seen_at > now() - interval '60 seconds'"` returns ≥ 1
  </acceptance_criteria>
  <done>Worker is live on Railway; long-polls q_verify with vt=300; writes heartbeat rows every 30s; D-00-11 item 5 is demoable.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire heartbeat + dispatcher integration tests</name>
  <files>worker/tests/test_heartbeat.py, worker/tests/test_worker_loop.py</files>
  <read_first>
    - worker/workers/heartbeat.py (just created)
    - worker/workers/dispatcher.py (just created)
    - worker/workers/lib/pgmq_client.py (just created)
    - worker/tests/conftest.py (db fixture)
    - .planning/phases/00-foundation/00-VALIDATION.md (Per-Task Verification Map 0-04-* rows)
  </read_first>
  <behavior>
    - test_heartbeat.py: import _write_row, call it directly; query worker_heartbeats and assert a row exists with WORKER_ID and last_seen_at within last 5 seconds
    - test_worker_loop.py: import dispatcher module; assert VT_SECONDS == 300; assert dispatcher_loop is an async function; mock QueueClient.read_one and verify it is called with vt_seconds=300
  </behavior>
  <action>
    Replace `worker/tests/test_heartbeat.py`:
    ```python
    """D-00-11 item 5: worker_heartbeats row written by heartbeat module."""
    import os
    import time
    import pytest

    pytestmark = pytest.mark.integration


    def test_write_row_inserts_heartbeat(conn, monkeypatch):
        # Use a unique WORKER_ID for this test so we do not collide with the running worker
        test_id = f"test-{int(time.time())}"
        monkeypatch.setenv("WORKER_ID", test_id)

        # Re-import to pick up the env var
        import importlib
        from workers import heartbeat as hb
        importlib.reload(hb)

        hb._write_row()

        # Verify the row landed
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
    ```

    Replace `worker/tests/test_worker_loop.py`:
    ```python
    """D-00-09 + Pitfall P11: dispatcher uses vt=300 at the consumer call site."""
    import asyncio
    import inspect
    import pytest
    from unittest.mock import MagicMock, patch


    def test_vt_seconds_is_300():
        from workers import dispatcher
        assert dispatcher.VT_SECONDS == 300, (
            f"D-00-09 violation: vt must be 300, got {dispatcher.VT_SECONDS}"
        )


    def test_dispatcher_loop_is_async():
        from workers.dispatcher import dispatcher_loop
        assert inspect.iscoroutinefunction(dispatcher_loop)


    def test_queue_client_read_one_passes_vt_300():
        """Verify QueueClient.read_one delegates vt=300 to PGMQueue.read_with_poll."""
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
        """Dispatcher should exit cleanly when shutdown event is set."""
        from workers import dispatcher as d
        from workers.lib.shutdown import shutdown as shutdown_evt

        # Replace QueueClient.read_one with a stub that returns None
        class FakeClient:
            def read_one(self, *a, **kw):
                return None
            def archive(self, *a, **kw):
                pass

        monkeypatch.setattr(d, "QueueClient", lambda: FakeClient())
        # Replace asyncio.to_thread to be synchronous (avoid blocking)
        async def fake_to_thread(fn, *a, **kw):
            return fn(*a, **kw)
        monkeypatch.setattr(d.asyncio, "to_thread", fake_to_thread)

        shutdown_evt.clear()

        async def cancel_soon():
            await asyncio.sleep(0.1)
            shutdown_evt.set()

        await asyncio.gather(
            d.dispatcher_loop(),
            cancel_soon(),
        )
        # If we get here, dispatcher_loop returned cleanly.
    ```

    Update `worker/pyproject.toml` to include `pytest-asyncio` in the dev dependencies (added in Wave 0 already; if missing, add it):
    ```toml
    [project.optional-dependencies]
    dev = [
      "pytest>=8.0,<9.0",
      "pytest-asyncio>=0.24",
      "datamodel-code-generator==0.57.0",
    ]

    [tool.pytest.ini_options]
    testpaths = ["tests"]
    pythonpath = ["."]
    asyncio_mode = "auto"
    addopts = "-x -ra --strict-markers"
    markers = [
      "integration: requires SUPABASE_DEV_DB_URL",
    ]
    ```
  </action>
  <verify>
    <automated>! grep -l "NotImplementedError\\|@pytest.mark.xfail" worker/tests/test_heartbeat.py worker/tests/test_worker_loop.py && grep -q "VT_SECONDS" worker/tests/test_worker_loop.py && grep -q "worker_heartbeats" worker/tests/test_heartbeat.py && grep -q "asyncio_mode" worker/pyproject.toml && cd worker && pytest tests/test_worker_loop.py -x --tb=short -m "not integration"</automated>
  </verify>
  <acceptance_criteria>
    - `worker/tests/test_heartbeat.py` and `worker/tests/test_worker_loop.py` no longer contain `@pytest.mark.xfail` or `raise NotImplementedError`
    - `test_worker_loop.py` asserts `VT_SECONDS == 300` (proves D-00-09)
    - `test_worker_loop.py` mocks PGMQueue and asserts `read_with_poll` is called with exactly `vt=300, qty=1, max_poll_seconds=20`
    - `test_heartbeat.py` calls `_write_row()` and verifies a row exists in `worker_heartbeats` with the test WORKER_ID
    - `worker/pyproject.toml` contains `asyncio_mode = "auto"` under pytest options
    - `cd worker && pytest tests/test_worker_loop.py -x -m "not integration"` exits 0 (4 tests pass; integration test for heartbeat needs DB)
    - When DB available: `cd worker && pytest tests/test_heartbeat.py -x` exits 0
  </acceptance_criteria>
  <done>D-00-09 has a deterministic unit test (no DB needed); D-00-11 item 5 has an integration test against the live worker_heartbeats table.</done>
</task>

</tasks>

<verification>
- After Railway deploy: `curl https://WORKER_DOMAIN/health` returns 200; `/heartbeat` shows a recent row.
- `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from public.worker_heartbeats where last_seen_at > now() - interval '90 seconds'"` returns ≥ 1.
- `cd worker && pytest tests/test_worker_loop.py tests/test_heartbeat.py -x` exits 0 (when DB available).
- D-00-09 + D-00-11 item 5 are both demoable.
</verification>

<success_criteria>
1. Worker deployed to Railway with /health passing.
2. Heartbeat row visible in dev Supabase within 60s of deploy.
3. Dispatcher long-polls q_verify with vt=300 at call site (per D-00-09).
4. SIGTERM gracefully cancels both tasks; pool closes.
5. Worker importable as a Python package; reuses business_checker via editable install.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-05-worker-railway-pgmq-SUMMARY.md` documenting:
- Railway service name + region; healthcheck pass time
- Heartbeat first-row latency observed (target: <30s after deploy)
- Any tembo-pgmq-python 0.10 API surface deviation from the wrapper (DSN vs kwargs)
- Phase 2 follow-up: replace dispatcher archive() stub with verify_row processing; add heartbeat extension during long jobs
- No requirements closed in this plan (worker scaffold supports later phases; D-00-09 + D-00-11 item 5 are demo gates only)
</output>
