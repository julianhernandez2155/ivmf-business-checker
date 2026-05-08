"""
Business Checker V2 — Flask Browser Dashboard

Serves a local browser UI for running, monitoring, and exporting business
status checks. Replaces the Tkinter GUI with a real-time web dashboard.

Usage:
    python business_checker_app.py

Opens http://localhost:5000 automatically.
V1 (business_checker_gui.py) is untouched — this is a parallel entry point.
"""

import json
import os
import queue
import shutil
import sys
import threading
import time
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import openpyxl
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_file
from werkzeug.utils import secure_filename

from tools.build_output import build_output_excel
from tools.check_business import check_business
from tools.checkpoint import (
    ERROR_KEYWORDS,
    get_run_summary,
    load_checkpoint,
    rewrite_checkpoint,
    save_checkpoint,
)
from tools.columns import COST_PER_BUSINESS_ESTIMATE, detect_columns

# ── Environment ───────────────────────────────────────────────────────────────

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Path setup ────────────────────────────────────────────────────────────────
# When frozen by PyInstaller, bundled read-only resources (templates, tools/)
# live in sys._MEIPASS. Writable user data (Runs/, uploads) must go next to
# the executable so they survive between launches.

if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR    = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR    = BUNDLE_DIR

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__, template_folder=os.path.join(BUNDLE_DIR, "templates"))

SCRIPT_DIR  = BUNDLE_DIR
UPLOAD_DIR  = os.path.join(APP_DIR, ".tmp_uploads")
RUNS_DIR    = os.path.join(APP_DIR, "Runs")

# ── Global state ──────────────────────────────────────────────────────────────

state = {
    "run_name":        None,
    "run_dir":         None,
    "input_path":      None,
    "col_map":         None,
    "headers":         None,
    "workers":         1,
    "stop_flag":       False,
    "pause_flag":      False,
    "running":         False,
    "run_gen":         0,          # incremented on each new run; old workers exit when theirs is stale
    "total_rows":      0,
    "done_at_start":   0,
    "completed_count": 0,
    "session_cost":    0.0,
    "throughput":      [],       # list of timestamps for ETA calculation
    "uploads":         {},       # upload_id → {path, original_name, total_rows}
    "session_rows":    [],       # in-memory row results for page-reload restore
    "event_queue":     queue.Queue(maxsize=500),
    "api_key":         os.getenv("PERPLEXITY_API_KEY", ""),
}

counter_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _put_event(event_type: str, data: dict) -> None:
    """Push an SSE event onto the queue. Drops if queue is full (client gone)."""
    try:
        state["event_queue"].put_nowait((event_type, data))
    except queue.Full:
        pass


def _is_error_row(row: dict) -> bool:
    conf     = row.get("confidence", "1")
    evidence = row.get("evidence", "")
    return conf == "0" and any(kw in evidence for kw in ERROR_KEYWORDS)


def _compute_eta(total: int, completed: int) -> float | None:
    """Return estimated seconds remaining, or None if insufficient data."""
    window = state["throughput"][-50:]
    if len(window) < 3:
        return None
    elapsed   = window[-1] - window[0]
    rate      = (len(window) - 1) / elapsed if elapsed > 0 else 0
    remaining = total - completed
    return (remaining / rate) if rate > 0 else None


def _get_cell(row_data: dict, field: str) -> str:
    col_map = state["col_map"] or {}
    idx = col_map.get(field)
    if idx is None:
        return ""
    return row_data.get(idx, "")


def _trim_headers(raw_headers: list) -> list:
    """Strip trailing None/empty headers — spreadsheets often have thousands of blank columns."""
    trimmed = list(raw_headers)
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    return trimmed


def _read_headers_and_rows(path: str):
    """Return (headers list, list of row-dicts {col_idx: value}) from xlsx.

    Streams rows from the workbook instead of materializing ws.rows into a list,
    so memory usage scales with row count, not total cells (which can be huge
    when spreadsheets have thousands of empty trailing columns).
    """
    wb  = openpyxl.load_workbook(path, read_only=True)
    ws  = wb.active

    headers   = []
    row_cache = []
    for i, row in enumerate(ws.rows):
        if i == 0:
            headers = _trim_headers([cell.value for cell in row])
            continue
        # Only read columns up to the number of actual headers
        row_cache.append({
            j: str(cell.value or "").strip()
            for j, cell in enumerate(row)
            if j < len(headers)
        })
    wb.close()
    return headers, row_cache


# ── Worker thread ─────────────────────────────────────────────────────────────

def _worker_thread() -> None:
    """
    Background thread that processes pending rows concurrently.
    Mirrors run_checker.py's run() function but emits SSE events instead of
    logging to stdout.
    """
    my_gen          = state["run_gen"]   # capture generation; exit if it changes (new run started)
    api_key         = state["api_key"]
    input_path      = state["input_path"]
    run_dir         = state["run_dir"]
    col_map         = state["col_map"]
    workers         = state["workers"]
    checkpoint_path = os.path.join(run_dir, "checkpoint.csv")

    _put_event("log", {"msg": f"Loading {os.path.basename(input_path)}...", "level": "dim"})

    try:
        headers, row_cache = _read_headers_and_rows(input_path)
    except Exception as e:
        _put_event("server_error", {"message": f"Failed to load input file: {e}"})
        with counter_lock:
            state["running"] = False
        _put_event("stopped", {"completed": state["completed_count"], "total": state["total_rows"]})
        state["event_queue"].put(None)
        return

    total     = len(row_cache)
    done      = load_checkpoint(checkpoint_path)
    pending   = [
        (row_idx + 2, row_data)
        for row_idx, row_data in enumerate(row_cache)
        if str(row_idx + 2) not in done
    ]

    with counter_lock:
        state["total_rows"]    = total
        state["done_at_start"] = len(done)
        state["completed_count"] = len(done)

    # On resume, hydrate session_rows from the existing checkpoint so the UI
    # shows all previously completed rows immediately — not just the current session.
    if done:
        prior_rows = []
        for key, r in sorted(done.items(), key=lambda kv: int(kv[0])):
            cache_idx = int(key) - 2   # row_cache is 0-based; checkpoint keys are row_idx+2
            row_data_lookup = row_cache[cache_idx] if 0 <= cache_idx < len(row_cache) else {}
            city_val  = row_data_lookup.get(col_map.get("city"),  "") if col_map.get("city")  is not None else ""
            state_val = row_data_lookup.get(col_map.get("state"), "") if col_map.get("state") is not None else ""
            prior_rows.append({
                "row_index":    int(key),
                "name":         r.get("name", ""),
                "city":         city_val,
                "state":        state_val,
                "status":       r.get("AI_Status", ""),
                "confidence":   r.get("AI_Confidence", ""),
                "evidence":     r.get("AI_Evidence", ""),
                "cost_usd":     0.0,
                "completed":    len(done),
                "total":        total,
                "session_cost": 0.0,
                "eta_secs":     0,
            })
        with counter_lock:
            state["session_rows"] = prior_rows

    _put_event("run_started", {
        "run_name":      state["run_name"],
        "total_rows":    total,
        "done_at_start": len(done),
        "workers":       workers,
        "session_rows":  state["session_rows"],
    })
    _put_event("log", {
        "msg":   f"Run started — {total} total, {len(done)} already done, {len(pending)} remaining",
        "level": "info",
    })

    if not pending:
        _put_event("log", {"msg": "All rows already checked.", "level": "success"})
        summary = get_run_summary(checkpoint_path)
        _put_event("run_complete", {"summary": summary, "session_cost": 0.0})
        with counter_lock:
            state["running"] = False
        state["event_queue"].put(None)
        return

    def process_row(row_idx: int, row_data: dict) -> None:
        # Pause loop
        while state["pause_flag"] and not state["stop_flag"] and state["run_gen"] == my_gen:
            time.sleep(0.3)

        if state["stop_flag"] or state["run_gen"] != my_gen:
            return

        name    = row_data.get(col_map.get("name"),    "") if col_map.get("name")    is not None else ""
        website = row_data.get(col_map.get("website"), "") if col_map.get("website") is not None else ""
        city    = row_data.get(col_map.get("city"),    "") if col_map.get("city")    is not None else ""
        state_  = row_data.get(col_map.get("state"),   "") if col_map.get("state")   is not None else ""

        result     = check_business(api_key, name, website, city, state_)
        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Re-check after the API call. If a new run started (gen changed),
        # checkpoint_path was captured at thread start and still points to the
        # OLD run's directory — save the paid-for result there before exiting.
        if state["run_gen"] != my_gen:
            save_checkpoint(
                checkpoint_path, row_idx, name, website,
                result["status"], result["confidence"],
                result["evidence"], checked_at,
                requires_review=bool(result.get("requires_review", False)),
                review_reason=str(result.get("review_reason") or ""),
            )
            return

        # If stop was requested during this API call, still save the result.
        # The user already paid for it — don't waste it. Just skip the UI event.
        save_checkpoint(
            checkpoint_path, row_idx, name, website,
            result["status"], result["confidence"],
            result["evidence"], checked_at,
        )

        with counter_lock:
            state["completed_count"] += 1
            state["session_cost"]    += result.get("cost_usd", 0.0)
            state["throughput"].append(time.time())
            if len(state["throughput"]) > 200:
                state["throughput"] = state["throughput"][-100:]

            completed    = state["completed_count"]
            session_cost = state["session_cost"]

        # If stopped mid-flight, the checkpoint is saved but skip the UI update
        if state["stop_flag"]:
            return

        eta = _compute_eta(total, completed)

        row_event = {
            "row_index":    row_idx,
            "name":         name,
            "city":         city,
            "state":        state_,
            "status":       result["status"],
            "confidence":   result["confidence"],
            "evidence":     result["evidence"],
            "cost_usd":     result.get("cost_usd", 0.0),
            "completed":    completed,
            "total":        total,
            "session_cost": session_cost,
            "eta_secs":     eta,
        }
        _put_event("row_result", row_event)

        with counter_lock:
            state["session_rows"].append(row_event)

        icon = {"Active": "✓", "Likely Closed": "✗", "Uncertain": "?",
                "No Web Presence": "○"}.get(result["status"], "?")
        _put_event("log", {
            "msg":   f"[{completed}/{total}] {icon} {result['status']} ({result['confidence']}%) | {name[:40]}",
            "level": "success" if result["status"] == "Active" else
                     "error"   if result["status"] == "Likely Closed" else
                     "warning" if result["status"] == "Uncertain" else "dim",
        })

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_row, row_idx, row_data): row_idx
                for row_idx, row_data in pending
            }
            for future in as_completed(futures):
                if state["stop_flag"] or state["run_gen"] != my_gen:
                    break
                try:
                    future.result()
                except Exception as e:
                    row_idx = futures[future]
                    _put_event("log", {"msg": f"Worker error on row {row_idx}: {e}", "level": "error"})
    except Exception as e:
        _put_event("server_error", {"message": f"Executor error: {e}"})

    # Only update shared state if we're still the active generation.
    # If run_gen changed, a new run has already claimed running=True — don't touch it.
    with counter_lock:
        if state["run_gen"] == my_gen:
            state["running"] = False

    if state["stop_flag"] and state["run_gen"] == my_gen:
        _put_event("stopped", {
            "completed": state["completed_count"],
            "total":     state["total_rows"],
        })
        _put_event("log", {"msg": "Run stopped. Progress saved to checkpoint.", "level": "warning"})
    else:
        summary      = get_run_summary(checkpoint_path)
        session_cost = state["session_cost"]
        _put_event("run_complete", {"summary": summary, "session_cost": session_cost})
        _put_event("log", {"msg": "Run complete!", "level": "success"})

        # Auto-export
        try:
            stem        = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(run_dir, f"{stem}_Results.xlsx")
            build_output_excel(input_path, output_path, checkpoint_path)
            _put_event("log", {"msg": f"Results exported: {os.path.basename(output_path)}", "level": "success"})
        except Exception as e:
            _put_event("log", {"msg": f"Auto-export failed: {e}", "level": "error"})

    state["event_queue"].put(None)


# ── Routes — pages ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from flask import render_template
    return render_template(
        "index.html",
        api_key_loaded=bool(state["api_key"]),
    )


# ── Routes — API ──────────────────────────────────────────────────────────────

@app.route("/api/key", methods=["GET"])
def api_key_status():
    """Return whether an API key is configured (never exposes the key itself)."""
    return jsonify({"configured": bool(state["api_key"])})


@app.route("/api/key", methods=["POST"])
def api_key_set():
    """Set or clear the API key server-side."""
    data = request.get_json(silent=True) or {}
    key  = data.get("api_key", "").strip()
    state["api_key"] = key
    return jsonify({"configured": bool(key)})


@app.route("/api/key/test", methods=["POST"])
def api_key_test():
    """Synchronous API key validation."""
    data    = request.get_json(silent=True) or {}
    api_key = data.get("api_key", "").strip()
    if not api_key:
        return jsonify({"ok": False, "message": "No key provided."})

    import requests as req
    try:
        t0   = time.time()
        resp = req.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "sonar", "messages": [{"role": "user", "content": "ping"}]},
            timeout=12,
        )
        elapsed = round((time.time() - t0) * 1000)
        if resp.status_code == 200:
            state["api_key"] = api_key
            return jsonify({"ok": True, "message": "Key valid.", "elapsed": elapsed})
        elif resp.status_code == 401:
            return jsonify({"ok": False, "message": "Invalid API key (401).", "elapsed": elapsed})
        else:
            return jsonify({"ok": False, "message": f"Unexpected status {resp.status_code}.", "elapsed": elapsed})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)[:120]})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Receive .xlsx file, return headers and column detection."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    f = request.files["file"]
    if not f.filename.endswith(".xlsx"):
        return jsonify({"error": "Only .xlsx files are supported."}), 400

    upload_id     = str(uuid.uuid4())
    safe_name     = secure_filename(f.filename)
    upload_path   = os.path.join(UPLOAD_DIR, f"{upload_id}_{safe_name}")
    f.save(upload_path)

    try:
        wb      = openpyxl.load_workbook(upload_path, read_only=True)
        ws      = wb.active
        headers    = []
        total_rows = 0
        for i, row in enumerate(ws.rows):
            if i == 0:
                headers = _trim_headers([str(cell.value or "") for cell in row])
            else:
                total_rows += 1
        wb.close()
    except Exception as e:
        os.unlink(upload_path)
        return jsonify({"error": f"Could not read file: {e}"}), 400

    detected = detect_columns(headers)
    state["uploads"][upload_id] = {
        "path":          upload_path,
        "original_name": safe_name,
        "total_rows":    total_rows,
    }

    return jsonify({
        "upload_id":     upload_id,
        "headers":       headers,
        "total_rows":    total_rows,
        "detected":      detected,
        "cost_estimate": COST_PER_BUSINESS_ESTIMATE,
    })


@app.route("/api/runs")
def api_runs():
    """List existing run folders."""
    os.makedirs(RUNS_DIR, exist_ok=True)
    runs = []
    for name in sorted(os.listdir(RUNS_DIR), reverse=True):
        run_dir = os.path.join(RUNS_DIR, name)
        if not os.path.isdir(run_dir):
            continue
        checkpoint_path = os.path.join(run_dir, "checkpoint.csv")
        summary         = get_run_summary(checkpoint_path) if os.path.exists(checkpoint_path) else {}

        # Try run_meta.json first (fast), fall back to reading the Excel (slow)
        meta_path = os.path.join(run_dir, "run_meta.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        total = meta.get("total_rows", 0)
        if not total:
            # Backward compat: older runs without run_meta.json
            for fname in os.listdir(run_dir):
                if fname.endswith(".xlsx") and not fname.endswith("_Results.xlsx"):
                    try:
                        wb    = openpyxl.load_workbook(os.path.join(run_dir, fname), read_only=True)
                        ws    = wb.active
                        total = max(0, ws.max_row - 1) if ws.max_row else 0
                        wb.close()
                    except Exception:
                        pass
                    break

        has_results = any(f.endswith("_Results.xlsx") for f in os.listdir(run_dir))
        runs.append({
            "name":          name,
            "display_label": meta.get("display_label"),
            "started_at":    meta.get("started_at"),
            "done":          summary.get("Total", 0),
            "total":         total,
            "errors":        summary.get("Errors", 0),
            "has_results":   has_results,
        })
    return jsonify(runs)


@app.route("/api/runs/<run_name>", methods=["DELETE"])
def api_run_delete(run_name: str):
    """Delete a run folder and all its contents."""
    if state["running"] and state["run_name"] == run_name:
        return jsonify({"error": "Cannot delete a run that is currently in progress."}), 409

    run_dir = os.path.join(RUNS_DIR, run_name)
    if not os.path.isdir(run_dir):
        return jsonify({"error": "Run not found."}), 404

    shutil.rmtree(run_dir)
    return jsonify({"ok": True})


@app.route("/api/runs/<run_name>/info")
def api_run_info(run_name: str):
    """Get details about an existing run folder."""
    run_dir = os.path.join(RUNS_DIR, run_name)
    if not os.path.isdir(run_dir):
        return jsonify({"error": "Run not found."}), 404

    input_path = None
    for fname in os.listdir(run_dir):
        if fname.endswith(".xlsx") and not fname.endswith("_Results.xlsx"):
            input_path = os.path.join(run_dir, fname)
            break

    if not input_path:
        return jsonify({"error": "No input .xlsx found in run folder."}), 404

    try:
        wb      = openpyxl.load_workbook(input_path, read_only=True)
        ws      = wb.active
        headers    = []
        total_rows = 0
        for i, row in enumerate(ws.rows):
            if i == 0:
                headers = _trim_headers([str(cell.value or "") for cell in row])
            else:
                total_rows += 1
        wb.close()
    except Exception as e:
        return jsonify({"error": f"Could not read file: {e}"}), 400

    detected   = detect_columns(headers)
    checkpoint = os.path.join(run_dir, "checkpoint.csv")
    done       = load_checkpoint(checkpoint) if os.path.exists(checkpoint) else {}

    return jsonify({
        "run_name":   run_name,
        "input_path": input_path,
        "headers":    headers,
        "detected":   detected,
        "total_rows": total_rows,
        "done_count": len(done),
        "cost_estimate": COST_PER_BUSINESS_ESTIMATE,
    })


@app.route("/api/run/start", methods=["POST"])
def api_run_start():
    """Create run folder from upload, spawn worker thread."""
    if state["running"]:
        return jsonify({"error": "A run is already in progress."}), 409

    data          = request.get_json(silent=True) or {}
    upload_id     = data.get("upload_id", "")
    col_map       = data.get("col_map", {})
    workers       = int(data.get("workers", 1))
    api_key       = data.get("api_key", state["api_key"]).strip()
    display_label = data.get("display_label", "").strip()

    if not api_key:
        return jsonify({"error": "No API key provided."}), 400

    upload = state["uploads"].get(upload_id)
    if not upload:
        return jsonify({"error": "Upload not found. Please re-upload the file."}), 400

    # Convert col_map values to int (JSON sends them as strings sometimes)
    col_map_int = {k: int(v) if v is not None else None for k, v in col_map.items()}

    # Create run folder
    os.makedirs(RUNS_DIR, exist_ok=True)
    stem      = os.path.splitext(upload["original_name"])[0]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffix    = uuid.uuid4().hex[:4]
    run_name  = f"{stem}_{timestamp}_{suffix}"
    run_dir   = os.path.join(RUNS_DIR, run_name)
    os.makedirs(run_dir, exist_ok=True)

    dest = os.path.join(run_dir, upload["original_name"])
    shutil.copy2(upload["path"], dest)

    # Write run metadata for the run picker UI
    meta = {
        "display_label": display_label or None,
        "auto_name":     run_name,
        "started_at":    datetime.now().isoformat(timespec="seconds"),
        "total_rows":    upload.get("total_rows", 0),
    }
    with open(os.path.join(run_dir, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # Clean up tmp upload
    try:
        os.unlink(upload["path"])
    except OSError:
        pass
    del state["uploads"][upload_id]

    _reset_run_state(
        run_name=run_name,
        run_dir=run_dir,
        input_path=dest,
        col_map=col_map_int,
        workers=workers,
        api_key=api_key,
    )
    threading.Thread(target=_worker_thread, daemon=True).start()
    return jsonify({"ok": True, "run_name": run_name})


@app.route("/api/run/resume", methods=["POST"])
def api_run_resume():
    """Resume an existing run folder."""
    if state["running"]:
        return jsonify({"error": "A run is already in progress."}), 409

    data     = request.get_json(silent=True) or {}
    run_name = data.get("run_name", "")
    col_map  = data.get("col_map", {})
    workers  = int(data.get("workers", 1))
    api_key  = data.get("api_key", state["api_key"]).strip()

    if not api_key:
        return jsonify({"error": "No API key provided."}), 400

    run_dir = os.path.join(RUNS_DIR, run_name)
    if not os.path.isdir(run_dir):
        return jsonify({"error": "Run folder not found."}), 404

    input_path = None
    for fname in os.listdir(run_dir):
        if fname.endswith(".xlsx") and not fname.endswith("_Results.xlsx"):
            input_path = os.path.join(run_dir, fname)
            break

    if not input_path:
        return jsonify({"error": "No input .xlsx found in run folder."}), 404

    col_map_int = {k: int(v) if v is not None else None for k, v in col_map.items()}

    _reset_run_state(
        run_name=run_name,
        run_dir=run_dir,
        input_path=input_path,
        col_map=col_map_int,
        workers=workers,
        api_key=api_key,
    )
    threading.Thread(target=_worker_thread, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/run/stop", methods=["POST"])
def api_run_stop():
    with counter_lock:
        state["stop_flag"] = True
        state["running"]   = False   # immediately unblock /start; old worker will exit via run_gen check
    return jsonify({"ok": True})


@app.route("/api/run/pause", methods=["POST"])
def api_run_pause():
    state["pause_flag"] = not state["pause_flag"]
    event_type = "paused" if state["pause_flag"] else "resumed"
    _put_event(event_type, {"ts": time.time()})
    return jsonify({"ok": True, "paused": state["pause_flag"]})


@app.route("/api/run/retry_failed", methods=["POST"])
def api_run_retry_failed():
    """Remove error rows from checkpoint so they'll be re-checked on next run."""
    if state["running"]:
        return jsonify({"error": "Cannot modify checkpoint while run is in progress."}), 409

    run_dir = state["run_dir"]
    if not run_dir:
        return jsonify({"error": "No run loaded."}), 400

    checkpoint_path = os.path.join(run_dir, "checkpoint.csv")
    if not os.path.exists(checkpoint_path):
        return jsonify({"error": "No checkpoint file found."}), 404

    done    = load_checkpoint(checkpoint_path)
    keep    = []
    removed = 0
    for row in done.values():
        conf     = row.get("AI_Confidence", "1")
        evidence = row.get("AI_Evidence", "")
        if conf == "0" and any(kw in evidence for kw in ERROR_KEYWORDS):
            removed += 1
        else:
            keep.append(row)

    rewrite_checkpoint(checkpoint_path, keep)
    return jsonify({"ok": True, "removed": removed})


@app.route("/api/run/export", methods=["POST"])
def api_run_export():
    """Build and return the path to the results xlsx."""
    run_dir    = state["run_dir"]
    input_path = state["input_path"]
    if not run_dir or not input_path:
        return jsonify({"error": "No run loaded."}), 400

    checkpoint_path = os.path.join(run_dir, "checkpoint.csv")
    if not os.path.exists(checkpoint_path):
        return jsonify({"error": "No checkpoint file found."}), 404

    stem        = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(run_dir, f"{stem}_Results.xlsx")

    try:
        build_output_excel(input_path, output_path, checkpoint_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Copy to Downloads with a unique name so repeated exports never collide
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    downloads_copy = None
    if os.path.isdir(downloads_dir):
        stem_out   = os.path.splitext(os.path.basename(output_path))[0]
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_name  = f"{stem_out}_{timestamp}.xlsx"
        downloads_copy = os.path.join(downloads_dir, dest_name)
        try:
            shutil.copy2(output_path, downloads_copy)
        except OSError:
            downloads_copy = None

    return jsonify({
        "ok": True,
        "filename": os.path.basename(output_path),
        "run_name": state["run_name"],
        "downloads_path": downloads_copy,
    })


@app.route("/api/run/download/<run_name>/<filename>")
def api_run_download(run_name: str, filename: str):
    """Download a file from a run folder."""
    # Basic path traversal guard
    safe_run  = secure_filename(run_name)
    safe_file = secure_filename(filename)
    filepath  = os.path.join(RUNS_DIR, safe_run, safe_file)
    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found."}), 404
    return send_file(filepath, as_attachment=True)


@app.route("/api/stream")
def api_stream():
    """SSE endpoint — streams all live events to the browser."""

    def generate():
        # Drain any stale events before the client connected
        while not state["event_queue"].empty():
            try:
                state["event_queue"].get_nowait()
            except queue.Empty:
                break

        while True:
            try:
                item = state["event_queue"].get(timeout=15)
                if item is None:
                    # Sentinel — run is complete, close stream
                    yield "event: done\ndata: {}\n\n"
                    return
                event_type, data = item
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            except queue.Empty:
                # Heartbeat to keep the connection alive
                yield f"data: {json.dumps({'ts': time.time()})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/state")
def api_state():
    """Full state snapshot for browser reconnect."""
    run_dir    = state["run_dir"]
    checkpoint_path = os.path.join(run_dir, "checkpoint.csv") if run_dir else None
    summary    = get_run_summary(checkpoint_path) if (checkpoint_path and os.path.exists(checkpoint_path)) else {}

    return jsonify({
        "run_name":        state["run_name"],
        "running":         state["running"],
        "paused":          state["pause_flag"],
        "total_rows":      state["total_rows"],
        "done_at_start":   state["done_at_start"],
        "completed_count": state["completed_count"],
        "session_cost":    state["session_cost"],
        "summary":         summary,
        "session_rows":    state["session_rows"],
        "headers":         state["headers"],
        "col_map":         state["col_map"],
        "api_key_loaded":  bool(state["api_key"]),
    })


# ── Internal helpers ──────────────────────────────────────────────────────────

def _reset_run_state(*, run_name, run_dir, input_path, col_map, workers, api_key):
    """Reset global state for a new or resumed run."""
    # Drain the event queue
    while not state["event_queue"].empty():
        try:
            state["event_queue"].get_nowait()
        except queue.Empty:
            break

    with counter_lock:
        state.update({
            "run_name":        run_name,
            "run_dir":         run_dir,
            "input_path":      input_path,
            "col_map":         col_map,
            "workers":         workers,
            "run_gen":         state["run_gen"] + 1,
            "stop_flag":       False,
            "pause_flag":      False,
            "running":         True,
            "total_rows":      0,
            "done_at_start":   0,
            "completed_count": 0,
            "session_cost":    0.0,
            "throughput":      [],
            "session_rows":    [],
            "api_key":         api_key,
        })


# ── Entry point ───────────────────────────────────────────────────────────────

def ensure_dirs():
    """Create writable directories if missing."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(RUNS_DIR, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5001")).start()
    print("Business Checker V2 — starting at http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, threaded=True, debug=False)
