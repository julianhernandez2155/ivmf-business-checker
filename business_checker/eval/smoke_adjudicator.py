"""Smoke test: run the iter-14 Sonnet adjudicator against real Phase 0 rows.

The mocked golden tests prove the parser + module contract; this script
exercises the live prompt against actual Perplexity output so we can see
whether the adjudicator emits sensible verdicts on real evidence shapes
BEFORE committing to a 60-row paid A1 run.

Picks 3 rows from `predictions_pass1.csv`: one human-labeled Active, one
Likely Closed, one Uncertain. Builds a minimal evidence dict from the
predictions CSV columns (Perplexity prose verdict + citations only — no
FB recency or website scrape, those would require live network calls).

Outputs a short markdown report in `eval/reports/iter14_adjudicator_smoke/`.

Cost: ~$0.005 × 3 ≈ $0.015.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.adjudicator import MODEL_ID, adjudicate  # noqa: E402
from tools.check_business_branch_a import classify_citation  # noqa: E402
from tools.evidence_schema import (  # noqa: E402
    BusinessEvidence,
    CitationHit,
    ScrapeResult,
)

logger = logging.getLogger(__name__)


def _build_minimal_evidence(row: pd.Series) -> BusinessEvidence:
    """Construct a BusinessEvidence from a Phase 0 predictions row.

    Uses only what's in the predictions CSV: Perplexity prose + citations.
    Website scrape and FB signal are left as 'not gathered' (None / unreachable)
    since this smoke test deliberately avoids extra paid calls.
    """
    citation_urls = [
        u.strip().rstrip("/")
        for u in str(row.get("predicted_citations", "")).split(",")
        if u.strip()
    ]
    hits = tuple(
        CitationHit(
            url=u,
            title=None,
            snippet=None,
            scraped_text=None,
            citation_type=classify_citation(u),
        )
        for u in citation_urls
    )
    return BusinessEvidence(
        name=str(row.get("name", "") or ""),
        website=(str(row.get("website", "")) or None) or None,
        city=str(row.get("city", "") or ""),
        state=str(row.get("state", "") or ""),
        metadata=None,
        own_website_scrape=ScrapeResult(
            reachable=False, status_code=None, text=None,
            error="not gathered in smoke test",
        ),
        citation_hits=hits,
        facebook_signal=None,
        instagram_signal=None,
        perplexity_prose=str(row.get("predicted_evidence", "") or "") or None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("eval/reports/iter14_phase0/predictions_pass1.csv"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("eval/reports/iter14_adjudicator_smoke"),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                        datefmt="%H:%M:%S")
    load_dotenv(Path(__file__).parent.parent / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY missing", file=sys.stderr)
        return 1

    df = pd.read_csv(args.predictions)
    # Pick one of each status if available; else first three rows.
    picks: list[pd.Series] = []
    for label in ("Active", "Likely Closed", "Uncertain"):
        candidates = df[df["human_label"] == label]
        if not candidates.empty:
            picks.append(candidates.iloc[0])
    if len(picks) < 3:
        for _, row in df.iterrows():
            if len(picks) >= 3:
                break
            if not any(p["row_index"] == row["row_index"] for p in picks):
                picks.append(row)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f"# Iter 14 — adjudicator smoke test\n",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Model:** `{MODEL_ID}`",
        f"**Predictions source:** `{args.predictions}`",
        f"**Rows tested:** {len(picks)}\n",
        "## Results\n",
        "| row_index | name | human label | Perplexity verdict | Adjudicator verdict | Match? |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]

    matches = 0
    for row in picks:
        evidence = _build_minimal_evidence(row)
        logger.info("Adjudicating row_index=%s name=%r", row["row_index"], evidence.name)
        result = adjudicate(evidence, api_key=api_key)
        match = "✅" if str(row.get("predicted_status")) == result.status else "⚠️"
        if match == "✅":
            matches += 1
        lines.append(
            f"| {int(row['row_index'])} | {evidence.name} "
            f"| {row.get('human_label')} | {row.get('predicted_status')} "
            f"| {result.status} ({result.confidence}) | {match} |"
        )
        # Append details
        lines.append("")
        lines.append(f"**Adjudicator evidence for row {int(row['row_index'])}:** "
                     f"{result.evidence}")
        lines.append("")

    lines.append(f"\n**Match rate vs. Perplexity:** {matches}/{len(picks)}\n")
    lines.append("Note: the adjudicator is intentionally working from minimal "
                 "evidence (no website scrape, no FB signal). A real A1 run "
                 "would have those signals; this smoke test only verifies "
                 "the prompt parses real Perplexity outputs and returns "
                 "valid JSON.")

    report = "\n".join(lines)
    out_path = args.out_dir / "adjudicator_smoke.md"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nReport: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
