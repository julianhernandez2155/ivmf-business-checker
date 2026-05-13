"""Sonnet adjudicator: structured evidence → verdict.

Iter-14 architectural rule: the gather layer (Perplexity v11, scraped
Perplexity citations, or Exa+Firecrawl) builds `BusinessEvidence`; this
adjudicator decides the verdict. No tools. Evidence in, verdict out.

The same instance is shared between Branch A1, A2, and B — that's what
makes the branch comparison honest. Any decisive-accuracy delta is
attributable to retrieval, not reasoning.

MODEL_ID was resolved at Phase 1 step 1 via `python -m tools.resolve_model`:
    claude-sonnet-4-6  — latest non-deprecated Sonnet 4.x (created 2026-02-17).
    claude-opus-4-7    — escalation target if Sonnet goldens fail (2026-04-14).

Both IDs were observed live via `client.models.list()` on 2026-05-13 and
recorded in this file. If a future caller wants to verify drift, re-run
`python -m tools.resolve_model` and compare.

Plan reference: docs/2026-05-13-iter14-search-vs-reasoning-spike.md
§Phase 1 step 1 + step 3.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from tools.evidence_schema import BusinessEvidence

logger = logging.getLogger(__name__)


MODEL_ID = "claude-sonnet-4-6"
ESCALATION_MODEL_ID = "claude-opus-4-7"

ADJUDICATOR_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "adjudicator_v1.md"


VALID_STATUSES = ("Active", "Likely Closed", "Uncertain", "No Web Presence")


class AdjudicationResult(BaseModel):
    """Pydantic schema for the adjudicator's structured output.

    Mirrors the shape `check_business()` returns today so downstream code
    paths (cache rows, CSV columns, eval scoring) do not change.
    """

    status: str = Field(..., description="One of: Active | Likely Closed | Uncertain | No Web Presence")
    confidence: int = Field(..., ge=0, le=100)
    evidence: str = Field(..., min_length=1)
    requires_review: bool = False
    review_reason: str | None = None

    def validate_status(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Adjudicator returned invalid status '{self.status}'. "
                f"Must be one of {VALID_STATUSES}."
            )


def _json_default(obj: Any) -> Any:
    """JSON serializer that handles dataclasses, dates, and enums."""
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if isinstance(obj, set):
        return sorted(obj)
    return str(obj)


def serialize_evidence(evidence: BusinessEvidence) -> str:
    """Render `BusinessEvidence` as a deterministic JSON string for the prompt."""
    return json.dumps(asdict(evidence), default=_json_default, sort_keys=True, indent=2)


def _load_system_prompt() -> str:
    """Read the prompt markdown from disk. Cached after first read."""
    if not ADJUDICATOR_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Adjudicator prompt missing at {ADJUDICATOR_PROMPT_PATH}. "
            f"Phase 1 step 3 prerequisite — re-create it before running the adjudicator."
        )
    return ADJUDICATOR_PROMPT_PATH.read_text(encoding="utf-8")


def parse_response(raw: str) -> AdjudicationResult:
    """Parse a model response into `AdjudicationResult`.

    The prompt forbids prose outside the JSON, but tolerate code-fenced
    JSON. On schema failure: surface as Uncertain + flag for review
    (per plan: no retries on schema failure — we want the noise visible).
    """
    text = raw.strip()
    if text.startswith("```"):
        # Strip a leading ```json or ``` fence.
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Adjudicator JSON parse failed: %s", exc)
        return AdjudicationResult(
            status="Uncertain",
            confidence=0,
            evidence=f"Adjudicator response was not valid JSON: {exc}",
            requires_review=True,
            review_reason="schema_failure",
        )

    try:
        result = AdjudicationResult(**payload)
    except ValidationError as exc:
        logger.warning("Adjudicator schema validation failed: %s", exc)
        return AdjudicationResult(
            status="Uncertain",
            confidence=0,
            evidence=f"Adjudicator response did not match schema: {exc}",
            requires_review=True,
            review_reason="schema_failure",
        )

    try:
        result.validate_status()
    except ValueError as exc:
        logger.warning("Adjudicator returned invalid status: %s", exc)
        return AdjudicationResult(
            status="Uncertain",
            confidence=0,
            evidence=f"Adjudicator returned invalid status: {exc}",
            requires_review=True,
            review_reason="invalid_status",
        )

    return result


def adjudicate(
    evidence: BusinessEvidence,
    api_key: str,
    model_id: str = MODEL_ID,
) -> AdjudicationResult:
    """Call the adjudicator on a single `BusinessEvidence` and return its verdict.

    Args:
        evidence: Structured evidence built by the gather layer.
        api_key: ANTHROPIC_API_KEY.
        model_id: Override for the pinned `MODEL_ID` (used by tests + Opus
            escalation). Default `claude-sonnet-4-6`.

    Returns:
        `AdjudicationResult` mirroring the existing `check_business()` shape.

    Cost note: ~$0.005/row at Sonnet 4.6 with the prompt cached.
    """
    import anthropic  # imported lazily so unit tests don't require the SDK

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _load_system_prompt()
    user_payload = serialize_evidence(evidence)

    logger.info("Adjudicating %r with model=%s", evidence.name, model_id)

    response = client.messages.create(
        model=model_id,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    "Adjudicate the business below. Return ONLY the JSON object "
                    "described in the system prompt — no prose outside the JSON.\n\n"
                    "Evidence:\n```json\n" + user_payload + "\n```"
                ),
            }
        ],
    )

    raw = "".join(block.text for block in response.content if block.type == "text")
    return parse_response(raw)
