"""Unit tests for scrape_website slop detection.

Covers the 40-char threshold (Bug 2) and _SLOP_MARKERS keyword matching.
Uses unittest.mock to avoid real HTTP calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from tools.scrape_website import scrape_website


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    """Build a fake requests.Response with the given HTML body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


class TestSlopThreshold:
    """Verify the 40-char floor for sparse-but-real vs parking pages."""

    def test_text_under_40_chars_is_slop(self):
        html = "<html><body><p>Short</p></body></html>"  # far under 40 chars of visible text
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://example.com")
        assert result["is_slop"] is True
        assert result["success"] is True
        assert "parking or placeholder" in result["note"]

    def test_text_exactly_40_chars_is_not_slop(self):
        # 40 chars of visible text: not a parking page
        content = "A" * 40
        html = f"<html><body><p>{content}</p></body></html>"
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://example.com")
        assert result["is_slop"] is False

    def test_text_between_40_and_80_chars_is_not_slop(self):
        # These were wrongly classified as slop under the old 80-char threshold
        content = "Call us at 315-555-0100. Book online at example.com/reserve"
        assert 40 <= len(content) < 80, "Fixture must be in the 40-79 char range"
        html = f"<html><body><p>{content}</p></body></html>"
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://example.com")
        assert result["is_slop"] is False
        assert content in result["text"]

    def test_sparse_real_business_site_not_slop(self):
        # Simulate a minimal but real site: h1 + phone + address.
        # get_text() skips img alt, so visible text must be in real elements.
        # "Acme Plumbing Call: (315) 555-0199 123 Main St Book Now" = 55 chars
        html = """
        <html><body>
          <h1>Acme Plumbing</h1>
          <p>Call: (315) 555-0199</p>
          <p>123 Main St</p>
          <a href="/book">Book Now</a>
        </body></html>
        """
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://acmeplumbing.com")
        assert result["is_slop"] is False


class TestSlopMarkers:
    """Keyword-based slop detection still fires regardless of text length."""

    def test_domain_for_sale_is_slop(self):
        html = "<html><body><p>This domain is for sale. Contact us today. " + "x" * 50 + "</p></body></html>"
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://example.com")
        assert result["is_slop"] is True
        assert "domain is for sale" in result["note"]

    def test_coming_soon_is_slop(self):
        html = "<html><body><p>Website coming soon. Stay tuned for updates. " + "x" * 50 + "</p></body></html>"
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://example.com")
        assert result["is_slop"] is True

    def test_lorem_ipsum_is_slop(self):
        html = "<html><body><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p></body></html>"
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://example.com")
        assert result["is_slop"] is True

    def test_real_content_with_long_text_is_not_slop(self):
        html = """
        <html><body>
          <h1>Acme Barbershop</h1>
          <p>Family-owned since 1985. Walk-ins welcome Mon-Sat 9am-6pm.</p>
          <p>123 Main St, Syracuse NY 13202 | (315) 555-0177</p>
        </body></html>
        """
        with patch("tools.scrape_website._fetch", return_value=(_mock_response(html), "")):
            result = scrape_website("https://acmebarbershop.com")
        assert result["is_slop"] is False
        assert result["success"] is True
