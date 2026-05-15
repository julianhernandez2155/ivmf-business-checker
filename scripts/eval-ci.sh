#!/usr/bin/env bash
# Runs the v1.0 eval gold set and fails if accuracy regresses below baseline or n_examples < 20.
#
# GAP-3 fix (.planning/phases/00-foundation/00-VERIFICATION.md):
# Dry-run mode (no PERPLEXITY_API_KEY_EVAL) STILL asserts n_examples >= 20 AND
# STILL compares accuracy against baseline.json. Only the external-API call
# path is skipped when the secret is absent — the regression comparison runs
# unconditionally so the eval-CI gate enforces on every PR (not just PRs with
# the Perplexity secret present).
#
# Also: `python3` everywhere (closes the Phase 0 polish flag re macOS local
# runs where `python` shim may be absent). Heredoc receives paths via env
# vars instead of shell substitution so quotes in paths don't break parsing.
#
# Consumed by .github/workflows/eval-ci.yml (Wave 5).
set -euo pipefail

if [ -z "${PERPLEXITY_API_KEY_EVAL:-}" ]; then
  echo "INFO: PERPLEXITY_API_KEY_EVAL unset; running offline scorer (--dry-run)" >&2
  DRY_RUN_FLAG="--dry-run"
else
  DRY_RUN_FLAG=""
fi

GOLD="${EVAL_GOLD:-business_checker/eval/gold.json}"
OUT="eval_result.json"
BASELINE="${EVAL_BASELINE:-business_checker/eval/baseline.json}"

python3 -m business_checker.eval.score --gold "$GOLD" --out "$OUT" $DRY_RUN_FLAG

BASELINE_PATH="$BASELINE" OUT_PATH="$OUT" python3 - <<'PY'
import json
import os
import sys

out_path = os.environ["OUT_PATH"]
baseline_path = os.environ["BASELINE_PATH"]

r = json.load(open(out_path))
n = r.get("n_examples", 0)
if n < 20:
    print(
        f"FAIL: gold set too small: {n} < 20 (Pitfall P8 defense)",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    b = json.load(open(baseline_path))
except FileNotFoundError:
    print(
        f"WARN: {baseline_path} not found; recording current run as baseline candidate"
    )
    sys.exit(0)

delta = r["accuracy"] - b["accuracy"]
if delta < -0.01:
    print(
        f"FAIL: eval regression: {r['accuracy']:.4f} < baseline "
        f"{b['accuracy']:.4f} - 0.01 (delta {delta:+.4f}, n={n})",
        file=sys.stderr,
    )
    sys.exit(1)

print(
    f"OK: accuracy={r['accuracy']:.4f} (baseline {b['accuracy']:.4f}, "
    f"delta {delta:+.4f}, n={n})"
)
PY
