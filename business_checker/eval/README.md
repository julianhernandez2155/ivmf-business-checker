# Eval Harness

Phase 0 ANALYTICS-04 measurement surface for the Business Checker. This directory
ships the gold set, the scorer, and the frozen baseline that gates every PR
through `.github/workflows/eval-ci.yml`.

## How to run

```bash
python -m business_checker.eval.score \
    --gold business_checker/eval/gold.json \
    --out eval_result.json
```

`--dry-run` is accepted for forward-compatibility with Phase 2 (where the
scorer will optionally make live Perplexity calls); Phase 0 is fully offline,
so the flag is currently a no-op.

## Output JSON shape (required by ANALYTICS-04 CI gate)

```json
{
  "accuracy": 0.689,
  "n_examples": 58,
  "routing_distribution": {
    "Active - auto accepted": 19,
    "Likely Closed - strong evidence": 15,
    "Uncertain - manual review recommended": 13,
    "Uncertain - outreach recommended": 0,
    "Likely Closed - outreach recommended": 9,
    "No contact available": 2
  },
  "details": [...]
}
```

`accuracy` is overall string-equality between `predicted_status` and
`expected_status` across all gold examples. `details` carries the raw
example list so failing CI runs can be debugged from the uploaded artifact.

## Baseline

`baseline.json` is the frozen accuracy floor for ANALYTICS-04. CI compares
each run against it and fails if:

```
accuracy < baseline.accuracy - 0.01
```

Update only after intentional improvement: rerun the scorer, replace
`baseline.json` in the same PR that introduces the improvement, and explain
the delta in the commit message.

## Pitfall P8 defense (n_examples >= 20)

The CI gate (`scripts/eval-ci.sh`) also asserts `n_examples >= 20`. The
canonical failure mode this guards against is an RLS-filtered gold set
silently returning zero rows — false-pass on an empty fixture.

If you see CI fail with "gold set too small", do **NOT** shrink the
threshold. Investigate why the gold set is shorter than expected:
- Is `gold.json` truncated or malformed?
- Did a migration filter the labeled-sample table?
- Did a recent commit accidentally remove gold rows?

Current gold set: 58 examples — well above the floor.

## Routing-label distribution (D-00-12)

`routing_distribution` is informational in Phase 0. The eval-CI workflow
uploads it as an artifact but does **not** fail on drift.

The 6-value `RoutingLabel` enum lives in
[`business_checker/eval/routing_labels.py`](./routing_labels.py) and is the
single source of truth for the schema defined in
[`.planning/2026-05-13-decision-triage-not-oracle.md`](../../.planning/2026-05-13-decision-triage-not-oracle.md).

Phase 2 imports the same enum for the production mapping function and adds
a distribution-drift gate on top of the existing accuracy gate. The Phase 0
mapping is a stub (`stub_label_from_gold`) using only `verdict + confidence`
because the gold set doesn't yet carry `requires_review` or
`contact_available` — Phase 2 will retrofit those fields.

## Adding gold examples

Phase 0 gold set: hand-curated from `bmosg_v1_eval_sample.csv` (the BMSG
v1.0 labeled sample). The canonical source going forward is the
`manual_labels` table (Phase 3 schema). To extend the gold set today:

1. Append rows to `gold.json` (each row needs `expected_status` +
   `expected_confidence` + identifying fields).
2. Rerun the scorer.
3. Update `baseline.json` if accuracy moves intentionally.
4. Open the PR — CI will validate the new contract automatically.

## Files in this directory

| File | Purpose |
| --- | --- |
| `gold.json` | Phase 0 gold set (58 examples from BMSG v1 sample) |
| `baseline.json` | Frozen accuracy floor consumed by `scripts/eval-ci.sh` |
| `routing_labels.py` | 6-value `RoutingLabel` enum (D-00-12 source of truth) |
| `score.py` | Scorer; `--gold/--out` mode is the Phase 0 JSON adapter, `--labeled` is the legacy v1.0 CSV report |
| `datasets/` | v1.0 labeled CSVs and iteration prediction files (unchanged) |
| `reports/` | v1.0 markdown reports (unchanged) |

## Cross-references

- ANALYTICS-04 (Phase 0 success criteria): `.planning/REQUIREMENTS.md`
- D-00-12 (routing-aware measurement surface):
  `.planning/phases/00-foundation/00-CONTEXT.md`
- Pitfall P8 (RLS-filtered gold set / n_examples assertion):
  `.planning/research/PITFALLS.md`
- CI gate script: `scripts/eval-ci.sh`
- CI workflow: `.github/workflows/eval-ci.yml`
