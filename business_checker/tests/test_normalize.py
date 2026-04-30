"""Unit tests for URL normalization."""

import pytest

from tools.scrape_website import normalize_url


class TestNormalizeUrlEmptyInput:
    """None, empty, and whitespace inputs return empty string."""

    def test_none_returns_empty(self):
        assert normalize_url(None) == ""

    def test_empty_string_returns_empty(self):
        assert normalize_url("") == ""

    def test_whitespace_returns_empty(self):
        assert normalize_url("   ") == ""


class TestNormalizeUrlScheme:
    """Scheme handling: add https when missing, force http -> https."""

    def test_adds_https_when_no_scheme(self):
        assert normalize_url("acme.com") == "https://acme.com"

    def test_upgrades_http_to_https(self):
        assert normalize_url("http://acme.com") == "https://acme.com"

    def test_preserves_https(self):
        assert normalize_url("https://acme.com") == "https://acme.com"

    def test_uppercase_scheme(self):
        assert normalize_url("HTTP://acme.com") == "https://acme.com"


class TestNormalizeUrlLowercase:
    """Scheme and host are lowercased; path casing is preserved."""

    def test_lowercases_domain(self):
        assert normalize_url("HTTPS://ACME.COM") == "https://acme.com"

    def test_preserves_path_casing(self):
        # Path casing is preserved to avoid 404s on case-sensitive servers
        assert normalize_url("https://acme.com/About") == "https://acme.com/About"

    def test_lowercases_scheme_and_host_preserves_path(self):
        assert normalize_url("Http://Acme.Com/Contact") == "https://acme.com/Contact"


class TestNormalizeUrlWww:
    """Leading www. prefix is stripped from domain."""

    def test_removes_www(self):
        assert normalize_url("https://www.acme.com") == "https://acme.com"

    def test_does_not_remove_www_in_middle(self):
        assert normalize_url("https://my-www.acme.com") == "https://my-www.acme.com"

    def test_removes_www_with_path(self):
        assert normalize_url("https://www.acme.com/about") == "https://acme.com/about"


class TestNormalizeUrlTrailingSlash:
    """Trailing slashes are stripped."""

    def test_strips_root_trailing_slash(self):
        assert normalize_url("https://acme.com/") == "https://acme.com"

    def test_strips_path_trailing_slash(self):
        assert normalize_url("https://acme.com/about/") == "https://acme.com/about"


class TestNormalizeUrlDefaultPaths:
    """Default index paths are removed (exact match only)."""

    def test_removes_index_html(self):
        assert normalize_url("http://acme.com/index.html") == "https://acme.com"

    def test_removes_index_php(self):
        assert normalize_url("http://acme.com/index.php") == "https://acme.com"

    def test_removes_home(self):
        assert normalize_url("http://acme.com/home") == "https://acme.com"

    def test_preserves_home_subpath(self):
        assert normalize_url("https://acme.com/home/products") == "https://acme.com/home/products"

    def test_preserves_non_default_path(self):
        assert normalize_url("https://acme.com/products") == "https://acme.com/products"

    def test_default_path_match_is_case_sensitive(self):
        # Exact match only — /Index.html may be a distinct resource on case-sensitive servers
        assert normalize_url("https://acme.com/Index.html") == "https://acme.com/Index.html"


class TestNormalizeUrlQueryFragment:
    """Query parameters and fragments are stripped."""

    def test_strips_query(self):
        assert normalize_url("https://acme.com/about?ref=google") == "https://acme.com/about"

    def test_strips_fragment(self):
        assert normalize_url("https://acme.com/about#section") == "https://acme.com/about"

    def test_strips_both(self):
        assert normalize_url("https://acme.com?q=1#top") == "https://acme.com"


class TestNormalizeUrlPort:
    """Port numbers are preserved; malformed ports return empty string."""

    def test_preserves_port(self):
        assert normalize_url("https://acme.com:8080/about") == "https://acme.com:8080/about"

    def test_preserves_port_strips_www(self):
        assert normalize_url("http://www.acme.com:3000") == "https://acme.com:3000"

    def test_invalid_port_string_returns_raw_url(self):
        # Malformed port: return raw URL so Perplexity still gets website context
        assert normalize_url("https://acme.com:abc/about") == "https://acme.com:abc/about"

    def test_out_of_range_port_returns_raw_url(self):
        assert normalize_url("https://acme.com:99999") == "https://acme.com:99999"


class TestNormalizeUrlCombined:
    """Acceptance criteria from UPGRADE_PLAN.md + idempotency."""

    def test_full_normalization_uppercase_www_slash(self):
        # Scheme+host lowercased, www stripped, trailing slash removed
        assert normalize_url("HTTP://WWW.ACME.COM/") == "https://acme.com"

    def test_full_normalization_index_html(self):
        assert normalize_url("http://acme.com/index.html") == "https://acme.com"

    def test_full_normalization_www_index_php_query(self):
        assert normalize_url("http://www.acme.com/index.php?id=5") == "https://acme.com"

    def test_idempotent(self):
        raw = "HTTP://WWW.ACME.COM/index.html?ref=1#top"
        once = normalize_url(raw)
        twice = normalize_url(once)
        assert once == twice
