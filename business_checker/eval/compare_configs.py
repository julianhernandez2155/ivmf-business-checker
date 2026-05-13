"""Side-by-side metric comparison for N labeled-CSV scoring runs.

Produced for iter-13 Phase B (2-input baseline-vs-candidate); extended in
iter-14 Phase 1 step 2 to accept N inputs so the iter-14 decision memo can
compare baseline + A1 + A2 + B in one table instead of three pairwise runs.

Usage (CLI) — 2-input (backwards-compatible):
    python -m eval.compare_configs \\
        --baseline eval/datasets/bmosg_v1_iteration_10_tiered.csv \\
        --candidate eval/datasets/bmosg_v1_iteration_11_fb.csv

Usage (CLI) — N-input:
    python -m eval.compare_configs \\
        --inputs v11=eval/reports/v11_fresh/labeled.csv \\
                 a1=eval/reports/iter14_a1/labeled.csv \\
                 a2=eval/reports/iter14_a2/labeled.csv \\
                 b=eval/reports/iter14_b/labeled.csv

The FIRST `--inputs` entry is the baseline; every other entry is verdicted
against it.

Exit code:
    0  no regression — every metric is green or yellow against the baseline.
    1  at least one candidate crossed a red threshold against the baseline.
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
    """Score two CSVs and produce a markdown delta table.

    Thin wrapper over `compare_n` preserved for the iter-13 callers. New
    callers should use `compare_n` directly to support arbitrary input counts.

    Returns:
        (table_markdown, exit_code) — exit_code is 1 if any metric was red.
    """
    return compare_n([("Baseline", baseline_csv), ("Candidate", candidate_csv)])


def compare_n(inputs: list[tuple[str, Path]]) -> tuple[str, int]:
    """Score N labeled CSVs and produce a markdown delta table.

    The first entry is the baseline; every other entry is verdicted against
    it. Each row in the output table shows one metric, one column per input
    plus a final per-candidate verdict column.

    Args:
        inputs: Ordered list of `(label, csv_path)` pairs, at least 2 entries.

    Returns:
        (table_markdown, exit_code) — exit_code is 1 if any candidate had a
        red verdict on any metric.
    """
    if len(inputs) < 2:
        raise ValueError(
            f"compare_n needs at least 2 inputs (1 baseline + 1 candidate); got {len(inputs)}."
        )

    scored: list[tuple[str, Path, dict[str, Any]]] = []
    for label, csv_path in inputs:
        scored.append((label, csv_path, score(csv_path, out_dir=None)))

    baseline_label, baseline_path, baseline_metrics = scored[0]
    candidates = scored[1:]

    headers: list[str] = ["Metric", baseline_label]
    for label, _, _ in candidates:
        headers.append(label)
        headers.append(f"Δ {label}")
        headers.append(f"Verdict {label}")

    rows: list[list[Any]] = []
    any_red = False
    for spec in METRICS:
        b_val = baseline_metrics.get(spec.key)
        row: list[Any] = [spec.label, spec.fmt_value(b_val)]
        for _, _, cand_metrics in candidates:
            c_val = cand_metrics.get(spec.key)
            v = spec.verdict(b_val, c_val)
            if v == RED:
                any_red = True
            row.append(spec.fmt_value(c_val))
            row.append(spec.fmt_delta(b_val, c_val))
            row.append(v)
        rows.append(row)

    table = _md_table(headers, rows)
    table += "\n\n"
    table += f"Baseline ({baseline_label}): `{baseline_path}`\n"
    for label, csv_path, _ in candidates:
        table += f"Candidate ({label}): `{csv_path}`\n"
    return table, (1 if any_red else 0)


def _parse_inputs_arg(raw: list[str]) -> list[tuple[str, Path]]:
    """Parse `label=path` pairs from `--inputs`. The first is the baseline."""
    out: list[tuple[str, Path]] = []
    for entry in raw:
        if "=" not in entry:
            raise argparse.ArgumentTypeError(
                f"--inputs entries must be `label=path`; got '{entry}'."
            )
        label, _, path = entry.partition("=")
        label = label.strip()
        path = path.strip()
        if not label or not path:
            raise argparse.ArgumentTypeError(
                f"--inputs entries must have a non-empty label and path; got '{entry}'."
            )
        out.append((label, Path(path)))
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval.compare_configs",
        description="Side-by-side metric comparison of N labeled CSVs.",
    )
    # 2-input legacy API: --baseline + --candidate.
    p.add_argument("--baseline", type=Path, default=None,
                   help="Labeled CSV from the prior config (2-input mode).")
    p.add_argument("--candidate", type=Path, default=None,
                   help="Labeled CSV from the new config under evaluation (2-input mode).")
    # N-input mode: --inputs label1=path1 label2=path2 ...
    p.add_argument(
        "--inputs", nargs="+", default=None,
        help="N-input mode: space-separated `label=path` pairs. The first entry "
             "is the baseline; every other entry is verdicted against it.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)

    legacy_pair = args.baseline is not None and args.candidate is not None
    n_input_mode = args.inputs is not None

    if legacy_pair and n_input_mode:
        print("ERROR: pass either --baseline/--candidate OR --inputs, not both.",
              file=sys.stderr)
        return 2
    if not legacy_pair and not n_input_mode:
        print("ERROR: pass --baseline + --candidate, or --inputs label1=path1 ...",
              file=sys.stderr)
        return 2

    if n_input_mode:
        inputs = _parse_inputs_arg(args.inputs)
        table, exit_code = compare_n(inputs)
    else:
        table, exit_code = compare(args.baseline, args.candidate)

    print(table)
    if exit_code != 0:
        print(f"\n{RED} Regression detected — exit 1.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
