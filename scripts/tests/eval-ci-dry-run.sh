#!/usr/bin/env bash
# GAP-3 regression test (.planning/phases/00-foundation/00-VERIFICATION.md):
# Proves scripts/eval-ci.sh dry-run path (no PERPLEXITY_API_KEY_EVAL) still
# loads baseline.json and exits non-zero on accuracy regression.
#
# Strategy: synthesize a tampered gold.json where every `predicted_status` is
# flipped to a wrong canonical label so the offline scorer collapses well
# below the 0.6897 baseline minus 0.01 tolerance. Then unset the secret and
# confirm scripts/eval-ci.sh exits non-zero.
#
# Two cases:
#   1. Tampered gold + no secret + standard baseline → MUST exit non-zero
#   2. Standard gold + no secret + standard baseline → MUST exit zero
#
# Idempotent: uses a temp dir wiped on EXIT; never mutates the real gold.json.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

GOLD_REAL="business_checker/eval/gold.json"
GOLD_TAMPERED="$TMP_DIR/gold-tampered.json"

# Tamper: flip every record's predicted_status to a guaranteed-wrong value so
# accuracy drops to ~0. Uses python3 so the test does not require jq.
GOLD_REAL="$GOLD_REAL" GOLD_TAMPERED="$GOLD_TAMPERED" python3 - <<'PY'
import json
import os
import pathlib

src_path = os.environ["GOLD_REAL"]
dst_path = os.environ["GOLD_TAMPERED"]

src = json.loads(pathlib.Path(src_path).read_text(encoding="utf-8"))
# gold.json is a list of dicts with expected_status + predicted_status keys
# (see business_checker/eval/score.py:_score_from_gold_json).
WRONG_MAP = {
    "Active": "Likely Closed",
    "Likely Closed": "Active",
    "Uncertain": "Active",
    "No Web Presence": "Active",
}
for r in src:
    if isinstance(r, dict) and "predicted_status" in r:
        cur = str(r["predicted_status"]).strip()
        r["predicted_status"] = WRONG_MAP.get(cur, "Active")
pathlib.Path(dst_path).write_text(json.dumps(src), encoding="utf-8")
PY

# Case 1: tampered gold must FAIL even with no secret
unset PERPLEXITY_API_KEY_EVAL
if EVAL_GOLD="$GOLD_TAMPERED" bash scripts/eval-ci.sh \
    > "$TMP_DIR/out-tampered.txt" 2>&1; then
  echo "FAIL: tampered gold did not regress; eval-ci.sh exited 0 in dry-run mode"
  cat "$TMP_DIR/out-tampered.txt"
  exit 1
else
  echo "PASS: tampered gold correctly failed eval-ci.sh in dry-run mode"
fi

# Case 2: standard gold should still PASS without the secret
unset PERPLEXITY_API_KEY_EVAL
if EVAL_GOLD="$GOLD_REAL" bash scripts/eval-ci.sh \
    > "$TMP_DIR/out-standard.txt" 2>&1; then
  echo "PASS: standard gold succeeded eval-ci.sh in dry-run mode"
else
  echo "FAIL: standard gold should pass dry-run; instead got:"
  cat "$TMP_DIR/out-standard.txt"
  exit 1
fi

echo "GAP-3 regression test PASS"
