#!/usr/bin/env bash
# Runs Drizzle introspect + datamodel-codegen and fails if either produces a diff against committed files.
# Consumed by .github/workflows/codegen-drift.yml (Wave 2) and locally via `make drift`.
set -euo pipefail

if [ -z "${SUPABASE_DEV_DB_URL:-}" ]; then
  echo "ERROR: SUPABASE_DEV_DB_URL is required" >&2
  exit 2
fi

# D-00-03 hard guard: web/drizzle/migrations must NOT exist or must be empty
if [ -d web/drizzle/migrations ] && [ -n "$(ls -A web/drizzle/migrations 2>/dev/null || true)" ]; then
  echo "ERROR: web/drizzle/migrations must be empty — Supabase CLI owns migrations (D-00-03)" >&2
  exit 1
fi

echo "==> Drizzle introspect"
(cd web && pnpm exec drizzle-kit pull)

echo "==> Pydantic codegen"
datamodel-codegen \
  --input-file-type postgres \
  --url "$SUPABASE_DEV_DB_URL" \
  --output worker/workers/lib/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-schema-description \
  --extra-fields-config extra=forbid 2>/dev/null || \
datamodel-codegen \
  --input-file-type postgres \
  --url "$SUPABASE_DEV_DB_URL" \
  --output worker/workers/lib/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-schema-description

echo "==> Diff check"
git diff --exit-code -- web/db/schema.ts worker/workers/lib/models.py
echo "OK: no drift"
