"""
SQLite-backed result cache for the Business Checker.

Avoids redundant Perplexity API calls for businesses that appear in
multiple datasets.

Cache key (since iter 13): (normalized name, normalized website, city,
state, pipeline_fingerprint). Earlier versions excluded the website on the
assumption that "verdicts shouldn't depend on the listed URL", but in
practice the URL feeds Perplexity context and the website-scrape signal,
both of which materially affect the verdict. Including a 12-char
PipelineConfig fingerprint also ensures different pipelines never share a
cache row — otherwise toggling `v11` ↔ `v12_current_prod` would silently
read each other's cached verdicts.

Migration: cache rows written with the legacy (name, city, state) key
remain on disk but are simply not hit under the new key — they are
harmless and will age out via TTL. No destructive cleanup is performed.

Cache file location: business_checker/cache/results.db (auto-created)
TTL default: 30 days, configurable via CACHE_TTL_DAYS in .env

Usage:
    from tools.pipeline_configs import V11
    cache = ResultCache()
    fp = V11.fingerprint()
    result = cache.get(name, website, city, state, fp)
    if result is None:
        result = check_business(...)
        cache.put(name, website, city, state, fp, result)
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


def _normalize_website(value: str) -> str:
    """Normalize a website URL fragment for cache-key generation.

    Lowercases, strips a leading scheme (http://, https://), a leading
    "www.", and any trailing slash / whitespace. Two listings of the same
    domain with cosmetic URL differences hash to the same key, but a
    genuine domain change does not.
    """
    if not value:
        return ""
    v = value.strip().lower()
    for prefix in ("https://", "http://"):
        if v.startswith(prefix):
            v = v[len(prefix):]
            break
    if v.startswith("www."):
        v = v[4:]
    return v.rstrip("/").strip()


def make_cache_key(
    name: str,
    website: str,
    city: str,
    state: str,
    pipeline_fingerprint: str,
) -> str:
    """Return a SHA-256 cache key for (name, website, city, state, fingerprint).

    Name / city / state are fully normalized (punctuation stripped,
    whitespace collapsed, lowercased) so "AABON 2, INC" and "Aabon 2 Inc"
    hash to the same key. Website is normalized via `_normalize_website`
    (scheme/www/trailing-slash stripped, lowercased) so the same domain in
    different cosmetic forms hashes to the same key, but a genuine domain
    change (data correction, brand redirect) does not.

    The `pipeline_fingerprint` segment (12-char hash from
    `PipelineConfig.fingerprint()`) namespaces the cache by pipeline so
    different toggle sets never read each other's cached verdicts.

    Exported so tests can verify key stability independently of the class.
    """
    normalized = (
        _normalize_part(name)
        + "|"
        + _normalize_website(website)
        + "|"
        + _normalize_part(city)
        + "|"
        + _normalize_part(state)
        + "|"
        + (pipeline_fingerprint or "")
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

    def get(
        self,
        name: str,
        website: str,
        city: str,
        state: str,
        pipeline_fingerprint: str,
    ) -> Optional[dict]:
        """Return a cached result dict, or None if missing/expired.

        A cache hit sets cost_usd=0.0 and adds _cached=True so callers
        can log it distinctly.

        All five key components must match what was passed to `put()` —
        a different `pipeline_fingerprint` (e.g. v10 vs v11) reads as a
        miss, not a hit.
        """
        key    = make_cache_key(name, website, city, state, pipeline_fingerprint)
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

    def put(
        self,
        name: str,
        website: str,
        city: str,
        state: str,
        pipeline_fingerprint: str,
        result: dict,
    ) -> None:
        """Store a successful API result. Errors are never cached."""
        if result.get("error"):
            return

        key        = make_cache_key(name, website, city, state, pipeline_fingerprint)
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
