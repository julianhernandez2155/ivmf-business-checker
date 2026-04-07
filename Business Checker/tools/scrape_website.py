"""
Website content scraper.

Fetches a business website and extracts visible text so the Perplexity prompt
has actual page content to reason about — instead of relying on search alone.

Only called when a URL is on file and Perplexity needs direct page content.
"""

import re
from urllib.parse import urlparse, urlunparse

import requests
import urllib3
from bs4 import BeautifulSoup

TIMEOUT = 8    # seconds before giving up
MAX_TEXT = 600  # chars of page text to pass into the prompt

# Paths that are equivalent to the site root — strip them during normalization
_DEFAULT_PATHS = frozenset({"/index.html", "/index.php", "/home"})


def normalize_url(url: str | None) -> str:
    """Normalize a URL for consistent comparison and caching.

    Lowercases scheme and host only — path casing is preserved to avoid
    turning valid mixed-case URLs into 404s on case-sensitive servers.

    Rules: strip whitespace, ensure https scheme, lowercase scheme+host,
    remove www. prefix, drop query/fragment, remove default index paths,
    strip trailing slashes.

    Returns empty string for None or blank input. Returns the raw URL if the
    port is malformed so callers still have the website for context.
    """
    if not url or not url.strip():
        return ""

    url = url.strip()

    # Ensure scheme is present (case-insensitive check)
    if "://" not in url.lower():
        url = "https://" + url

    parsed = urlparse(url)

    # Force https scheme
    scheme = "https"

    # Lowercase hostname only — not path
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    # Guard against malformed ports (e.g. ":abc" or ":99999").
    # Return the raw URL so check_business() still has the website for Perplexity
    # context and the scraper can attempt it (and fail with a real error note).
    try:
        port = parsed.port
    except ValueError:
        return url.strip()
    netloc = f"{hostname}:{port}" if port else hostname

    # Remove default index paths — exact case-sensitive match only.
    # We preserve path casing for case-sensitive servers, so we must not
    # lowercase here either: /Home and /home could be distinct resources.
    path = parsed.path
    if path in _DEFAULT_PATHS:
        path = ""
    path = path.rstrip("/")

    # Drop query and fragment entirely
    normalized = urlunparse((scheme, netloc, path, "", "", ""))

    return normalized

# Phrases that indicate a parking, placeholder, or spam-squatted page, not a real business
_SLOP_MARKERS = [
    # Domain parking / placeholder
    "this domain is for sale",
    "buy this domain",
    "domain for sale",
    "domain parking",
    "parked free",
    "lorem ipsum",
    "coming soon",
    "under construction",
    "website coming soon",
    "site coming soon",
    "this site is under construction",
    # Spam / squatted domains (gambling, adult content)
    "situs judi",       # Indonesian gambling sites
    "slot online",
    "togel",
    "link alternatif",
    "daftar sekarang",  # common spam CTA
    "casino online",
    "judi online",
    "pornhub",
    "xvideos",
    "onlyfans.com",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _fetch(url: str) -> tuple[requests.Response | None, str]:
    """Try to GET a URL, retrying without SSL verification on SSLError.

    Returns (response, error_note). error_note is empty on success.
    Specific error notes are preserved so callers can keyword-match on them
    (e.g. "timed out", "connection", "nodename") for closure-signal logic.
    """
    try:
        return requests.get(
            url, headers=_HEADERS, timeout=TIMEOUT,
            allow_redirects=True, verify=True,
        ), ""
    except requests.exceptions.SSLError:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            return requests.get(
                url, headers=_HEADERS, timeout=TIMEOUT,
                allow_redirects=True, verify=False,
            ), ""
        except Exception as e:
            return None, str(e)[:120]
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except Exception as e:
        return None, str(e)[:120]


def scrape_website(url: str) -> dict:
    """
    Fetch a website and extract its visible text content.

    Returns a dict with:
        success  — True if the page was fetched and parsed
        is_slop  — True if the page looks like a parking/placeholder page
        text     — Extracted visible text (up to MAX_TEXT chars); empty if failed
        note     — Human-readable explanation (slop reason or error)
    """
    url = normalize_url(url)
    if not url:
        return {"success": False, "is_slop": False, "text": "", "note": "No URL provided."}

    # Try normalized https URL first, fall back to http if it fails
    resp, err_note = _fetch(url)
    if resp is None and url.startswith("https://"):
        resp, err_note = _fetch("http://" + url[8:])
    if resp is None:
        return {"success": False, "is_slop": False, "text": "", "note": err_note or "Could not connect to site."}

    if resp.status_code == 404:
        return {"success": False, "is_slop": False, "text": "", "note": "HTTP 404 — page not found."}

    if resp.status_code != 200:
        return {"success": False, "is_slop": False, "text": "", "note": f"HTTP {resp.status_code}."}

    try:
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip non-content elements
        for tag in soup(["script", "style", "nav", "footer", "head", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
    except Exception as e:
        return {"success": False, "is_slop": False, "text": "", "note": str(e)[:120]}

    # Very short pages are almost always parking or placeholder pages
    if len(text) < 80:
        return {
            "success": True, "is_slop": True, "text": "",
            "note": "Page has almost no text content — likely a parking or placeholder page.",
        }

    text_lower = text.lower()
    for marker in _SLOP_MARKERS:
        if marker in text_lower:
            return {
                "success": True, "is_slop": True, "text": "",
                "note": f"Parking/placeholder page detected (found: '{marker}').",
            }

    return {
        "success": True,
        "is_slop": False,
        "text": text[:MAX_TEXT],
        "note": "",
    }
