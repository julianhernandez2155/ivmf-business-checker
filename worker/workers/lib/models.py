# Generated baseline derived from supabase/migrations/0001_init_schema.sql.
#
# In CI, `datamodel-codegen --input-file-type postgres --url $SUPABASE_DEV_DB_URL`
# regenerates this file from the live Supabase dev DB and `git diff --exit-code`
# fails the build on any drift (Pitfall P4 defense).
#
# DO NOT hand-edit. To update:
#   1. Apply schema migration in supabase/migrations/
#   2. From worker/: source .venv/bin/activate
#      datamodel-codegen \
#        --input-file-type postgres \
#        --url "$SUPABASE_DEV_DB_URL" \
#        --output workers/lib/models.py \
#        --output-model-type pydantic_v2.BaseModel \
#        --use-schema-description \
#        --extra-fields-config extra=forbid
#   3. Commit the regenerated file.
#
# Live regeneration is deferred until the ivmf-checker-dev Supabase project is
# provisioned (see STATE.md Open Externally-Blocked Items).
#
# ConfigDict(extra='forbid') is set on every model: unknown columns raise loudly
# (P4 defense — see .planning/research/PITFALLS.md §Pitfall 4).
#
# filename:  workers/lib/models.py
# generator: datamodel-code-generator
# baseline:  hand-derived from supabase/migrations/0001_init_schema.sql

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Businesses(BaseModel):
    """Canonical entity (CANON-05). Trigger-maintained current state via aggregator."""

    model_config = ConfigDict(extra='forbid')

    id: UUID
    name: str
    normalized_name: str | None = None
    ein: str | None = None
    website_domain: str | None = None
    phone_e164: str | None = None
    address_normalized: dict[str, Any] | None = None
    city: str | None = None
    state: str | None = None
    match_signals: dict[str, Any] | None = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Runs(BaseModel):
    """Per-upload run record. status: pending/parsing/running/paused/completed/errored."""

    model_config = ConfigDict(extra='forbid')

    id: UUID
    user_id: UUID
    status: str = 'pending'
    source_filename: str | None = None
    row_count: int | None = None
    cost_estimate_cents: int | None = 0
    cost_actual_cents: int | None = 0
    paused_at: datetime | None = None
    pause_reason: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RunRows(BaseModel):
    """Individual row of a run; unique on (run_id, row_index)."""

    model_config = ConfigDict(extra='forbid')

    id: UUID
    run_id: UUID
    row_index: int
    source_payload: dict[str, Any]
    business_id: UUID | None = None
    passes_completed: int = 0
    passes_required: int = 1
    status: str = 'pending'
    error_reason: str | None = None
    created_at: datetime


class Verifications(BaseModel):
    """APPEND-ONLY (CANON-06). BEFORE UPDATE/DELETE triggers raise P0001.

    Idempotency: UNIQUE (run_id, row_index, pass).
    method: perplexity / firecrawl / cache / admin_edit / email_response / aggregator.
    status: active / likely_closed / closed / uncertain / errored.
    """

    model_config = ConfigDict(extra='forbid')

    id: UUID
    business_id: UUID | None = None
    run_id: UUID | None = None
    row_index: int | None = None
    pass_: int = Field(default=1, alias='pass')
    method: str
    status: str | None = None
    confidence: Decimal | None = None
    provenance: dict[str, Any] | None = Field(default_factory=dict)
    match_signals: dict[str, Any] | None = Field(default_factory=dict)
    evidence: str | None = None
    source_url: str | None = None
    cost_cents: int | None = 0
    from_cache: bool | None = False
    created_at: datetime


class ApiCalls(BaseModel):
    """Outbound API dedup (CANON-07; Pitfall P1 defense). UNIQUE (provider, request_hash)."""

    model_config = ConfigDict(extra='forbid')

    id: UUID
    provider: str
    request_hash: str
    response_payload: dict[str, Any] | None = None
    cost_cents: int | None = None
    created_at: datetime


class AppConfig(BaseModel):
    """Admin-mutable settings (D-00-05, D-00-10). audit_log_trigger attached."""

    model_config = ConfigDict(extra='forbid')

    key: str
    value: dict[str, Any]
    description: str | None = None
    updated_at: datetime


class ApiKeys(BaseModel):
    """Admin-managed API keys. Phase 0 schema only; Phase 2 wires encryption."""

    model_config = ConfigDict(extra='forbid')

    id: UUID
    provider: str
    label: str | None = None
    key_ciphertext: str | None = None
    is_primary: bool | None = False
    is_disabled: bool | None = False
    monthly_cap_cents: int | None = None
    low_balance_threshold_cents: int | None = None
    created_at: datetime
    updated_at: datetime


class BudgetLedger(BaseModel):
    """Append-only spend ledger. event_type: estimate / charge / reconcile / cap_hit."""

    model_config = ConfigDict(extra='forbid')

    id: int
    api_key_id: UUID | None = None
    event_type: str
    cents: int
    running_total_cents: int | None = None
    provider_truth_cents: int | None = None
    meta: dict[str, Any] | None = Field(default_factory=dict)
    created_at: datetime


class OutreachTickets(BaseModel):
    """STUB for Phase 4. Schema-only in Phase 0 so audit trigger has a target."""

    model_config = ConfigDict(extra='forbid')

    id: UUID
    run_id: UUID | None = None
    status: str = 'pending'
    token_hash: str | None = None
    approved_by: UUID | None = None
    created_at: datetime


class AuditLog(BaseModel):
    """Generic audit log (D-00-06). INSERT-only via trigger; UPDATE/DELETE revoked."""

    model_config = ConfigDict(extra='forbid')

    id: int
    actor_user_id: UUID | None = None
    action: str
    table_name: str
    row_pk: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    diff: dict[str, Any] | None = None
    request_id: str | None = None
    created_at: datetime


class WorkerHeartbeats(BaseModel):
    """D-00-11 item 5. Worker writes here each loop; Phase 2 watchdog reads."""

    model_config = ConfigDict(extra='forbid')

    worker_id: str
    last_seen_at: datetime
    hostname: str | None = None
    version: str | None = None
