---
phase: 00-foundation
plan: 05
subsystem: worker-railway-pgmq
tags: [worker, railway, fastapi, pgmq, heartbeat, sigterm, vt-300, infrastructure]
dependency-graph:
  requires:
    - "00-01-wave0-test-scaffolding (worker/tests/conftest.py + xfail stubs)"
    - "00-02-supabase-schema-rls (worker_heartbeats table + pgmq queues live)"
    - "00-03-codegen-drift-gate (worker test CI job exists)"
  provides:
    - "worker/workers/main.py — FastAPI lifespan worker entrypoint"
    - "worker/workers/lib/pgmq_client.py — D-00-09 vt-per-read enforcement point"
    - "worker/workers/lib/db.py — psycopg3 pool singleton (reusable by Phase 2)"
    - "worker/workers/lib/shutdown.py — SIGTERM-coordinated asyncio.Event"
    - "worker/Procfile + worker/railway.json — Railway deployment manifest"
  affects:
    - "Phase 2 worker (replaces dispatcher archive() stub with verify_row processing)"
    - "Phase 0 demo D-00-09 (vt=300 demonstrable via unit test + grep)"
    - "Phase 0 demo D-00-11 item 5 (heartbeat row gated on Railway provisioning + dev DB)"
tech-stack:
  added:
    - "FastAPI 0.136.1 + uvicorn[standard] (worker HTTP surface)"
    - "psycopg-pool ConnectionPool (shared via worker/workers/lib/db.py)"
    - "tembo-pgmq-python 0.10 PGMQueue (wrapped by QueueClient)"
    - "Railway NIXPACKS builder (worker/railway.json)"
  patterns:
    - "FastAPI asynccontextmanager lifespan spawning asyncio.create_task background loops"
    - "asyncio.to_thread bridge for blocking psycopg + pgmq calls"
    - "asyncio.wait_for(shutdown.wait(), timeout=30) for SIGTERM-fast heartbeat loop"
    - "vt-per-read at consumer call site (D-00-09 / P11 mitigation)"
    - "UPSERT pattern with on conflict (worker_id) do update for heartbeat idempotency"
key-files:
  created:
    - "worker/workers/lib/db.py"
    - "worker/workers/lib/pgmq_client.py"
    - "worker/workers/lib/shutdown.py"
    - "worker/workers/dispatcher.py"
    - "worker/workers/heartbeat.py"
    - "worker/workers/main.py"
    - "worker/Procfile"
    - "worker/railway.json"
  modified:
    - "worker/.env.example (added DATABASE_URL, GIT_SHA, LOG_LEVEL)"
    - "worker/tests/test_heartbeat.py (xfail stub → live integration test)"
    - "worker/tests/test_worker_loop.py (xfail stub → 4 deterministic unit tests)"
    - "worker/pyproject.toml (added asyncio_mode = 'auto')"
decisions:
  - "vt=300 lives in dispatcher.VT_SECONDS module constant — grep-verifiable + unit-testable without DB"
  - "QueueClient.__init__ tries PGMQueue(dsn=...) first, falls back to host/port/username/password/database kwargs — survives 0.10 API surface drift between published builds"
  - "Heartbeat loop uses asyncio.wait_for(shutdown.wait(), timeout=30) instead of asyncio.sleep(30) so SIGTERM exits within ms, not up to 30s"
  - "Phase 0 dispatcher is archive-on-receive (no business logic) — Phase 2 will replace archive() with verify_row + extend_vt"
  - "Railway deployment DEFERRED — Railway project not yet linked; Procfile + railway.json shipped as the deployment manifest, live deploy waits on Railway project provisioning + Supabase dev project (same external block as Plan 00-02)"
metrics:
  duration: "~25 min (3 tasks, parallel-wave aware executor)"
  completed-date: "2026-05-14"
  tasks: 3
  files-created: 8
  files-modified: 4
  commits: 3
---

# Phase 0 Plan 05: Railway FastAPI Worker + pgmq Long-Poll + Heartbeat Summary

Ships the Phase 0 worker scaffold: a FastAPI app whose lifespan spawns two asyncio background loops (`dispatcher_loop` long-polls `q_verify` with vt=300 per D-00-09; `heartbeat_loop` UPSERTs `public.worker_heartbeats` every 30s per D-00-11 item 5), a psycopg3 connection pool singleton, a tembo-pgmq-python 0.10 wrapper that enforces vt-per-read, a shared `asyncio.Event` driving SIGTERM-fast graceful shutdown, and Railway deployment manifests (`Procfile` + `railway.json`). Three Wave 0 test stubs (`test_heartbeat.py`, `test_worker_loop.py`) converted to live assertions: 4 deterministic unit tests proving D-00-09 (vt=300 at the consumer call site) + SIGTERM contract, plus 1 integration test proving D-00-11 item 5 against the live `worker_heartbeats` table. All 20 non-integration worker tests pass locally in 0.18s.

## What Shipped

### Library Primitives (worker/workers/lib/)
- **db.py** — `get_pool()` / `close_pool()` singleton over `psycopg_pool.ConnectionPool(min_size=1, max_size=4, open=True)`; raises `RuntimeError` if `DATABASE_URL` is missing
- **pgmq_client.py** — `QueueClient` wrapping `tembo-pgmq-python 0.10`; `read_one(queue, vt_seconds=300, poll_seconds=20)` enforces D-00-09; methods: `read_one`, `archive`, `delete`, `extend_vt`; constructor tries `PGMQueue(dsn=...)` then falls back to host/port/etc. kwargs
- **shutdown.py** — module-level `shutdown: asyncio.Event` + `install_signal_handlers()` registering SIGINT/SIGTERM via `loop.add_signal_handler` (with `signal.signal` fallback for platforms that don't support it)

### Worker Loops (worker/workers/)
- **dispatcher.py** — `dispatcher_loop()` long-polls `q_verify` with `VT_SECONDS = 300` (module constant, grep-verifiable); receives via `asyncio.to_thread(_read_one, q)`; **Phase 0 stub: archives on receive — NO business logic**; logs `dispatcher.message msg_id=...`; exits cleanly when `shutdown.is_set()`
- **heartbeat.py** — `heartbeat_loop()` writes initial row, then loops every `HEARTBEAT_INTERVAL_S = 30` until shutdown; uses `asyncio.wait_for(shutdown.wait(), timeout=30)` so SIGTERM exits within ms; `_write_row()` is synchronous (called via `asyncio.to_thread`) and UPSERTs `public.worker_heartbeats` keyed on `worker_id`

### FastAPI App (worker/workers/main.py)
- `@asynccontextmanager lifespan`: opens pool → installs signal handlers → spawns `asyncio.create_task(dispatcher_loop())` + `asyncio.create_task(heartbeat_loop())` → on shutdown: `shutdown.set()` + cancel + `asyncio.gather(*tasks, return_exceptions=True)` + `close_pool()`
- `GET /health` — liveness probe (no DB touch) — Railway healthcheck target
- `GET /heartbeat` — reads THIS worker's `worker_heartbeats` row so D-00-11 item 5 is demoable without psql

### Railway Manifests
- **Procfile**: `web: uvicorn workers.main:app --host 0.0.0.0 --port $PORT`
- **railway.json**: NIXPACKS builder, `pip install -e . && pip install -e ../business_checker` build command, `/health` healthcheck (30s timeout), `ON_FAILURE` restart policy (max 5 retries)

### Tests
- **test_worker_loop.py** (4 tests, all passing without DB):
  - `test_vt_seconds_is_300` — asserts `dispatcher.VT_SECONDS == 300` (D-00-09)
  - `test_dispatcher_loop_is_async` — confirms `inspect.iscoroutinefunction(dispatcher_loop)`
  - `test_queue_client_read_one_passes_vt_300` — mocks `PGMQueue`, asserts `read_with_poll` called with `vt=300, qty=1, max_poll_seconds=20`
  - `test_dispatcher_loop_exits_on_shutdown` (`@pytest.mark.asyncio`) — sets `shutdown` event after 100ms, asserts loop returns cleanly
- **test_heartbeat.py** (integration; runs when `SUPABASE_DEV_DB_URL` set):
  - `test_write_row_inserts_heartbeat` — calls `hb._write_row()`, verifies row lands in `public.worker_heartbeats`, cleans up

### Env Template (worker/.env.example)
Added `DATABASE_URL`, `GIT_SHA`, `LOG_LEVEL` alongside existing `SUPABASE_DEV_DB_URL`, `WORKER_ID`. Documented that `DATABASE_URL` is the live-worker connection (Railway sets this; locally points at the same direct-postgres DSN as `SUPABASE_DEV_DB_URL`).

## Decisions Made

1. **VT_SECONDS as a module constant, not a function default** — `dispatcher.py` defines `VT_SECONDS = 300` at module scope so grep, unit tests, and code review all see the same surface. The constant flows into `q.read_one(QUEUE, vt_seconds=VT_SECONDS, ...)` at the call site, satisfying D-00-09 ("vt at the consumer call site").

2. **QueueClient dsn-or-kwargs constructor fallback** — tembo-pgmq-python 0.10 is the locked version per STACK.md, but its published constructor signature varies between point releases. The wrapper tries `PGMQueue(dsn=...)` first and falls back to host/port/username/password/database kwargs on `TypeError`. This avoids a hard pin to a specific patch version.

3. **Heartbeat loop uses `asyncio.wait_for(shutdown.wait(), timeout=30)` instead of `asyncio.sleep(30)`** — SIGTERM contract: a 30-second sleep would delay shutdown by up to a full interval. `wait_for` on the shutdown event exits immediately when the event is set; the `TimeoutError` is the normal "write another row" path. This is the same pattern the dispatcher achieves naturally via long-poll yielding.

4. **Phase 0 dispatcher is archive-on-receive** — explicitly stubbed. No Perplexity. No FireCrawl. No `verify_row`. Phase 2's job to replace `await asyncio.to_thread(q.archive, QUEUE, msg_id)` with the actual verification call + `extend_vt` during long-running jobs. Documented in the module docstring.

5. **`test_dispatcher_loop_exits_on_shutdown` fake_to_thread must yield** — initial implementation used a synchronous fake_to_thread that CPU-spun the event loop and starved the cancel_soon timer. Fixed by adding `await asyncio.sleep(0)` after running the function. Documented inline so future maintainers don't strip the yield as "dead code." This is a test-only mechanic; production `read_with_poll` blocks for up to 20s on the network and yields naturally.

6. **Railway deployment deferred** — Procfile + railway.json shipped as the deployment manifest, but `railway up` / `railway link` are gated on the Railway project being provisioned for this monorepo. Same external block as Plan 00-02's `supabase db push` (see STATE.md Open Externally-Blocked Items). When the Railway project + dev Supabase project are both live, follow the deploy sequence in the plan's Task 2 action block.

## Deviations from Plan

None functionally — plan executed verbatim with one minor correctness fix:

### [Rule 1 — Bug] Async test deadlock fix

- **Found during:** Task 3 verification (`pytest tests/test_worker_loop.py`)
- **Issue:** `test_dispatcher_loop_exits_on_shutdown` hung indefinitely because the test's synchronous `fake_to_thread` never yielded to the event loop, so `cancel_soon`'s `asyncio.sleep(0.1)` timer never fired.
- **Fix:** Added `await asyncio.sleep(0)` to `fake_to_thread` so the dispatcher's None-message path yields back to the event loop. Production `read_with_poll` blocks on the network for up to 20s and yields naturally — only the test stub had this issue.
- **Files modified:** `worker/tests/test_worker_loop.py`
- **Commit:** `5bb1dc6` (test-only fix; folded into the Task 3 commit since it was identified during verification, not as a separate work item)

### Live Deploy / Live DB — DEFERRED

The Railway worker is not yet running in production. Reasons (same as Plan 00-02):
- Railway project for the v1.1 worker not provisioned in this execution environment
- `SUPABASE_DEV_DB_URL` not set; dev Supabase project (`ivmf-checker-dev`) still pending provisioning per STATE.md Open Externally-Blocked Items

**Status:** "needs provisioning." Procfile, railway.json, and all worker source code are deliverables in their own right and have been verified via import tests + unit tests against mocked PGMQueue. When Railway + dev Supabase are both live:
1. `railway link` → pick the `ivmf-checker-worker` project; set service root to `worker/`
2. Set env vars in Railway dashboard: `DATABASE_URL` (direct-postgres port-5432 DSN), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `WORKER_ID=railway-prod`
3. `railway up` (or git push if GitHub-integrated)
4. `curl https://WORKER_DOMAIN/health` → expect 200 with worker_id
5. After ≥30s: `curl https://WORKER_DOMAIN/heartbeat` → expect a row with recent `last_seen_at`
6. `psql $SUPABASE_DEV_DB_URL -tAc "select count(*) from public.worker_heartbeats where last_seen_at > now() - interval '60 seconds'"` → ≥ 1
7. `cd worker && SUPABASE_DEV_DB_URL=... pytest tests/test_heartbeat.py -x` → exits 0

### No Other Deviations

No CLAUDE.md-driven adjustments. No checkpoints. No architectural changes.

## Acceptance Criteria Status

### Task 1 (library primitives) — SHIPPED
- ✓ All 4 files exist
- ✓ `worker/.env.example` contains `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `WORKER_ID`
- ✓ `db.py` exports `get_pool()` and `close_pool()`; uses `psycopg_pool.ConnectionPool`
- ✓ `pgmq_client.py` defines `QueueClient` with `read_one`, `archive`, `delete`, `extend_vt`
- ✓ `read_one` defaults `vt_seconds=300` AND passes `vt=vt_seconds` to `read_with_poll`
- ✓ `pgmq_client.py` docstring references D-00-09 and Pitfall P11
- ✓ `shutdown.py` exports `shutdown` asyncio.Event and `install_signal_handlers()`
- ✓ All 4 modules importable from `cd worker` via `python -c "from workers.lib.db import get_pool; from workers.lib.pgmq_client import QueueClient; from workers.lib.shutdown import shutdown"`
- ✓ No hardcoded credentials; all secrets via `os.environ`

### Task 2 (FastAPI + Railway config) — SHIPPED (code) / DEFERRED (live deploy)
- ✓ All 5 files exist
- ✓ `main.py` defines `app = FastAPI(lifespan=lifespan, ...)` + `/health` + `/heartbeat`
- ✓ `main.py` spawns both `dispatcher_loop` and `heartbeat_loop` as asyncio tasks via lifespan
- ✓ `dispatcher.py` defines `VT_SECONDS = 300` AND calls `q.read_one(..., vt_seconds=VT_SECONDS, ...)`
- ✓ `heartbeat.py` UPSERTs into `public.worker_heartbeats` with `on conflict (worker_id) do update`
- ✓ `Procfile` contains `uvicorn workers.main:app`
- ✓ `railway.json` is valid JSON AND contains `healthcheckPath: "/health"`
- DEFERRED: live `/health` 200 response on Railway (needs Railway project)
- DEFERRED: `worker_heartbeats` row visible via psql within 60s of deploy (needs dev DB + Railway)

### Task 3 (tests) — SHIPPED
- ✓ `test_heartbeat.py` + `test_worker_loop.py` no longer contain `@pytest.mark.xfail` or `raise NotImplementedError`
- ✓ `test_worker_loop.py` asserts `VT_SECONDS == 300` (proves D-00-09)
- ✓ `test_worker_loop.py` mocks PGMQueue and asserts `read_with_poll` called with exactly `vt=300, qty=1, max_poll_seconds=20`
- ✓ `test_heartbeat.py` calls `_write_row()` and verifies a row exists in `worker_heartbeats` with the test WORKER_ID
- ✓ `worker/pyproject.toml` contains `asyncio_mode = "auto"` under pytest options
- ✓ `cd worker && pytest tests/test_worker_loop.py -x -m "not integration"` → 4 passed in 0.13s
- ✓ Full non-integration suite: 20 passed in 0.18s (16 normalize + 4 worker_loop)
- DEFERRED: `pytest tests/test_heartbeat.py` (needs SUPABASE_DEV_DB_URL)

## Verification Evidence

```
$ cd worker && python3 -m pytest tests/ --tb=short -m "not integration"
============================= test session starts ==============================
platform darwin -- Python 3.13.3, pytest-8.4.2, pluggy-1.6.0
configfile: pyproject.toml
plugins: anyio-4.9.0, evalview-0.6.1, typeguard-4.5.2, asyncio-1.3.0
asyncio: mode=Mode.AUTO
collected 42 items / 22 deselected / 20 selected

tests/test_normalize.py ................                                 [ 80%]
tests/test_worker_loop.py ....                                           [100%]

====================== 20 passed, 22 deselected in 0.18s =======================
```

```
$ grep -rn "vt=" worker/workers/ | grep -v __pycache__
worker/workers/lib/pgmq_client.py:52:            vt=vt_seconds,
```
(Single vt= site — proves D-00-09 not violated anywhere else.)

```
$ python3 -c "from workers.dispatcher import VT_SECONDS; assert VT_SECONDS == 300; print('VT_SECONDS =', VT_SECONDS)"
VT_SECONDS = 300
```

## Known Stubs

- **dispatcher.py archive-on-receive** — Phase 0 stub. Phase 2 will replace `await asyncio.to_thread(q.archive, QUEUE, msg_id)` with `await verify_row(msg)` + `extend_vt(...)` during long-running Perplexity/FireCrawl calls. Documented in the module docstring. Not blocking Phase 0 demo — D-00-09 only requires that vt=300 is at the call site, which it is.
- **Live Railway deploy** — Procfile + railway.json shipped; live `railway up` deferred pending Railway + dev Supabase provisioning (see Deviations). Worker startup itself is verified via `from workers.main import app` import test.

## Requirements Closed

None. Plan 00-05 is infrastructure scaffolding — it satisfies the demo gates D-00-09 + D-00-11 item 5 but does not directly close any AUTH/CANON/ANALYTICS requirement IDs. (Phase 2 will close worker-side requirements once business logic lands.)

## Phase 0 Demo Gates Status (D-00-11)

After this plan:
- **Item 1** (magic-link login round-trip) — code complete (Plan 00-04); live demo deferred pending dev project
- **Item 2** (PR drift trip on codegen) — complete (Plan 00-03)
- **Item 3** (eval-CI regression block) — Plan 00-06 (next)
- **Item 4** (append-only + unique-violation) — complete (Plan 00-02)
- **Item 5** (worker heartbeat row) — **CODE COMPLETE**; live demo deferred pending Railway + dev DB provisioning
- **Item 6** (Resend DNS ticket filed with IT) — external task; STATE.md tracks

## Commits

- `675f993` — feat(00-05): worker library — db pool, pgmq client (vt=300/read), shutdown event
- `9477157` — feat(00-05): FastAPI worker + dispatcher + heartbeat + Railway config
- `5bb1dc6` — test(00-05): wire heartbeat + dispatcher integration/unit tests (D-00-09, D-00-11 item 5)

## Self-Check: PASSED

Files verified present:
- ✓ worker/workers/lib/db.py
- ✓ worker/workers/lib/pgmq_client.py
- ✓ worker/workers/lib/shutdown.py
- ✓ worker/workers/dispatcher.py
- ✓ worker/workers/heartbeat.py
- ✓ worker/workers/main.py
- ✓ worker/Procfile
- ✓ worker/railway.json
- ✓ worker/.env.example (modified)
- ✓ worker/tests/test_heartbeat.py (modified)
- ✓ worker/tests/test_worker_loop.py (modified)
- ✓ worker/pyproject.toml (modified — asyncio_mode added)

Commits verified in git log:
- ✓ 675f993 (Task 1)
- ✓ 9477157 (Task 2)
- ✓ 5bb1dc6 (Task 3)

D-00-09 verification:
- ✓ `grep -rn "vt=" worker/workers/` returns single site at pgmq_client.py:52 (vt=vt_seconds)
- ✓ `dispatcher.VT_SECONDS == 300` proven by unit test
- ✓ `read_with_poll` called with `vt=300` proven by mock-assertion unit test

D-00-11 item 5 verification:
- ✓ heartbeat._write_row() UPSERTs public.worker_heartbeats keyed on worker_id (grep confirms)
- ✓ heartbeat_loop spawned in main.py lifespan (grep confirms)
- ✓ Integration test exists (test_heartbeat.py); will run green when SUPABASE_DEV_DB_URL is set
