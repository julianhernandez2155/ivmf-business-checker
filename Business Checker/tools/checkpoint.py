"""
Checkpoint utilities — shared by the GUI and headless runner.

All write operations are protected by a threading.Lock so multiple
concurrent workers can safely call save_checkpoint() at the same time.
"""

import csv
import os
import threading

_lock = threading.Lock()

FIELDNAMES = [
    "row_index", "name", "website",
    "AI_Status", "AI_Confidence", "AI_Evidence", "AI_Checked_At",
]

ERROR_KEYWORDS = ["Parse error", "No text response", "Error:", "Failed after"]


def load_checkpoint(path: str) -> dict:
    """
    Load a checkpoint CSV and return a dict keyed by row_index string.
    Returns an empty dict if the file doesn't exist yet.
    """
    result = {}
    if not os.path.exists(path):
        return result
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["row_index"]] = row
    return result


def save_checkpoint(path: str, row_index, name, website,
                    status, confidence, evidence, checked_at) -> None:
    """
    Append one result row to the checkpoint CSV.
    Thread-safe — safe to call from multiple concurrent workers.
    """
    with _lock:
        file_exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "row_index":     str(row_index),
                "name":          name,
                "website":       website,
                "AI_Status":     status,
                "AI_Confidence": confidence,
                "AI_Evidence":   evidence,
                "AI_Checked_At": checked_at,
            })


def rewrite_checkpoint(path: str, rows: list) -> None:
    """
    Overwrite the checkpoint with a new list of rows.
    Used by the 'Retry Failed' feature to remove failed rows.

    Writes to a temp file first, then atomically replaces the original.
    A backup (.bak) is kept in case rollback is needed.
    """
    tmp_path = path + ".tmp"
    bak_path = path + ".bak"
    with _lock:
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

        # Keep a backup of the current checkpoint before replacing
        if os.path.exists(path):
            try:
                os.replace(path, bak_path)
            except OSError:
                pass
        os.replace(tmp_path, path)


def get_run_summary(checkpoint_path: str) -> dict:
    """
    Return a count breakdown of results from a checkpoint file.
    """
    done = load_checkpoint(checkpoint_path)
    summary = {
        "Active": 0,
        "Likely Closed": 0,
        "Uncertain": 0,
        "No Web Presence": 0,
        "Errors": 0,
        "Total": len(done),
    }
    for r in done.values():
        status = r.get("AI_Status", "")
        conf   = r.get("AI_Confidence", "1")
        is_error = (
            conf == "0" and
            any(kw in r.get("AI_Evidence", "") for kw in ERROR_KEYWORDS)
        )
        if is_error:
            summary["Errors"] += 1
        elif status in summary:
            summary[status] += 1
        else:
            summary["Uncertain"] += 1
    return summary
