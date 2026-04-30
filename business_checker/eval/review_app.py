"""Streamlit labeling UI for Business Checker eval datasets.

Single-labeler workflow.  Reads a sample CSV, displays one business at a time,
writes human labels back to the same CSV after every save.

Run with:
    streamlit run eval/review_app.py -- --dataset eval/datasets/<name>.csv
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse as up
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DATASET: str = "eval/datasets/bmosg_v1_eval_sample.csv"

LABEL_OPTIONS: list[str] = [
    "",  # placeholder — forces user to make a choice
    "Active",
    "Likely Closed",
    "Uncertain",
    "No Web Presence",
    "Unable to Determine",
]

MIN_JUSTIFICATION_CHARS: int = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def quick_links(name: str) -> dict[str, str]:
    """Build pre-filled search URLs for a business name.

    Args:
        name: The business name to search for.

    Returns:
        Dict mapping platform label to URL string.
    """
    q = up.quote_plus(name)
    return {
        "Google": f"https://www.google.com/search?q={q}",
        "Google Maps": f"https://www.google.com/maps/search/{q}",
        "Facebook": f"https://www.facebook.com/search/pages?q={q}",
        "Instagram": f"https://www.instagram.com/explore/search/keyword/?q={q}",
        "LinkedIn": f"https://www.linkedin.com/search/results/companies/?keywords={q}",
    }


def load_dataset(path: Path) -> pd.DataFrame:
    """Load the labeled CSV from disk.

    Args:
        path: Path to the CSV file.

    Returns:
        DataFrame with all columns, including human review columns.
    """
    df = pd.read_csv(path, dtype={"predicted_confidence": str})
    for col in ("human_label", "human_justification", "reviewed_at"):
        if col not in df.columns:
            df[col] = ""
    df["human_label"] = df["human_label"].fillna("")
    df["human_justification"] = df["human_justification"].fillna("")
    df["reviewed_at"] = df["reviewed_at"].fillna("")
    return df


def save_label(
    df: pd.DataFrame,
    idx: int,
    label: str,
    justification: str,
    dataset_path: Path,
) -> pd.DataFrame:
    """Write a label for one row and persist to disk.

    This function creates a new DataFrame (immutable pattern) rather than
    mutating the input, then writes it to disk.

    Args:
        df: The current full DataFrame.
        idx: Integer position (iloc) of the row being labeled.
        label: The chosen human label.
        justification: Free-text justification.
        dataset_path: Path to write the updated CSV.

    Returns:
        Updated DataFrame with the label applied to row idx.
    """
    updated = df.copy()
    updated.at[df.index[idx], "human_label"] = label
    updated.at[df.index[idx], "human_justification"] = justification
    updated.at[df.index[idx], "reviewed_at"] = datetime.now(tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    updated.to_csv(dataset_path, index=False)
    return updated


# ---------------------------------------------------------------------------
# CLI parsing (runs before Streamlit hijacks argv)
# ---------------------------------------------------------------------------


def _parse_dataset_path() -> Path:
    """Extract --dataset from sys.argv, ignoring Streamlit's own flags.

    Returns:
        Path to the dataset CSV.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    # Streamlit passes its own argv; ignore unknown args.
    args, _ = parser.parse_known_args()
    return args.dataset


# ---------------------------------------------------------------------------
# Main Streamlit app
# ---------------------------------------------------------------------------


def main() -> None:
    """Streamlit entry point — renders the labeling UI."""
    st.set_page_config(page_title="Business Checker Eval Labeler", layout="wide")

    dataset_path = _parse_dataset_path()

    # ------------------------------------------------------------------
    # Session state bootstrap
    # ------------------------------------------------------------------
    if "cursor" not in st.session_state:
        st.session_state.cursor = 0
    if "dataset_path" not in st.session_state or st.session_state.dataset_path != str(
        dataset_path
    ):
        st.session_state.dataset_path = str(dataset_path)
        st.session_state.cursor = 0

    # Always load fresh from disk so saves are reflected immediately.
    if not dataset_path.exists():
        st.error(f"Dataset not found: {dataset_path}")
        st.stop()

    df = load_dataset(dataset_path)
    total = len(df)

    if total == 0:
        st.warning("Dataset is empty.")
        st.stop()

    cursor: int = st.session_state.cursor
    cursor = max(0, min(cursor, total - 1))

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    completed = int((df["human_label"].str.strip() != "").sum())
    with st.sidebar:
        st.header("Progress")
        st.metric("Labeled", f"{completed} / {total}")
        st.progress(completed / total)
        st.caption(f"Dataset: {dataset_path.name}")
        st.caption(f"Row {cursor + 1} of {total}")

    # ------------------------------------------------------------------
    # Current row
    # ------------------------------------------------------------------
    row = df.iloc[cursor]
    name: str = str(row.get("name", ""))
    website: str = str(row.get("website", ""))
    city: str = str(row.get("city", ""))
    state_val: str = str(row.get("state", ""))
    pred_status: str = str(row.get("predicted_status", ""))
    pred_conf: str = str(row.get("predicted_confidence", ""))
    pred_evidence: str = str(row.get("predicted_evidence", ""))
    pred_citations: str = str(row.get("predicted_citations", ""))
    current_label: str = str(row.get("human_label", "") or "")
    current_just: str = str(row.get("human_justification", "") or "")

    location_str = ", ".join(part for part in [city, state_val] if part and part != "nan")

    # ------------------------------------------------------------------
    # Business header
    # ------------------------------------------------------------------
    st.progress((cursor + 1) / total, text=f"Row {cursor + 1} of {total}")
    st.markdown(f"## {name}")
    if website and website != "nan":
        st.markdown(f"[{website}]({website})")
    if location_str:
        st.caption(location_str)

    # ------------------------------------------------------------------
    # Predicted info + quick links side by side
    # ------------------------------------------------------------------
    col_pred, col_links = st.columns([2, 1])

    with col_pred:
        st.subheader("AI Prediction")
        st.markdown(f"**Status:** `{pred_status}` &nbsp; **Confidence:** {pred_conf}%")
        st.markdown("**Evidence:**")
        st.text_area("evidence_display", value=pred_evidence, height=120, disabled=True, label_visibility="collapsed")
        if pred_citations and pred_citations != "nan":
            with st.expander("Citations"):
                for url in pred_citations.split(", "):
                    url = url.strip()
                    if url:
                        st.markdown(f"- [{url}]({url})")

    with col_links:
        st.subheader("Quick Links")
        for platform, url in quick_links(name).items():
            st.markdown(f"[{platform}]({url})")

    st.divider()

    # ------------------------------------------------------------------
    # Labeling form
    # ------------------------------------------------------------------
    with st.form(key=f"label_form_{cursor}", clear_on_submit=False):
        label_index = LABEL_OPTIONS.index(current_label) if current_label in LABEL_OPTIONS else 0
        chosen_label = st.radio(
            "Your label",
            options=LABEL_OPTIONS[1:],  # hide the empty placeholder in radio
            index=max(0, label_index - 1),
            horizontal=True,
        )
        justification = st.text_area(
            "Justification (≥10 chars required)",
            value=current_just,
            height=80,
            placeholder="Describe what you found across the sources you checked.",
        )

        nav_col1, nav_col2, nav_col3 = st.columns(3)
        with nav_col1:
            save_clicked = st.form_submit_button("Save & Next", type="primary")
        with nav_col2:
            prev_clicked = st.form_submit_button("Previous")
        with nav_col3:
            skip_clicked = st.form_submit_button("Skip")

    # ------------------------------------------------------------------
    # Button logic (outside form to allow state mutation)
    # ------------------------------------------------------------------
    if save_clicked:
        if not chosen_label:
            st.error("Select a label before saving.")
        elif len(justification.strip()) < MIN_JUSTIFICATION_CHARS:
            st.error(f"Justification must be at least {MIN_JUSTIFICATION_CHARS} characters.")
        else:
            updated_df = save_label(df, cursor, chosen_label, justification, dataset_path)
            df = updated_df
            st.session_state.cursor = min(cursor + 1, total - 1)
            st.rerun()

    if prev_clicked:
        st.session_state.cursor = max(cursor - 1, 0)
        st.rerun()

    if skip_clicked:
        st.session_state.cursor = min(cursor + 1, total - 1)
        st.rerun()


if __name__ == "__main__":
    main()
