"""
SQLite-backed result cache for the Business Checker.

Avoids redundant Perplexity API calls for businesses that appear in
multiple datasets. Cache key is (normalized name, city, state) — website
is intentionally excluded so the same business is recognized regardless of
URL format or variation.

Cache file location: Business Checker/cache/results.db (auto-created)
TTL default: 30 days, configurable via CACHE_TTL_DAYS in .env

Usage:
    cache = ResultCache()
    result = cache.get(name, city, state)
    if result is None:
        result = check_business(...)
        cache.put(name, city, state, result)
    cache.close()

    # Or as a context manager:
    with ResultCache() as cache:
        ...
"""

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional


# ── Config ────────────────────────────────────────────────────────────────────

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "cache", "results.db"
)
_DEFAULT_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "30"))

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS results (
    cache_key   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT,
    state       TEXT,
    status      TEXT NOT NULL,
    confidence  INTEGER NOT NULL,
    evidence    TEXT NOT NULL,
    citations   TEXT,
    checked_at  TEXT NOT NULL,
    cost_usd    REAL DEFAULT 0.0
);
"""


# ── Key generation ────────────────────────────────────────────────────────────

def _normalize_part(value: str) -> str:
    """Normalize a name/city/state fragment for cache key generation.

    Strips punctuation, collapses whitespace, lowercases.
    "St. Louis" → "st louis"
    "AABON 2, INC" → "aabon 2 inc"
    """
    value = value.lower()
    value = re.sub(r"[^\w\s]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


# Keep the old name as an alias so existing callers aren't broken
_normalize_name = _normalize_part


def make_cache_key(name: str, city: str, state: str) -> str:
    """Return a SHA-256 cache key for (normalized name, city, state).

    All three parts are fully normalized — punctuation stripped, whitespace
    collapsed, lowercased — so "AABON 2, INC" and "Aabon 2 Inc" hash to the
    same key, and "St. Louis" and "St Louis" hash to the same key.

    Exported so tests can verify key stability independently of the class.
    """
    normalized = (
        _normalize_part(name)
        + "|"
        + _normalize_part(city)
        + "|"
        + _normalize_part(state)
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ── Cache class ───────────────────────────────────────────────────────────────

class ResultCache:
    """Thread-safe SQLite cache for business check results.

    Each thread gets its own SQLite connection via threading.local().
    SQLite WAL mode allows concurrent readers across connections; writes
    are serialized by SQLite's internal locking.
    """

    def __init__(
        self,
        db_path: str = _DEFAULT_DB_PATH,
        ttl_days: int = _DEFAULT_TTL_DAYS,
    ) -> None:
        self.db_path = db_path
        self.ttl_days = ttl_days
        self._local = threading.local()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        # Initialize the schema on the calling thread's connection
        self._get_conn()

    def _get_conn(self) -> sqlite3.Connection:
        """Return this thread's SQLite connection, creating it if needed."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(_CREATE_TABLE)
            conn.commit()
            self._local.conn = conn
        return conn

    def get(self, name: str, city: str, state: str) -> Optional[dict]:
        """Return a cached result dict, or None if missing/expired.

        A cache hit sets cost_usd=0.0 and adds _cached=True so callers
        can log it distinctly.
        """
        key    = make_cache_key(name, city, state)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.ttl_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        row = self._get_conn().execute(
            "SELECT status, confidence, evidence, citations, cost_usd "
            "FROM results WHERE cache_key = ? AND checked_at > ?",
            (key, cutoff),
        ).fetchone()

        if row is None:
            return None

        status, confidence, evidence, citations_json, _ = row
        citations = json.loads(citations_json) if citations_json else []

        return {
            "status":     status,
            "confidence": str(confidence),
            "evidence":   evidence,
            "citations":  citations,
            "cost_usd":   0.0,
            "error":      None,
            "_cached":    True,
        }

    def put(self, name: str, city: str, state: str, result: dict) -> None:
        """Store a successful API result. Errors are never cached."""
        if result.get("error"):
            return

        key        = make_cache_key(name, city, state)
        checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        citations  = json.dumps(result.get("citations", []))

        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO results
                (cache_key, name, city, state, status, confidence,
                 evidence, citations, checked_at, cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                name,
                city or "",
                state or "",
                result["status"],
                int(result["confidence"]),
                result["evidence"],
                citations,
                checked_at,
                result.get("cost_usd", 0.0),
            ),
        )
        conn.commit()

    def close(self) -> None:
        """Close this thread's connection. Call from each thread that used the cache."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
