"""
Shared column detection utilities.

Used by both business_checker_gui.py and run_checker.py to map spreadsheet
headers to the fields the checker needs (name, website, city, state).
"""

# Estimate used in the GUI's run preview dialog.
# Keep in sync with PERPLEXITY_COST_PER_REQUEST in .env.example (~$0.005 base + tokens).
COST_PER_BUSINESS_ESTIMATE = 0.008

HEADER_HINTS = {
    "name":    ["name", "business name", "company", "organization"],
    "website": ["website", "web", "url", "site", "link"],
    "city":    ["city", "town", "municipality"],
    "state":   ["state", "province", "region"],
}


def detect_columns(headers: list) -> dict:
    """
    Auto-detect column indices from a header row.

    Returns a dict mapping field names to 0-based column indices.
    A field's value is None if no matching header was found.
    """
    detected = {field: None for field in HEADER_HINTS}
    for idx, h in enumerate(headers):
        if h is None:
            continue
        h_lower = str(h).lower().strip()
        for field, hints in HEADER_HINTS.items():
            if detected[field] is None and any(hint in h_lower for hint in hints):
                detected[field] = idx
    return detected
