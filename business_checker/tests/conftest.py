"""Shared pytest fixtures for the IVMF Business Checker test suite.

This conftest.py is auto-discovered by pytest and provides fixtures available
to every test in the tests/ tree. Keep it small — fixtures used by only one
file should stay in that file.
"""

import os
from pathlib import Path

import pytest


@pytest.fixture
def fake_perplexity_key(monkeypatch):
    """Set a deterministic fake Perplexity API key for the duration of one test.

    Use this when a test exercises code that reads PERPLEXITY_API_KEY from env
    but you want to ensure no live API call is made (combine with mocked
    requests.post or similar).
    """
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-fake-key-do-not-use")
    yield "pplx-test-fake-key-do-not-use"


@pytest.fixture
def fake_firecrawl_key(monkeypatch):
    """Set a deterministic fake Firecrawl API key for tests that need one."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-fake-key-do-not-use")
    yield "fc-test-fake-key-do-not-use"


@pytest.fixture
def no_firecrawl_key(monkeypatch):
    """Ensure FIRECRAWL_API_KEY is unset so the scraper falls back to direct HTTP."""
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    yield


@pytest.fixture
def project_root() -> Path:
    """Absolute path to the business_checker package root.

    Useful for tests that need to read fixture files relative to the package.
    """
    return Path(__file__).parent.parent


@pytest.fixture
def sample_business() -> dict:
    """A canonical sample business record for tests that need one."""
    return {
        "name": "Acme Veteran Services LLC",
        "city": "Syracuse",
        "state": "NY",
        "website": "https://example.com",
    }


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Auto-applied: ensure tests cannot accidentally use real .env values.

    Removes the real PERPLEXITY_API_KEY and FIRECRAWL_API_KEY from os.environ
    for the duration of each test. Tests that need keys must use the
    fake_*_key fixtures explicitly. This prevents accidental live API calls
    during local development runs.
    """
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    yield
