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

# Test pipeline fingerprint — short stable string used in cache keys.
# Real callers pass `PipelineConfig.fingerprint()`; tests use a fixed value so
# cache hit/miss behavior is decoupled from pipeline_configs.py.
_FP = "testfp123456"
_WEBSITE = "https://acme.example.com"


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
    """Cache key stability and collision resistance.

    Since iter 13 the key signature is
    (name, website, city, state, pipeline_fingerprint). These tests
    exercise both the cosmetic-equivalence properties (same business in
    different casing should hash equally) and the new isolation
    properties (different website or fingerprint must produce a miss).
    """

    def test_same_inputs_same_key(self):
        k1 = make_cache_key("AABON 2, INC", _WEBSITE, "Birmingham", "AL", _FP)
        k2 = make_cache_key("AABON 2, INC", _WEBSITE, "Birmingham", "AL", _FP)
        assert k1 == k2

    def test_case_insensitive_name(self):
        k1 = make_cache_key("aabon 2, inc", _WEBSITE, "Birmingham", "AL", _FP)
        k2 = make_cache_key("AABON 2, INC", _WEBSITE, "Birmingham", "AL", _FP)
        assert k1 == k2

    def test_case_insensitive_city_state(self):
        k1 = make_cache_key("Acme LLC", _WEBSITE, "birmingham", "al", _FP)
        k2 = make_cache_key("Acme LLC", _WEBSITE, "Birmingham", "AL", _FP)
        assert k1 == k2

    def test_punctuation_variants_match(self):
        k1 = make_cache_key("AABON 2, INC", _WEBSITE, "Birmingham", "AL", _FP)
        k2 = make_cache_key("AABON 2 INC", _WEBSITE, "Birmingham", "AL", _FP)
        assert k1 == k2

    def test_different_business_different_key(self):
        k1 = make_cache_key("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        k2 = make_cache_key("Zenith Corp", _WEBSITE, "Syracuse", "NY", _FP)
        assert k1 != k2

    def test_different_city_different_key(self):
        k1 = make_cache_key("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        k2 = make_cache_key("Acme LLC", _WEBSITE, "Buffalo", "NY", _FP)
        assert k1 != k2

    def test_city_punctuation_variants_match(self):
        k1 = make_cache_key("Acme LLC", _WEBSITE, "St. Louis", "MO", _FP)
        k2 = make_cache_key("Acme LLC", _WEBSITE, "St Louis", "MO", _FP)
        assert k1 == k2

    def test_city_case_and_whitespace_variants_match(self):
        k1 = make_cache_key("Acme LLC", _WEBSITE, "NEW  YORK", "NY", _FP)
        k2 = make_cache_key("Acme LLC", _WEBSITE, "New York", "NY", _FP)
        assert k1 == k2

    def test_returns_64_char_hex(self):
        key = make_cache_key("Acme", _WEBSITE, "Syracuse", "NY", _FP)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    # ── Website inclusion (iter 13) ───────────────────────────────────────

    def test_website_scheme_variants_match(self):
        """https://, http://, and bare domain hash to the same key."""
        k1 = make_cache_key("Acme", "https://acme.com", "Syracuse", "NY", _FP)
        k2 = make_cache_key("Acme", "http://acme.com", "Syracuse", "NY", _FP)
        k3 = make_cache_key("Acme", "acme.com", "Syracuse", "NY", _FP)
        assert k1 == k2 == k3

    def test_website_www_prefix_variants_match(self):
        k1 = make_cache_key("Acme", "https://www.acme.com", "Syracuse", "NY", _FP)
        k2 = make_cache_key("Acme", "https://acme.com", "Syracuse", "NY", _FP)
        assert k1 == k2

    def test_website_trailing_slash_match(self):
        k1 = make_cache_key("Acme", "https://acme.com/", "Syracuse", "NY", _FP)
        k2 = make_cache_key("Acme", "https://acme.com", "Syracuse", "NY", _FP)
        assert k1 == k2

    def test_different_website_different_key(self):
        """Same business name + city + state but different domain must miss."""
        k1 = make_cache_key("Acme", "https://acme.com", "Syracuse", "NY", _FP)
        k2 = make_cache_key("Acme", "https://acme-corp.com", "Syracuse", "NY", _FP)
        assert k1 != k2

    # ── Pipeline fingerprint namespacing (iter 13) ────────────────────────

    def test_different_fingerprint_different_key(self):
        """Different pipelines must not share cache rows."""
        k1 = make_cache_key("Acme", _WEBSITE, "Syracuse", "NY", "fp_v10aaa")
        k2 = make_cache_key("Acme", _WEBSITE, "Syracuse", "NY", "fp_v11aaa")
        assert k1 != k2

    def test_same_fingerprint_same_key(self):
        k1 = make_cache_key("Acme", _WEBSITE, "Syracuse", "NY", _FP)
        k2 = make_cache_key("Acme", _WEBSITE, "Syracuse", "NY", _FP)
        assert k1 == k2


# ── Cache hit/miss ────────────────────────────────────────────────────────────

class TestCacheHitMiss:
    """Basic get/put behavior with the iter-13 5-tuple key."""

    def test_miss_on_empty_cache(self, cache):
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result is None

    def test_hit_after_put(self, cache):
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result is not None
        assert result["status"] == "Active"
        assert result["confidence"] == "92"

    def test_hit_sets_cost_to_zero(self, cache):
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result["cost_usd"] == 0.0

    def test_hit_sets_cached_flag(self, cache):
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result.get("_cached") is True

    def test_hit_sets_error_none(self, cache):
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result["error"] is None

    def test_citations_round_trip(self, cache):
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result["citations"] == ["https://example.com"]

    def test_empty_citations_round_trip(self, cache):
        result_no_cites = {**_SAMPLE_RESULT, "citations": []}
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, result_no_cites)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result["citations"] == []

    def test_errors_are_not_cached(self, cache):
        error_result = {**_SAMPLE_RESULT, "error": "Request timed out"}
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, error_result)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result is None

    def test_replace_on_second_put(self, cache):
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        updated = {**_SAMPLE_RESULT, "status": "Likely Closed", "confidence": "85"}
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, updated)
        result = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        assert result["status"] == "Likely Closed"

    def test_different_businesses_do_not_collide(self, cache):
        result_a = {**_SAMPLE_RESULT, "status": "Active"}
        result_b = {**_SAMPLE_RESULT, "status": "Likely Closed"}
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, result_a)
        cache.put("Zenith Corp", _WEBSITE, "Syracuse", "NY", _FP, result_b)
        assert cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)["status"] == "Active"
        assert cache.get("Zenith Corp", _WEBSITE, "Syracuse", "NY", _FP)["status"] == "Likely Closed"

    # ── Iter 13 isolation behaviors ──────────────────────────────────────

    def test_different_website_misses(self, cache):
        """Same business under a different URL is not a hit."""
        cache.put("Acme LLC", "https://acme.com", "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        miss = cache.get("Acme LLC", "https://acme-corp.com", "Syracuse", "NY", _FP)
        assert miss is None

    def test_different_pipeline_fingerprint_misses(self, cache):
        """Pipelines are namespaced — v10 cache row is invisible to v11."""
        cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", "fp_v10aaa", _SAMPLE_RESULT)
        miss = cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", "fp_v11aaa")
        assert miss is None

    def test_normalized_website_is_a_hit(self, cache):
        """Cosmetic URL differences still resolve to a hit."""
        cache.put("Acme LLC", "https://www.acme.com/", "Syracuse", "NY", _FP, _SAMPLE_RESULT)
        hit = cache.get("Acme LLC", "https://acme.com", "Syracuse", "NY", _FP)
        assert hit is not None
        assert hit["status"] == "Active"


# ── TTL expiry ────────────────────────────────────────────────────────────────

class TestTTL:
    """Cache entries expire correctly based on TTL."""

    def test_fresh_entry_is_returned(self, db_path):
        with ResultCache(db_path=db_path, ttl_days=30) as cache:
            cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
            assert cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP) is not None

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
        key = make_cache_key("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP)
        conn.execute(
            "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?)",
            (key, "Acme LLC", "Syracuse", "NY", "Active", 92,
             "old evidence", json.dumps([]), old_date, 0.006),
        )
        conn.commit()
        conn.close()

        with ResultCache(db_path=db_path, ttl_days=30) as cache:
            assert cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP) is None

    def test_zero_ttl_always_misses(self, db_path):
        with ResultCache(db_path=db_path, ttl_days=0) as cache:
            cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
            assert cache.get("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP) is None


# ── Context manager ───────────────────────────────────────────────────────────

class TestContextManager:
    def test_context_manager_closes_without_error(self, db_path):
        with ResultCache(db_path=db_path) as cache:
            cache.put("Acme LLC", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)
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
                cache.put(f"Business {i}", _WEBSITE, "St. Louis", "MO", _FP, _SAMPLE_RESULT)
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
            cache.put(f"Business {i}", _WEBSITE, "Syracuse", "NY", _FP, _SAMPLE_RESULT)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(as_completed([ex.submit(write, i) for i in range(20)]))

        # Verify all 20 are retrievable
        misses = [i for i in range(20)
                  if cache.get(f"Business {i}", _WEBSITE, "Syracuse", "NY", _FP) is None]
        cache.close()
        assert misses == [], f"Missing cache entries for indices: {misses}"
