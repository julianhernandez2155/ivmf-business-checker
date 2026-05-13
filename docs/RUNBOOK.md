# RUNBOOK — Business Checker production runs

Single-page reference. If a step is missing here, it doesn't belong in a
production run.

## Pre-flight

- [ ] `.env` has `PERPLEXITY_API_KEY`, `FIRECRAWL_API_KEY`, `APIFY_API_TOKEN`,
      and `ANTHROPIC_API_KEY` set.
- [ ] Perplexity account tier matches `--workers` (Tier 0 = 1, Tier 1 = 3,
      Tier 2 = 8). Lower workers if 429s start appearing.
- [ ] Cost cap: pricing is roughly $0.005–0.05 per row. For a 709-row run
      that means $4–40 (Perplexity + Firecrawl + Apify combined). Confirm
      budget before kicking off.
- [ ] Decide caching:
        - **Default:** use cache. Resumable, idempotent under the
          (name, website, city, state, pipeline_fingerprint) key.
        - **--no-cache:** force fresh calls. Use only when you want to
          regenerate verdicts under the same config (e.g., Perplexity
          quality drift suspected).
- [ ] Pick the pipeline. Production = `v11` until iter 14 ships.

## Pick a pipeline

| `--pipeline` | When to use |
|---|---|
| `v10` | Regression anchor. Pre-FB-recency baseline. Don't ship to clients. |
| `v11` | **Production default.** iter 10 + Facebook recency. The documented shippable. |
| `v12_current_prod` | What production silently ran during iter 12 (metadata + marketplace-residue + verify-flagged, FB/IG off). Exposed so the leak is auditable. **Not recommended** until the iter-12 regressions are diagnosed. |
| `v12_full` | Everything on (FB, IG, metadata, marketplace-residue, verify-flagged). Use for eval-only side-by-side comparisons. Don't ship. |

The flag is **required** — both `run_checker.py` and `eval/rerun_sample.py`
refuse to start without `--pipeline <name>` since iter 13. This is by
design: production and eval cannot drift silently.

## Run

```bash
# Production 709-row run, iter-11 frozen config:
python run_checker.py --input ../data/BMOSG_All_Businesses.xlsx \
    --workers 3 --pipeline v11
```

Outputs land under `Runs/<stem>_<timestamp>/`:
- `run.log` — full session log. The first ~30 lines record the resolved
  pipeline config + fingerprint, so you can prove which toggles were used.
- `checkpoint.csv` — resumable progress. Re-run the same command to resume.
- `<stem>_Results.xlsx` — final output. Hand off to analysts.

## Eval after a run

```bash
# Re-run the AI on the 60-row labeled sample under the same config.
python -m eval.rerun_sample --pipeline v11 \
    --sample eval/datasets/bmosg_v1_eval_sample.csv \
    --input-xlsx ../data/BMOSG_All_Businesses.xlsx \
    --out eval/reports/v11_<date>/predictions.csv

# Score it.
python -m eval.score --labeled eval/reports/v11_<date>/predictions.csv \
    --out-dir eval/reports/v11_<date>/

# Read the side-by-side delta vs. the prior baseline.
python -m eval.compare_configs \
    --baseline eval/datasets/bmosg_v1_iteration_11_fb.csv \
    --candidate eval/reports/v11_<date>/predictions.csv
```

### Reading `compare_configs` output

Five metrics, all signed so improvement is unambiguous:

| Verdict | Meaning |
|---|---|
| ✅ | Candidate equals or beats baseline. |
| ⚠️ | Within noise band (±2pp on decisive accuracy, ±1 on harmful flips). Probably random churn, not a real regression. |
| ❌ | Crossed the threshold. Investigate before shipping. Exit code is 1 if any row is ❌. |

A ❌ on `harmful_flips_active_to_closed` (false-positive on Active) is
operationally the most expensive — it means real customers get marked
closed and dropped from outreach.

## Rollback

A 709-row run is interruptible. To abort cleanly:

1. Hit `Ctrl+C` in the terminal where `run_checker.py` is running.
2. `run.log` records the interrupt. `checkpoint.csv` has every row
   already completed (status, evidence, citations).
3. Re-run the exact same command later to resume from the checkpoint.
   The cache + checkpoint mean already-completed rows do not re-bill.
4. To **discard** an in-progress run instead of resuming, delete the
   `Runs/<stem>_<timestamp>/` directory and re-run fresh.

Do not edit `checkpoint.csv` by hand. Use `tools/checkpoint.py`'s
`rewrite_checkpoint()` if the file is corrupted.
