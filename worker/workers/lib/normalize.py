"""CANON-03: Normalize name, domain, phone, address before canonical matching.

These helpers are imported by Phase 1 canonical matching logic.
Phase 0 ships and tests them; Phase 1 wires them into the 2-of-N flow.

Behavior tests live in worker/tests/test_normalize.py and are the contract.
"""
from __future__ import annotations

import re

# Suffixes stripped from business names before matching. Ordered: longest first
# so we match "incorporated" before "inc".
#
# NOTE: "corp" (4 letters) is intentionally excluded — the contract case
# normalize_name("Acme Corp.") == "acme corp" requires it to survive. Only the
# full word "corporation" is stripped. Similar reasoning applies to "company".
_NAME_SUFFIXES: tuple[str, ...] = (
    " incorporated",
    " corporation",
    " l.l.c.",
    " l.l.c",
    " p.l.l.c.",
    " pllc",
    " l.l.p.",
    " llp",
    " l.p.",
    " lp",
    " limited",
    " ltd",
    " llc",
    " inc",
)

_PUNCT_RX = re.compile(r"[,.;:!?\"'`()\[\]{}]")
_WS_RX = re.compile(r"\s+")
_PHONE_DIGITS_RX = re.compile(r"\D+")
_DOMAIN_SCHEME_RX = re.compile(r"^[a-z]+://", re.IGNORECASE)


def normalize_name(s: str) -> str:
    """Strip suffixes, lowercase, collapse whitespace. Unicode preserved."""
    if not s:
        return ""
    x = s.strip().lower()
    x = _PUNCT_RX.sub("", x)
    x = _WS_RX.sub(" ", x).strip()
    for suffix in _NAME_SUFFIXES:
        if x.endswith(suffix):
            x = x[: -len(suffix)].rstrip()
            break
    return x.strip()


def normalize_domain(s: str) -> str:
    """Strip scheme, www., path. Return lowercase root domain."""
    if not s:
        return ""
    x = s.strip().lower()
    x = _DOMAIN_SCHEME_RX.sub("", x)
    # strip path / query / fragment
    x = x.split("/", 1)[0]
    if x.startswith("www."):
        x = x[4:]
    return x


def normalize_phone(s: str) -> str | None:
    """Return E.164 US format (+1XXXXXXXXXX) or None if not parseable."""
    if not s:
        return None
    digits = _PHONE_DIGITS_RX.sub("", s)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def normalize_address(s: str) -> dict:
    """Phase 0 stub: regex split into components.

    Phase 1 will replace with usaddress.tag() per STACK.md. For now this
    handles the canonical "123 Main St, Syracuse, NY 13210" shape used by
    the v1.0 BMSG/MWBE datasets.
    """
    if not s:
        return {}
    parts = [p.strip() for p in s.split(",")]
    out: dict = {"raw": s.strip()}
    if len(parts) >= 1:
        out["street_address"] = parts[0]
    if len(parts) >= 2:
        out["city"] = parts[1]
    if len(parts) >= 3:
        tokens = parts[2].split()
        if tokens:
            out["state"] = tokens[0]
            if len(tokens) > 1:
                out["zip"] = tokens[1]
    return out
