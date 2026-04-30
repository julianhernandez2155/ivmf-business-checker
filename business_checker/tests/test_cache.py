"""Unit tests for the SQLite result cache."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from tools.cache import ResultCache, make_cache_key, _normalize_part, _normalize_name


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    """A fresh temporary database path for each test."""
    return str(tmp_path / "test_results.db")


@pytest.fixture
def cache(db_path):
    """A ResultCache backed by a temp database."""
    c = ResultCache(db_path=db_path, ttl_days=30)
    yield c
    c.close()


_SAMPLE_RESULT = {
    "status":     "Active",
    "confidence": "92",
    "evidence":   "Website loads with active e-commerce as of 2025",
    "citations":  ["https://example.com"],
    "cost_usd":   0.006,
    "error":      None,
}


# ── Key generation ────────────────────────────────────────────────────────────

class TestNormalizePart:
    """_normalize_part handles names, cities, and states identically."""

    def test_lowercases(self):
        assert _normalize_part("ACME Corp") == "acme corp"

    def test_strips_punctuation(self):
        assert _normalize_part("AABON 2, INC") == "aabon 2 inc"

    def test_collapses_whitespace(self):
        assert _normalize_part("Smith   Catering") == "smith catering"

    def test_strips_punctuation_and_collapses(self):
        assert _normalize_part("Aabon 2, Inc.") == "aabon 2 inc"

    def test_city_strips_period(self):
        assert _normalize_part("St. Louis") == "st louis"

    def test_city_already_clean(self):
        assert _normalize_part("Birmingham") == "birmingham"

    # _normalize_name is an alias — verify it's the same function
    def test_normalize_name_alias(self):
        assert _normalize_name("AABON 2, INC") == _normalize_part("AABON 2, INC")


class TestMakeCacheKey:
    """Cache key stability and collision resistance."""

    def test_same_inputs_same_key(self):
        k1 = make_cache_key("AABON 2, INC", "Birmingham", "AL")
        k2 = make_cache_key("AABON 2, INC", "Birmingham", "AL")
        assert k1 == k2

    def test_case_insensitive_name(self):
        k1 = make_cache_key("aabon 2, inc", "Birmingham", "AL")
        k2 = make_cache_key("AABON 2, INC", "Birmingham", "AL")
        assert k1 == k2

    def test_case_insensitive_city_state(self):
        k1 = make_cache_key("Acme LLC", "birmingham", "al")
        k2 = make_cache_key("Acme LLC", "Birmingham", "AL")
        assert k1 == k2

    def test_punctuation_variants_match(self):
        k1 = make_cache_key("AABON 2, INC", "Birmingham", "AL")
        k2 = make_cache_key("AABON 2 INC", "Birmingham", "AL")
        assert k1 == k2

    def test_different_business_different_key(self):
        k1 = make_cache_key("Acme LLC", "Syracuse", "NY")
        k2 = make_cache_key("Zenith Corp", "Syracuse", "NY")
        assert k1 != k2

    def test_different_city_different_key(self):
        k1 = make_cache_key("Acme LLC", "Syracuse", "NY")
        k2 = make_cache_key("Acme LLC", "Buffalo", "NY")
        assert k1 != k2

    def test_city_punctuation_variants_match(self):
        k1 = make_cache_key("Acme LLC", "St. Louis", "MO")
        k2 = make_cache_key("Acme LLC", "St Louis", "MO")
        assert k1 == k2

    def test_city_case_and_whitespace_variants_match(self):
        k1 = make_cache_key("Acme LLC", "NEW  YORK", "NY")
        k2 = make_cache_key("Acme LLC", "New York", "NY")
        assert k1 == k2

    def test_returns_64_char_hex(self):
        key = make_cache_key("Acme", "Syracuse", "NY")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


# ── Cache hit/miss ────────────────────────────────────────────────────────────

class TestCacheHitMiss:
    """Basic get/put behavior."""

    def test_miss_on_empty_cache(self, cache):
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result is None

    def test_hit_after_put(self, cache):
        cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result is not None
        assert result["status"] == "Active"
        assert result["confidence"] == "92"

    def test_hit_sets_cost_to_zero(self, cache):
        cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result["cost_usd"] == 0.0

    def test_hit_sets_cached_flag(self, cache):
        cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result.get("_cached") is True

    def test_hit_sets_error_none(self, cache):
        cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result["error"] is None

    def test_citations_round_trip(self, cache):
        cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result["citations"] == ["https://example.com"]

    def test_empty_citations_round_trip(self, cache):
        result_no_cites = {**_SAMPLE_RESULT, "citations": []}
        cache.put("Acme LLC", "Syracuse", "NY", result_no_cites)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result["citations"] == []

    def test_errors_are_not_cached(self, cache):
        error_result = {**_SAMPLE_RESULT, "error": "Request timed out"}
        cache.put("Acme LLC", "Syracuse", "NY", error_result)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result is None

    def test_replace_on_second_put(self, cache):
        cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
        updated = {**_SAMPLE_RESULT, "status": "Likely Closed", "confidence": "85"}
        cache.put("Acme LLC", "Syracuse", "NY", updated)
        result = cache.get("Acme LLC", "Syracuse", "NY")
        assert result["status"] == "Likely Closed"

    def test_different_businesses_do_not_collide(self, cache):
        result_a = {**_SAMPLE_RESULT, "status": "Active"}
        result_b = {**_SAMPLE_RESULT, "status": "Likely Closed"}
        cache.put("Acme LLC", "Syracuse", "NY", result_a)
        cache.put("Zenith Corp", "Syracuse", "NY", result_b)
        assert cache.get("Acme LLC", "Syracuse", "NY")["status"] == "Active"
        assert cache.get("Zenith Corp", "Syracuse", "NY")["status"] == "Likely Closed"


# ── TTL expiry ────────────────────────────────────────────────────────────────

class TestTTL:
    """Cache entries expire correctly based on TTL."""

    def test_fresh_entry_is_returned(self, db_path):
        with ResultCache(db_path=db_path, ttl_days=30) as cache:
            cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
            assert cache.get("Acme LLC", "Syracuse", "NY") is not None

    def test_expired_entry_returns_none(self, db_path):
        """Manually insert a row with an old checked_at to simulate expiry."""
        import sqlite3, json
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                cache_key TEXT PRIMARY KEY, name TEXT NOT NULL,
                city TEXT, state TEXT, status TEXT NOT NULL,
                confidence INTEGER NOT NULL, evidence TEXT NOT NULL,
                citations TEXT, checked_at TEXT NOT NULL, cost_usd REAL DEFAULT 0.0
            )
        """)
        old_date = (datetime.now(timezone.utc) - timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
        key = make_cache_key("Acme LLC", "Syracuse", "NY")
        conn.execute(
            "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?)",
            (key, "Acme LLC", "Syracuse", "NY", "Active", 92,
             "old evidence", json.dumps([]), old_date, 0.006),
        )
        conn.commit()
        conn.close()

        with ResultCache(db_path=db_path, ttl_days=30) as cache:
            assert cache.get("Acme LLC", "Syracuse", "NY") is None

    def test_zero_ttl_always_misses(self, db_path):
        with ResultCache(db_path=db_path, ttl_days=0) as cache:
            cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
            assert cache.get("Acme LLC", "Syracuse", "NY") is None


# ── Context manager ───────────────────────────────────────────────────────────

class TestContextManager:
    def test_context_manager_closes_without_error(self, db_path):
        with ResultCache(db_path=db_path) as cache:
            cache.put("Acme LLC", "Syracuse", "NY", _SAMPLE_RESULT)
        # No exception means __exit__ closed cleanly


# ── Concurrent access ─────────────────────────────────────────────────────────

class TestConcurrentAccess:
    """Each thread gets its own connection — no cursor races under load."""

    def test_concurrent_puts_do_not_raise(self, db_path):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cache = ResultCache(db_path=db_path)
        errors = []

        def write(i):
            try:
                cache.put(f"Business {i}", "St. Louis", "MO", _SAMPLE_RESULT)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(write, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()  # re-raises if write() raised

        cache.close()
        assert errors == [], f"Concurrent puts raised: {errors}"

    def test_concurrent_puts_all_persisted(self, db_path):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cache = ResultCache(db_path=db_path)

        def write(i):
            cache.put(f"Business {i}", "Syracuse", "NY", _SAMPLE_RESULT)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(as_completed([ex.submit(write, i) for i in range(20)]))

        # Verify all 20 are retrievable
        misses = [i for i in range(20)
                  if cache.get(f"Business {i}", "Syracuse", "NY") is None]
        cache.close()
        assert misses == [], f"Missing cache entries for indices: {misses}"
