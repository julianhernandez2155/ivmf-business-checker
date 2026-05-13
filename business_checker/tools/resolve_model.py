"""Resolve the current Claude adjudicator model ID via the Anthropic SDK.

Why this exists (iter 14 Phase 1 step 1): Anthropic doc pages disagree on which
Claude 4.x Sonnet ID is current. The plan refuses to hard-code; instead we
list available models at execution time and pin the latest non-deprecated
Sonnet 4.x. Result is recorded in `business_checker/tools/adjudicator.py`
as `MODEL_ID` and printed in every adjudicator log line so future drift is
auditable.

Usage
-----
    python -m tools.resolve_model
        → prints a table of available models with created_at + display_name.

    python -m tools.resolve_model --pick sonnet-4
        → prints the picked ID on stdout, one line, no decoration. Suitable
          for shelling into another script (e.g. `MODEL=$(python -m tools.resolve_model --pick sonnet-4)`).

Plan reference: docs/2026-05-13-iter14-search-vs-reasoning-spike.md
§Phase 1 step 1 (Revision 2 changelog #1).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _normalize_id_for_ranking(model_id: str) -> tuple[int, int, str]:
    """Sort key that prefers higher Claude version numbers.

    Returns (major, minor, id) so the natural sort puts the newest first.
    """
    # IDs look like 'claude-sonnet-4-6' or 'claude-sonnet-4-20250514'.
    parts = model_id.split("-")
    try:
        major = int(parts[2])
    except (IndexError, ValueError):
        major = 0
    try:
        minor = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    except (IndexError, ValueError):
        minor = 0
    return (major, minor, model_id)


def list_models(api_key: str) -> list[dict]:
    """Return all visible models as a list of plain dicts (id, created_at, display)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    page = client.models.list(limit=50)
    out: list[dict] = []
    for m in page.data:
        out.append(
            {
                "id": m.id,
                "created_at": str(getattr(m, "created_at", "")),
                "display_name": getattr(m, "display_name", ""),
            }
        )
    return out


def pick_latest(models: list[dict], family: str) -> str | None:
    """Pick the latest model ID containing the family substring (e.g. 'sonnet-4').

    Sorts by `created_at` descending; falls back to ID version sort if missing.
    """
    candidates = [m for m in models if family in m["id"]]
    if not candidates:
        return None
    candidates.sort(
        key=lambda m: (m.get("created_at", ""), _normalize_id_for_ranking(m["id"])),
        reverse=True,
    )
    return candidates[0]["id"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.resolve_model",
        description="List available Anthropic models and (optionally) pick the latest of a family.",
    )
    parser.add_argument(
        "--pick", default=None,
        help="If set, print only the ID of the latest model whose ID contains this substring "
             "(e.g. 'sonnet-4', 'opus-4', 'haiku-4'). Nothing else printed — suitable for $(...).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY missing from .env", file=sys.stderr)
        sys.exit(1)

    args = _build_parser().parse_args(argv)
    models = list_models(api_key)

    if args.pick:
        picked = pick_latest(models, args.pick)
        if not picked:
            print(f"ERROR: no model ID contains '{args.pick}'", file=sys.stderr)
            sys.exit(2)
        print(picked)
        return

    print(f"{'ID':<45} {'CREATED':<28} {'DISPLAY'}")
    print("-" * 100)
    for m in models:
        print(f"{m['id']:<45} {m['created_at']:<28} {m['display_name']}")


if __name__ == "__main__":
    main(sys.argv[1:])
