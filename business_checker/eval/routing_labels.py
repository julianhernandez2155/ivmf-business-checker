"""Routing labels for triage output (locked 2026-05-13).

Single source of truth for the 6-value schema defined in
.planning/2026-05-13-decision-triage-not-oracle.md.

Phase 0: imported by eval/score.py to emit a distribution report (informational).
Phase 2: imported by the worker's post-adjudicator mapping function (gated).
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class RoutingLabel(str, Enum):
    """Six-value routing label enum.

    Order matches the mapping rules table in
    .planning/2026-05-13-decision-triage-not-oracle.md. The string values are
    user-facing and used directly as keys in the eval `routing_distribution`
    JSON object — DO NOT rename without updating baseline.json + downstream
    Phase 2 mapping function.
    """

    ACTIVE_AUTO_ACCEPTED = "Active - auto accepted"
    LIKELY_CLOSED_STRONG_EVIDENCE = "Likely Closed - strong evidence"
    UNCERTAIN_MANUAL_REVIEW = "Uncertain - manual review recommended"
    UNCERTAIN_OUTREACH = "Uncertain - outreach recommended"
    LIKELY_CLOSED_OUTREACH = "Likely Closed - outreach recommended"
    NO_CONTACT_AVAILABLE = "No contact available"


def stub_label_from_gold(example: dict[str, Any]) -> RoutingLabel:
    """Phase 0 stub mapping — uses ONLY v1.0 gold-set fields.

    Phase 2 replaces this with a real mapping over
    (verdict, confidence, requires_review, contact_available)
    per the triage decision doc. Phase 0 does not have requires_review
    or contact_available, so we approximate from verdict + confidence only.

    DO NOT use this stub for production routing. It exists so the
    eval-CI report has a populated distribution column from day one.

    Args:
        example: A gold-set example dict. Recognized keys:
            - expected_status / verdict: one of
              {Active, Likely Closed, Uncertain, No Web Presence} (case-insensitive)
            - expected_confidence / confidence: int 0-100 or float 0-1

    Returns:
        A RoutingLabel value. Always returns one of the 6 buckets; defaults
        to UNCERTAIN_MANUAL_REVIEW for unrecognized or ambiguous inputs.
    """
    verdict_raw = example.get("expected_status") or example.get("verdict") or ""
    verdict = str(verdict_raw).strip().lower()

    confidence_raw = example.get("expected_confidence") or example.get("confidence") or 0.0
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    # Accept either 0-1 or 0-100 scales.
    if confidence > 1.0:
        confidence = confidence / 100.0

    if verdict == "active" and confidence >= 0.70:
        return RoutingLabel.ACTIVE_AUTO_ACCEPTED
    if verdict in ("likely_closed", "likely closed", "closed") and confidence >= 0.70:
        return RoutingLabel.LIKELY_CLOSED_STRONG_EVIDENCE
    if verdict in ("likely_closed", "likely closed", "closed"):
        return RoutingLabel.LIKELY_CLOSED_OUTREACH
    if verdict in ("no web presence", "no_web_presence"):
        return RoutingLabel.NO_CONTACT_AVAILABLE
    return RoutingLabel.UNCERTAIN_MANUAL_REVIEW


def empty_distribution() -> dict[str, int]:
    """Return a fresh distribution dict with all 6 buckets at zero.

    The dict shape (all 6 keys present, even when zero) is the contract
    consumed by eval-ci. Phase 2 distribution-drift gates assume this shape.
    """
    return {label.value: 0 for label in RoutingLabel}
