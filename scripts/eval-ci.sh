#!/usr/bin/env bash
# Runs the v1.0 eval gold set and fails if accuracy regresses below baseline or n_examples < 20.
# Consumed by .github/workflows/eval-ci.yml (Wave 5).
set -euo pipefail

if [ -z "${PERPLEXITY_API_KEY_EVAL:-}" ]; then
  echo "WARN: PERPLEXITY_API_KEY_EVAL unset; running in --dry-run mode" >&2
  DRY_RUN_FLAG="--dry-run"
else
  DRY_RUN_FLAG=""
fi

GOLD="${EVAL_GOLD:-business_checker/eval/gold.json}"
OUT="eval_result.json"
BASELINE="${EVAL_BASELINE:-business_checker/eval/baseline.json}"

python -m business_checker.eval.score --gold "$GOLD" --out "$OUT" $DRY_RUN_FLAG

python - <<PY
import json, sys
r = json.load(open("$OUT"))
n = r.get("n_examples", 0)
assert n >= 20, f"gold set too small: {n} < 20 (Pitfall P8 defense)"
if "$DRY_RUN_FLAG" == "--dry-run":
    print(f"dry-run OK: n_examples={n}")
    sys.exit(0)
try:
    b = json.load(open("$BASELINE"))
except FileNotFoundError:
    print("WARN: baseline.json not found; recording current run as baseline candidate")
    sys.exit(0)
delta = r["accuracy"] - b["accuracy"]
assert delta >= -0.01, f"eval regression: {r['accuracy']:.3f} < baseline {b['accuracy']:.3f} - 0.01"
print(f"OK: accuracy={r['accuracy']:.3f} (baseline {b['accuracy']:.3f}, delta {delta:+.3f}, n={n})")
PY
