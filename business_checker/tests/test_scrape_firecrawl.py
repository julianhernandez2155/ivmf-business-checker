"""Unit tests for Firecrawl scraper integration.

Covers:
- _scrape_firecrawl: success, slop detection, empty content, HTTP errors, timeout, JSON errors
- _scrape_direct: unchanged behavior (scrape_cost=0.0)
- scrape_website: Firecrawl-first routing, fallback to direct when Firecrawl fails,
  no Firecrawl key → direct only
"""

import pytest
from unittest.mock import patch, MagicMock

import tools.scrape_website as scrape_module
from tools.scrape_website import (
    _scrape_direct,
    _scrape_firecrawl,
    scrape_website,
    FIRECRAWL_COST_PER_SCRAPE,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_http_response(html: str, status_code: int = 200) -> MagicMock:
    """Fake requests.Response for direct HTTP."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


def _mock_firecrawl_response(markdown: str = "", success: bool = True, status_code: int = 200) -> MagicMock:
    """Fake requests.Response for Firecrawl POST."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "success": success,
        "data": {"markdown": markdown},
    }
    return resp


# ── _scrape_firecrawl ─────────────────────────────────────────────────────────

class TestScrapeFirecrawl:
    """Unit tests for the Firecrawl backend in isolation."""

    def test_success_real_content(self):
        """Valid Firecrawl response with real content → success, correct cost."""
        markdown = "# Acme Plumbing\n\nFamily-owned since 1985. Call (315) 555-0199. Walk-ins welcome."
        with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response(markdown)):
            result = _scrape_firecrawl("https://acmeplumbing.com")

        assert result["success"] is True
        assert result["is_slop"] is False
        assert "Acme Plumbing" in result["text"]
        assert result["scrape_cost"] == pytest.approx(FIRECRAWL_COST_PER_SCRAPE)

    def test_markdown_stripped_to_plain_text(self):
        """Markdown syntax is stripped before returning text."""
        # Fixture must produce >40 chars of plain text to avoid the slop threshold
        markdown = (
            "# Acme Roofing Services\n\n"
            "**Licensed and insured** roofing contractor. *Serving Syracuse since 1995.*\n\n"
            "[Call us today](tel:3155550100) for a free estimate. `info@acme.com`"
        )
        with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response(markdown)):
            result = _scrape_firecrawl("https://example.com")

        assert "#" not in result["text"]
        assert "**" not in result["text"]
        assert "`" not in result["text"]
        assert "Acme Roofing Services" in result["text"]
        assert "Licensed and insured" in result["text"]
        assert "Call us today" in result["text"]

    def test_slop_detection_on_firecrawl_output(self):
        """Parking page content from Firecrawl is flagged as slop."""
        markdown = "## This domain is for sale\n\nContact us today. " + "x" * 50
        with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response(markdown)):
            result = _scrape_firecrawl("https://example.com")

        assert result["is_slop"] is True
        assert result["success"] is True
        assert result["scrape_cost"] == pytest.approx(FIRECRAWL_COST_PER_SCRAPE)

    def test_short_content_is_slop(self):
        """Pages with under 40 chars of text after markdown stripping → slop."""
        markdown = "Short"
        with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response(markdown)):
            result = _scrape_firecrawl("https://example.com")

        assert result["is_slop"] is True
        assert result["scrape_cost"] == pytest.approx(FIRECRAWL_COST_PER_SCRAPE)

    def test_empty_markdown_returns_failure(self):
        """Empty markdown content → success=False, no cost charged."""
        with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response("")):
            result = _scrape_firecrawl("https://example.com")

        assert result["success"] is False
        assert result["scrape_cost"] == 0.0

    def test_firecrawl_http_error(self):
        """Non-200 from Firecrawl → success=False, no cost charged."""
        with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response(status_code=500)):
            result = _scrape_firecrawl("https://example.com")

        assert result["success"] is False
        assert "500" in result["note"]
        assert result["scrape_cost"] == 0.0

    def test_firecrawl_api_success_false(self):
        """Firecrawl returns success=false → success=False, no cost."""
        with patch(
            "tools.scrape_website.requests.post",
            return_value=_mock_firecrawl_response(markdown="content", success=False),
        ):
            result = _scrape_firecrawl("https://example.com")

        assert result["success"] is False
        assert result["scrape_cost"] == 0.0

    def test_firecrawl_timeout(self):
        """Timeout on Firecrawl → success=False, no cost."""
        import requests as req
        with patch("tools.scrape_website.requests.post", side_effect=req.exceptions.Timeout):
            result = _scrape_firecrawl("https://example.com")

        assert result["success"] is False
        assert "timed out" in result["note"].lower()
        assert result["scrape_cost"] == 0.0

    def test_firecrawl_invalid_json(self):
        """Malformed JSON response → success=False."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("not json")
        with patch("tools.scrape_website.requests.post", return_value=resp):
            result = _scrape_firecrawl("https://example.com")

        assert result["success"] is False
        assert result["scrape_cost"] == 0.0

    def test_text_capped_at_max_text(self):
        """Text output is capped at MAX_TEXT characters."""
        from tools.scrape_website import MAX_TEXT
        markdown = "Word " * 300   # well over MAX_TEXT
        with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response(markdown)):
            result = _scrape_firecrawl("https://example.com")

        assert result["success"] is True
        assert len(result["text"]) <= MAX_TEXT


# ── _scrape_direct ────────────────────────────────────────────────────────────

class TestScrapeDirect:
    """Verify direct HTTP path still works and always returns scrape_cost=0.0."""

    def test_direct_success_has_zero_cost(self):
        html = "<html><body><p>Acme Barbershop. Walk-ins welcome Mon-Sat 9am-6pm. 315-555-0177</p></body></html>"
        with patch("tools.scrape_website._fetch", return_value=(_mock_http_response(html), "")):
            result = _scrape_direct("https://acmebarbershop.com")

        assert result["success"] is True
        assert result["scrape_cost"] == 0.0

    def test_direct_failure_has_zero_cost(self):
        with patch("tools.scrape_website._fetch", return_value=(None, "Request timed out.")):
            result = _scrape_direct("https://example.com")

        assert result["success"] is False
        assert result["scrape_cost"] == 0.0

    def test_direct_404_has_zero_cost(self):
        with patch("tools.scrape_website._fetch", return_value=(_mock_http_response("", 404), "")):
            result = _scrape_direct("https://example.com")

        assert result["success"] is False
        assert result["scrape_cost"] == 0.0


# ── scrape_website routing ────────────────────────────────────────────────────

class TestScrapeWebsiteRouting:
    """Verify Firecrawl-first routing and fallback behavior."""

    def test_uses_firecrawl_when_key_set(self):
        """With a Firecrawl key, Firecrawl is tried before direct HTTP."""
        markdown = "# Acme Roofing\n\nFull-service roofing contractor. Call 315-555-0100. Licensed and insured."
        firecrawl_resp = _mock_firecrawl_response(markdown)

        with patch.object(scrape_module, "_FIRECRAWL_KEY", "test-key"):
            with patch("tools.scrape_website.requests.post", return_value=firecrawl_resp) as mock_post:
                with patch("tools.scrape_website._fetch") as mock_fetch:
                    result = scrape_website("https://acmeroofing.com")

        mock_post.assert_called_once()
        mock_fetch.assert_not_called()
        assert result["success"] is True
        assert result["scrape_cost"] == pytest.approx(FIRECRAWL_COST_PER_SCRAPE)

    def test_falls_back_to_direct_when_firecrawl_fails(self):
        """Firecrawl failure is silent — direct HTTP is tried next."""
        import requests as req
        html = "<html><body><p>Acme Barbershop. Walk-ins welcome Mon-Sat 9am-6pm. 315-555-0177</p></body></html>"

        with patch.object(scrape_module, "_FIRECRAWL_KEY", "test-key"):
            with patch("tools.scrape_website.requests.post", side_effect=req.exceptions.Timeout):
                with patch("tools.scrape_website._fetch", return_value=(_mock_http_response(html), "")):
                    result = scrape_website("https://acmebarbershop.com")

        assert result["success"] is True
        assert result["scrape_cost"] == 0.0   # direct HTTP — no Firecrawl cost

    def test_no_firecrawl_key_uses_direct_only(self):
        """Without a key, Firecrawl is never called."""
        html = "<html><body><p>Acme Barbershop. Walk-ins welcome Mon-Sat 9am-6pm. 315-555-0177</p></body></html>"

        with patch.object(scrape_module, "_FIRECRAWL_KEY", ""):
            with patch("tools.scrape_website.requests.post") as mock_post:
                with patch("tools.scrape_website._fetch", return_value=(_mock_http_response(html), "")) as mock_fetch:
                    result = scrape_website("https://acmebarbershop.com")

        mock_post.assert_not_called()
        mock_fetch.assert_called()
        assert result["scrape_cost"] == 0.0

    def test_no_url_returns_early(self):
        """Empty URL skips all scraping."""
        result = scrape_website("")
        assert result["success"] is False
        assert result["scrape_cost"] == 0.0

    def test_firecrawl_slop_is_not_retried_with_direct(self):
        """A slop result from Firecrawl is final — direct HTTP is not tried."""
        markdown = "## This domain is for sale\n\nContact us today. " + "x" * 60

        with patch.object(scrape_module, "_FIRECRAWL_KEY", "test-key"):
            with patch("tools.scrape_website.requests.post", return_value=_mock_firecrawl_response(markdown)):
                with patch("tools.scrape_website._fetch") as mock_fetch:
                    result = scrape_website("https://example.com")

        mock_fetch.assert_not_called()
        assert result["is_slop"] is True
