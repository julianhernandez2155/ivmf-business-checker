"""
Website content scraper.

Fetches a business website and extracts visible text so the Perplexity prompt
has actual page content to reason about — instead of relying on search alone.

Only called when a URL is on file and Perplexity needs direct page content.

Scraping strategy:
  1. Firecrawl API (if FIRECRAWL_API_KEY is set) — handles JS-rendered sites,
     Cloudflare protection, and SPAs that requests.get() can't read.
  2. Direct HTTP fallback — free, covers simple static sites.

The public interface (scrape_website) is unchanged — callers don't need to
know which backend was used.
"""

import os
import re
from urllib.parse import urlparse, urlunparse

import requests
import urllib3
from bs4 import BeautifulSoup

TIMEOUT           = 8    # seconds before giving up (direct HTTP)
FIRECRAWL_TIMEOUT = 15   # seconds for Firecrawl (JS rendering needs more time)
MAX_TEXT          = 600  # chars of page text to pass into the prompt

FIRECRAWL_COST_PER_SCRAPE = 0.001  # ~$0.001/page on Standard plan
FIRECRAWL_API_URL         = "https://api.firecrawl.dev/v1/scrape"

# Loaded once at import — if not set, Firecrawl path is skipped entirely
_FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY", "").strip()

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


def _classify_text(text: str, scrape_cost: float) -> dict:
    """Apply slop detection to extracted text and return a scrape result dict.

    Shared by both scrape backends so detection logic stays in one place.
    """
    # Very short pages are almost always parking or placeholder pages.
    # 40-char floor: genuine parking pages are typically much shorter (often just
    # the domain name), while sparse-but-real sites (logo + phone + booking link)
    # can easily exceed 40 chars. The original 80-char threshold was too aggressive.
    if len(text) < 40:
        return {
            "success": True, "is_slop": True, "text": "",
            "note": "Page has almost no text content — likely a parking or placeholder page.",
            "scrape_cost": scrape_cost,
        }

    text_lower = text.lower()
    for marker in _SLOP_MARKERS:
        if marker in text_lower:
            return {
                "success": True, "is_slop": True, "text": "",
                "note": f"Parking/placeholder page detected (found: '{marker}').",
                "scrape_cost": scrape_cost,
            }

    return {
        "success": True,
        "is_slop": False,
        "text": text[:MAX_TEXT],
        "note": "",
        "scrape_cost": scrape_cost,
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


def _scrape_direct(url: str) -> dict:
    """Scrape via direct HTTP — free, works for static sites.

    Returns a scrape result dict with keys: success, is_slop, text, note, scrape_cost.
    scrape_cost is always 0.0 (no API cost for direct HTTP).
    """
    # Try normalized https URL first, fall back to http if it fails
    resp, err_note = _fetch(url)
    if resp is None and url.startswith("https://"):
        resp, err_note = _fetch("http://" + url[8:])
    if resp is None:
        return {
            "success": False, "is_slop": False, "text": "",
            "note": err_note or "Could not connect to site.",
            "scrape_cost": 0.0,
        }

    if resp.status_code == 404:
        return {"success": False, "is_slop": False, "text": "", "note": "HTTP 404 — page not found.", "scrape_cost": 0.0}

    if resp.status_code != 200:
        return {"success": False, "is_slop": False, "text": "", "note": f"HTTP {resp.status_code}.", "scrape_cost": 0.0}

    try:
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip non-content elements
        for tag in soup(["script", "style", "nav", "footer", "head", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
    except Exception as e:
        return {"success": False, "is_slop": False, "text": "", "note": str(e)[:120], "scrape_cost": 0.0}

    return _classify_text(text, scrape_cost=0.0)


def _scrape_firecrawl(url: str) -> dict:
    """Scrape via Firecrawl API — handles JS rendering, Cloudflare, SPAs.

    Returns a scrape result dict with keys: success, is_slop, text, note, scrape_cost.
    scrape_cost is FIRECRAWL_COST_PER_SCRAPE on any response (success or slop),
    0.0 on connection failure (no credit consumed).
    """
    payload = {"url": url, "formats": ["markdown"]}
    headers = {
        "Authorization": f"Bearer {_FIRECRAWL_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            FIRECRAWL_API_URL,
            headers=headers,
            json=payload,
            timeout=FIRECRAWL_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return {"success": False, "is_slop": False, "text": "", "note": "Firecrawl timed out.", "scrape_cost": 0.0}
    except Exception as e:
        return {"success": False, "is_slop": False, "text": "", "note": str(e)[:120], "scrape_cost": 0.0}

    if resp.status_code != 200:
        return {
            "success": False, "is_slop": False, "text": "",
            "note": f"Firecrawl HTTP {resp.status_code}.",
            "scrape_cost": 0.0,
        }

    try:
        data = resp.json()
    except Exception:
        return {"success": False, "is_slop": False, "text": "", "note": "Firecrawl returned invalid JSON.", "scrape_cost": 0.0}

    if not data.get("success"):
        return {
            "success": False, "is_slop": False, "text": "",
            "note": "Firecrawl returned success=false.",
            "scrape_cost": 0.0,
        }

    markdown = (data.get("data") or {}).get("markdown", "")
    if not markdown:
        return {"success": False, "is_slop": False, "text": "", "note": "Firecrawl returned empty content.", "scrape_cost": 0.0}

    # Convert markdown to plain text
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", markdown)   # images → alt text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)         # links → link text
    text = re.sub(r"#{1,6}\s+", "", text)                        # strip heading markers
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)      # bold/italic
    text = re.sub(r"`[^`\n]+`", " ", text)                       # inline code
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)  # horizontal rules
    text = re.sub(r"\s+", " ", text).strip()

    # Credit is consumed on a successful API response regardless of content quality
    return _classify_text(text, scrape_cost=FIRECRAWL_COST_PER_SCRAPE)


def scrape_website(url: str) -> dict:
    """
    Fetch a business website and extract its visible text content.

    Tries Firecrawl first (if FIRECRAWL_API_KEY is set), falls back to
    direct HTTP. Both paths use the same slop detection logic.

    Returns a dict with:
        success      — True if the page was fetched and parsed
        is_slop      — True if the page looks like a parking/placeholder page
        text         — Extracted visible text (up to MAX_TEXT chars); empty if failed
        note         — Human-readable explanation (slop reason or error)
        scrape_cost  — API cost in USD (0.001 for Firecrawl, 0.0 for direct)
    """
    url = normalize_url(url)
    if not url:
        return {"success": False, "is_slop": False, "text": "", "note": "No URL provided.", "scrape_cost": 0.0}

    # Try Firecrawl first (JS-aware, anti-bot bypass)
    if _FIRECRAWL_KEY:
        result = _scrape_firecrawl(url)
        if result["success"]:
            return result
        # Firecrawl failed — fall through to direct HTTP silently

    return _scrape_direct(url)
