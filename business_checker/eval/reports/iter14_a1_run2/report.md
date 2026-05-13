# Eval Report — predictions

**Generated:** 2026-05-13 19:34 UTC
**Source:** eval/reports/iter14_a1_run2/predictions.csv
**Total labeled rows:** 60
**Excluded (Unable to Determine or empty):** 2

## Headline

**Overall agreement: 55.2% (95% Wilson CI: 42.5%–67.3%, n=58)**

## Canonical metrics (iter 13)

| Metric | Value |
| --- | --- |
| decisive_accuracy | 65.2% (n=46) |
| harmful_flips_total | 2 |
| harmful_flips_active_to_closed | 2 |
| harmful_flips_closed_to_active | 0 |
| review_queue_size | 0 |

## Slices (by reachability)

| Slice | n | Decisive acc. | Harmful (total) | A→C | C→A |
| --- | --- | --- | --- | --- | --- |
| all | 58 | 65.2% | 2 | 2 | 0 |
| reachable | 31 | 74.1% | 0 | 0 | 0 |
| unreachable-judgment | 6 | 0.0% | 0 | 0 | 0 |
| unreachable-metadata | 3 | 100.0% | 0 | 0 | 0 |
| unreachable-other | 2 | 100.0% | 0 | 0 | 0 |
| unreachable-social | 16 | 57.1% | 2 | 2 | 0 |

## Per-status metrics

| Status | n | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| Active | 22 | 74.1% | 90.9% | 0.816 |
| Likely Closed | 24 | 71.4% | 41.7% | 0.526 |
| Uncertain | 10 | 16.7% | 20.0% | 0.182 |
| No Web Presence | 2 | 0.0% | 0.0% | 0.000 |

## Confusion matrix

Rows = human label (true), columns = predicted label (AI).

| Predicted \ Human | Active | Likely Closed | Uncertain | No Web Presence |
| --- | --- | --- | --- | --- |
| Active | 20 | 0 | 2 | 0 |
| Likely Closed | 2 | 10 | 8 | 4 |
| Uncertain | 5 | 2 | 2 | 1 |
| No Web Presence | 0 | 2 | 0 | 0 |

## Calibration

| Confidence bucket | n | Agreement rate |
| --- | --- | --- |
| 0–49 | 12 | 16.7% |
| 50–59 | 0 | — |
| 60–69 | 5 | 0.0% |
| 70–79 | 12 | 66.7% |
| 80–89 | 16 | 68.8% |
| 90–100 | 13 | 84.6% |

## Disagreement summary

| Predicted | Human Label | Count |
| --- | --- | --- |
| Uncertain | Likely Closed | 8 |
| Active | Uncertain | 5 |
| No Web Presence | Likely Closed | 4 |
| Active | Likely Closed | 2 |
| Likely Closed | No Web Presence | 2 |
| Likely Closed | Uncertain | 2 |
| Uncertain | Active | 2 |
| No Web Presence | Uncertain | 1 |
