"""Stratified sampler for Business Checker checkpoint CSVs.

Reads a checkpoint CSV produced by a Business Checker run, groups records by
AI_Status, and draws a fixed-size sample per status bucket.  The output CSV
includes empty columns for human review so it feeds directly into review_app.py.

Usage (CLI):
    python -m eval.sample \\
        --checkpoint Runs/<run>/checkpoint.csv \\
        --n-per-status 20 \\
        --seed 42 \\
        --out eval/datasets/my_sample.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical status values emitted by the Business Checker.
VALID_STATUSES: list[str] = [
    "Active",
    "Likely Closed",
    "Uncertain",
    "No Web Presence",
]

# Separator that splits evidence text from citation URLs in AI_Evidence.
_SOURCES_SEPARATOR: str = " | Sources: "

# Output column order for the labeled CSV.
OUTPUT_COLUMNS: list[str] = [
    "row_index",
    "name",
    "website",
    "city",
    "state",
    "predicted_status",
    "predicted_confidence",
    "predicted_evidence",
    "predicted_citations",
    "predicted_checked_at",
    "human_label",
    "human_justification",
    "reviewed_at",
]


def _load_city_state_from_xlsx(xlsx_path: Path) -> dict[int, tuple[str, str]]:
    """Read city + state from the input spreadsheet, keyed by row_index.

    The checkpoint CSV preserves only name/website. Disambiguating
    similarly-named businesses during labeling requires city/state, so the
    sampler joins back to the original input on row_index when given.

    Args:
        xlsx_path: Path to the input .xlsx (e.g. BMOSG_All_Businesses.xlsx).

    Returns:
        Dict mapping row_index (1-based, matching checkpoint convention)
        to (city, state) tuples. Missing values are empty strings.
    """
    import openpyxl  # local import — keeps eval module load light

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.rows)
    wb.close()

    headers = [str(c.value or "").strip().lower() for c in rows[0]]

    def find_col(*candidates: str) -> int | None:
        for cand in candidates:
            for idx, h in enumerate(headers):
                if cand in h:
                    return idx
        return None

    city_idx = find_col("city", "town", "municipality")
    state_idx = find_col("state", "province", "region")

    if city_idx is None and state_idx is None:
        logger.warning("No city/state columns found in %s — output will have empty city/state.", xlsx_path)
        return {}

    out: dict[int, tuple[str, str]] = {}
    # row_index in checkpoint is 1-based and skips the header row, so the
    # first data row in the xlsx (row index 1 in openpyxl) maps to
    # checkpoint row_index 2.
    for sheet_idx, row in enumerate(rows[1:], start=2):
        city = str(row[city_idx].value or "").strip() if city_idx is not None else ""
        state = str(row[state_idx].value or "").strip() if state_idx is not None else ""
        out[sheet_idx] = (city, state)
    return out


def _split_evidence(raw: str) -> tuple[str, str]:
    """Split a raw AI_Evidence value into (evidence, citations).

    Args:
        raw: The raw AI_Evidence string, which may contain a " | Sources: "
            suffix with citation URLs.

    Returns:
        Tuple of (evidence_text, citations_string).  citations_string is an
        empty string when no separator is found.
    """
    if _SOURCES_SEPARATOR in str(raw):
        left, right = str(raw).split(_SOURCES_SEPARATOR, maxsplit=1)
        return left.strip(), right.strip()
    return str(raw).strip(), ""


def stratified_sample(
    checkpoint_path: Path | str,
    n_per_status: int | None = 20,
    seed: int = 42,
    out_path: Path | str | None = None,
    input_xlsx: Path | str | None = None,
) -> pd.DataFrame:
    """Stratified sample of a checkpoint CSV by AI_Status.

    Args:
        checkpoint_path: Path to checkpoint.csv from a Business Checker run.
        n_per_status: Target records per status group.  If a group has fewer
            records than this, all are taken (with a warning logged).  Pass
            None to take every row in each bucket.
        seed: Random seed for reproducibility.
        out_path: If provided, write the sample CSV here.
        input_xlsx: Optional path to the input .xlsx used to produce the
            checkpoint. When provided, city + state are joined onto every
            sampled row for the labeler. When omitted, city/state are
            emitted as empty strings with a warning.

    Returns:
        DataFrame with columns: row_index, name, website, city, state,
        predicted_status, predicted_confidence (int), predicted_evidence,
        predicted_citations, predicted_checked_at, human_label (empty),
        human_justification (empty), reviewed_at (empty).
    """
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    raw = pd.read_csv(checkpoint_path, dtype={"AI_Confidence": str})
    if raw.empty:
        raise ValueError(f"Checkpoint file is empty: {checkpoint_path}")

    required_cols = {"AI_Status", "AI_Confidence", "AI_Evidence", "AI_Checked_At"}
    missing = required_cols - set(raw.columns)
    if missing:
        raise ValueError(f"Checkpoint missing required columns: {missing}")

    # Build sample group by group.
    buckets: list[pd.DataFrame] = []
    for status, group in raw.groupby("AI_Status", sort=False):
        if n_per_status is None:
            take_n = len(group)
        elif len(group) < n_per_status:
            logger.warning(
                "Status '%s' has only %d row(s) — taking all (requested %d).",
                status,
                len(group),
                n_per_status,
            )
            take_n = len(group)
        else:
            take_n = n_per_status

        buckets.append(group.sample(n=take_n, random_state=seed))

    if not buckets:
        logger.warning("No status buckets found in checkpoint — returning empty DataFrame.")
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    sample = pd.concat(buckets, ignore_index=True)

    # Split evidence text from citations.
    ev_and_cit = sample["AI_Evidence"].apply(_split_evidence)
    evidence_series = ev_and_cit.apply(lambda t: t[0])
    citations_series = ev_and_cit.apply(lambda t: t[1])

    # Join city + state from the input xlsx if provided.
    if input_xlsx is not None:
        location_lookup = _load_city_state_from_xlsx(Path(input_xlsx))
        cities = sample["row_index"].apply(lambda r: location_lookup.get(int(r), ("", ""))[0])
        states = sample["row_index"].apply(lambda r: location_lookup.get(int(r), ("", ""))[1])
    else:
        logger.warning(
            "No --input-xlsx provided — city/state columns will be empty in the labeling sample. "
            "Pass --input-xlsx to the original spreadsheet to enable disambiguation by location."
        )
        cities = pd.Series([""] * len(sample), index=sample.index)
        states = pd.Series([""] * len(sample), index=sample.index)

    output = pd.DataFrame(
        {
            "row_index": sample["row_index"],
            "name": sample["name"],
            "website": sample["website"],
            "city": cities,
            "state": states,
            "predicted_status": sample["AI_Status"],
            "predicted_confidence": sample["AI_Confidence"].astype(int),
            "predicted_evidence": evidence_series,
            "predicted_citations": citations_series,
            "predicted_checked_at": sample["AI_Checked_At"],
            "human_label": "",
            "human_justification": "",
            "reviewed_at": "",
        }
    )

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(out_path, index=False)
        logger.info("Sample written to %s (%d rows).", out_path, len(output))

    return output


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m eval.sample",
        description="Stratified sampler for Business Checker checkpoint CSVs.",
    )
    parser.add_argument("--checkpoint", required=True, type=Path, help="Path to checkpoint.csv")
    parser.add_argument(
        "--n-per-status",
        type=int,
        default=20,
        help="Records per status bucket (default: 20).  0 = take all.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path.  Defaults to eval/datasets/sample_<stem>.csv.",
    )
    parser.add_argument(
        "--input-xlsx",
        type=Path,
        default=None,
        help="Path to the original input .xlsx — when provided, city + state are joined onto each sampled row.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    n = args.n_per_status if args.n_per_status > 0 else None
    out = args.out or Path("eval/datasets") / f"sample_{args.checkpoint.parent.name}.csv"

    sample_df = stratified_sample(
        checkpoint_path=args.checkpoint,
        n_per_status=n,
        seed=args.seed,
        out_path=out,
        input_xlsx=args.input_xlsx,
    )
    print(f"Wrote {len(sample_df)} rows → {out}")
    print(sample_df["predicted_status"].value_counts().to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
