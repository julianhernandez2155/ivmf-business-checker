"""
Business Checker — Headless Concurrent Runner

Use this for large unattended runs (709 records, 20K records, etc.).
Runs in the terminal. No GUI needed. Supports pause via Ctrl+C.

Usage:
    python run_checker.py --input businesses.xlsx --workers 3
    python run_checker.py --input businesses.xlsx --workers 3 --limit 10

Worker count guide (based on your Perplexity account tier):
    --workers 1   Tier 0  (new accounts — 1 QPS)
    --workers 3   Tier 1  (3 QPS)
    --workers 8   Tier 2  (8 QPS)

Check your tier at: https://www.perplexity.ai/settings/api
"""

import argparse
import logging
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import openpyxl
from dotenv import load_dotenv

from tools.cache import ResultCache
from tools.check_business import check_business
from tools.checkpoint import load_checkpoint, save_checkpoint, get_run_summary
from tools.build_output import build_output_excel
from tools.columns import detect_columns

# ── Load environment ──────────────────────────────────────────────────────────

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging(run_dir: str) -> logging.Logger:
    log_path = os.path.join(run_dir, "run.log")
    logger   = logging.getLogger("business_checker")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ── Column helpers ────────────────────────────────────────────────────────────

def get_cell(row: tuple, col_idx) -> str:
    if col_idx is None or col_idx >= len(row):
        return ""
    return str(row[col_idx].value or "").strip()


# ── Main runner ───────────────────────────────────────────────────────────────

def run(input_path: str, run_dir: str, api_key: str,
        col_map: dict, workers: int, limit: int = None,
        cache: ResultCache = None) -> None:

    checkpoint_path = os.path.join(run_dir, "checkpoint.csv")
    logger          = setup_logging(run_dir)

    # Load workbook (read_only for memory efficiency)
    wb = openpyxl.load_workbook(input_path, read_only=True)
    ws = wb.active
    all_rows = list(ws.rows)
    wb.close()

    data_rows = all_rows[1:]
    total      = len(data_rows)

    done       = load_checkpoint(checkpoint_path)
    pending    = [
        (row_idx + 2, row)               # +2: 1-based index + skip header row
        for row_idx, row in enumerate(data_rows)
        if str(row_idx + 2) not in done
    ]

    if limit:
        pending = pending[:limit]

    remaining = len(pending)

    logger.info("=" * 60)
    logger.info("  IVMF Business Operational Status Checker")
    logger.info(f"  File      : {os.path.basename(input_path)}")
    logger.info(f"  Total     : {total}")
    logger.info(f"  Done      : {len(done)}")
    logger.info(f"  Remaining : {remaining}")
    logger.info(f"  Workers   : {workers}")
    logger.info("=" * 60)

    if remaining == 0:
        logger.info("All rows already checked. Nothing to do.")
        return

    # Thread-safe progress + cost counters
    counter_lock    = threading.Lock()
    completed_count = [len(done)]
    total_cost      = [0.0]

    def process_row(row_idx: int, row: tuple) -> dict:
        name    = get_cell(row, col_map.get("name"))
        website = get_cell(row, col_map.get("website"))
        city    = get_cell(row, col_map.get("city"))
        state   = get_cell(row, col_map.get("state"))

        result = check_business(api_key, name, website, city, state, cache=cache)
        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        save_checkpoint(
            checkpoint_path, row_idx, name, website,
            result["status"], result["confidence"],
            result["evidence"], checked_at,
        )

        with counter_lock:
            completed_count[0] += 1
            n = completed_count[0]
            total_cost[0] += result.get("cost_usd", 0.0)
            run_cost = total_cost[0]

        status_icon = {"Active": "✓", "Likely Closed": "✗",
                       "Uncertain": "?", "No Web Presence": "○"}.get(result["status"], "?")
        cache_tag = " [CACHED]" if result.get("_cached") else ""
        logger.info(
            f"[{n}/{total}]{cache_tag} {status_icon} {result['status']} "
            f"({result['confidence']}%) | ${run_cost:.3f} | {name[:35]} — {result['evidence'][:70]}"
        )

        return result

    def run_row(row_idx: int, row: tuple) -> dict:
        """Wrapper that closes the thread-local cache connection when done."""
        try:
            return process_row(row_idx, row)
        finally:
            if cache is not None:
                cache.close()

    # Run concurrently
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_row, row_idx, row): (row_idx, row)
                for row_idx, row in pending
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    row_idx, _ = futures[future]
                    logger.error(f"Worker error on row {row_idx}: {e}")

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Progress saved to checkpoint.")
        logger.info("Re-run the same command to resume.")
        return

    logger.info("=" * 60)
    logger.info("Run complete.")

    summary  = get_run_summary(checkpoint_path)
    run_cost = total_cost[0]
    checked  = completed_count[0] - len(done)  # rows checked this session
    avg_cost = run_cost / checked if checked > 0 else 0

    logger.info(f"  Active          : {summary['Active']}")
    logger.info(f"  Likely Closed   : {summary['Likely Closed']}")
    logger.info(f"  Uncertain       : {summary['Uncertain']}")
    logger.info(f"  No Web Presence : {summary['No Web Presence']}")
    logger.info(f"  Errors          : {summary['Errors']}")
    logger.info(f"  Total checked   : {summary['Total']}")
    logger.info(f"  Session cost    : ${run_cost:.4f}  (avg ${avg_cost:.4f}/check)")
    logger.info("=" * 60)

    # Auto-export results
    stem        = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(run_dir, f"{stem}_Results.xlsx")
    build_output_excel(input_path, output_path, checkpoint_path)
    logger.info(f"Results exported to: {output_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="IVMF Business Checker — headless concurrent runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Worker count guide (Perplexity rate limits):
  --workers 1   Tier 0 (new accounts)
  --workers 3   Tier 1
  --workers 8   Tier 2

Check your tier: https://www.perplexity.ai/settings/api
        """
    )
    parser.add_argument("--input",    required=True, help="Path to input .xlsx file")
    parser.add_argument("--workers",  type=int, default=1,
                        help="Number of concurrent workers (default: 1)")
    parser.add_argument("--limit",    type=int, default=None,
                        help="Only process this many rows (useful for testing)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Skip cache — force fresh API calls for every row")
    args = parser.parse_args()

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY not found.")
        print("Make sure .env exists with your key. See .env.example for the format.")
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f"ERROR: File not found: {args.input}")
        sys.exit(1)

    # Rate limit sanity check
    if args.workers > 3:
        print(f"WARNING: {args.workers} workers requires Perplexity Tier 2+.")
        print("If you hit rate limit errors, reduce --workers.")

    # Create run directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    stem       = os.path.splitext(os.path.basename(args.input))[0]
    timestamp  = datetime.now().strftime("%Y-%m-%d_%H%M")
    run_dir    = os.path.join(script_dir, "Runs", f"{stem}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    # Copy input file into run directory
    dest = os.path.join(run_dir, os.path.basename(args.input))
    shutil.copy2(args.input, dest)

    # Detect columns from header row
    wb      = openpyxl.load_workbook(args.input, read_only=True)
    ws      = wb.active
    headers = [cell.value for cell in next(ws.rows)]
    wb.close()

    col_map = detect_columns(headers)
    missing = [f for f, idx in col_map.items() if idx is None]
    if missing:
        print(f"WARNING: Could not auto-detect columns: {missing}")
        print("Headers found:", headers)
        print("Edit col_map manually in run_checker.py if needed.")

    cache = None if args.no_cache else ResultCache()
    if args.no_cache:
        print("Cache disabled — all rows will make fresh API calls.")

    try:
        run(
            input_path=dest,
            run_dir=run_dir,
            api_key=api_key,
            col_map=col_map,
            workers=args.workers,
            limit=args.limit,
            cache=cache,
        )
    finally:
        if cache is not None:
            cache.close()


if __name__ == "__main__":
    main()
