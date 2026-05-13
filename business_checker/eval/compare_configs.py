"""Side-by-side metric comparison for two labeled-CSV scoring runs.

Produced for iter-13 Phase B: when a config change ships, the eval gate
needs a single command that prints a baseline-vs-candidate delta table
and exits non-zero on regression. No HTML, no plots, no dashboard — the
scope floor agreed with Codex.

Usage (CLI):
    python -m eval.compare_configs \\
        --baseline eval/datasets/bmosg_v1_iteration_10_tiered.csv \\
        --candidate eval/datasets/bmosg_v1_iteration_11_fb.csv

Exit code:
    0  no regression — every metric is green or yellow.
    1  at least one metric crossed a red threshold.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from eval.score import score

logger = logging.getLogger(__name__)


# Noise band before a delta is flagged red.
DECISIVE_NOISE_PP = 0.02   # ±2 percentage points
HARMFUL_NOISE = 1          # ±1 harmful flip

GREEN = "✅"
YELLOW = "⚠️"
RED = "❌"


@dataclass(frozen=True)
class MetricSpec:
    """Describes one metric row in the comparison table."""

    key: str
    label: str
    is_pct: bool
    # `direction = +1` means "higher is better"; -1 means "lower is better".
    direction: int
    noise: float

    def fmt_value(self, raw: Any) -> str:
        if raw is None:
            return "—"
        if self.is_pct:
            return f"{raw:.1%}"
        return str(raw)

    def fmt_delta(self, baseline: Any, candidate: Any) -> str:
        if baseline is None or candidate is None:
            return "—"
        delta = candidate - baseline
        if self.is_pct:
            return f"{delta:+.1%}"
        if isinstance(delta, float):
            return f"{delta:+.2f}"
        return f"{delta:+d}"

    def verdict(self, baseline: Any, candidate: Any) -> str:
        if baseline is None or candidate is None:
            return YELLOW
        delta = candidate - baseline
        signed = delta * self.direction  # > 0 means improvement
        if signed >= 0:
            return GREEN
        if abs(delta) <= self.noise:
            return YELLOW
        return RED


METRICS: tuple[MetricSpec, ...] = (
    MetricSpec("decisive_accuracy", "Decisive accuracy", True, +1, DECISIVE_NOISE_PP),
    MetricSpec("harmful_flips_total", "Harmful flips (total)", False, -1, HARMFUL_NOISE),
    MetricSpec("harmful_flips_active_to_closed", "  Active→Closed (false-pos)",
               False, -1, HARMFUL_NOISE),
    MetricSpec("harmful_flips_closed_to_active", "  Closed→Active (false-neg)",
               False, -1, HARMFUL_NOISE),
    MetricSpec("review_queue_size", "Review queue size", False, -1, HARMFUL_NOISE),
)


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = [
        "| " + " | ".join(str(v) if v is not None else "" for v in r) + " |"
        for r in rows
    ]
    return "\n".join([header_line, separator] + body_lines)


def compare(baseline_csv: Path, candidate_csv: Path) -> tuple[str, int]:
    """Score both CSVs and produce a markdown delta table.

    Returns:
        (table_markdown, exit_code) — exit_code is 1 if any metric was red.
    """
    base = score(baseline_csv, out_dir=None)
    cand = score(candidate_csv, out_dir=None)

    rows: list[list[Any]] = []
    any_red = False
    for spec in METRICS:
        b = base.get(spec.key)
        c = cand.get(spec.key)
        v = spec.verdict(b, c)
        if v == RED:
            any_red = True
        rows.append([
            spec.label,
            spec.fmt_value(b),
            spec.fmt_value(c),
            spec.fmt_delta(b, c),
            v,
        ])

    table = _md_table(
        ["Metric", "Baseline", "Candidate", "Δ", "Verdict"],
        rows,
    )
    table += (
        f"\n\nBaseline:  `{baseline_csv}`\n"
        f"Candidate: `{candidate_csv}`\n"
    )
    return table, (1 if any_red else 0)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval.compare_configs",
        description="Side-by-side metric comparison of two labeled CSVs.",
    )
    p.add_argument("--baseline", required=True, type=Path,
                   help="Labeled CSV from the prior config.")
    p.add_argument("--candidate", required=True, type=Path,
                   help="Labeled CSV from the new config under evaluation.")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    table, exit_code = compare(args.baseline, args.candidate)
    print(table)
    if exit_code != 0:
        print(f"\n{RED} Regression detected — exit 1.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
