# Eval Report — predictions

**Generated:** 2026-05-13 19:17 UTC
**Source:** eval/reports/iter14_a1_run1/predictions.csv
**Total labeled rows:** 60
**Excluded (Unable to Determine or empty):** 2

## Headline

**Overall agreement: 56.9% (95% Wilson CI: 44.1%–68.8%, n=58)**

## Canonical metrics (iter 13)

| Metric | Value |
| --- | --- |
| decisive_accuracy | 65.9% (n=44) |
| harmful_flips_total | 2 |
| harmful_flips_active_to_closed | 2 |
| harmful_flips_closed_to_active | 0 |
| review_queue_size | 0 |

## Slices (by reachability)

| Slice | n | Decisive acc. | Harmful (total) | A→C | C→A |
| --- | --- | --- | --- | --- | --- |
| all | 58 | 65.9% | 2 | 2 | 0 |
| reachable | 31 | 70.4% | 0 | 0 | 0 |
| unreachable-judgment | 6 | 0.0% | 0 | 0 | 0 |
| unreachable-metadata | 3 | 100.0% | 0 | 0 | 0 |
| unreachable-other | 2 | 100.0% | 0 | 0 | 0 |
| unreachable-social | 16 | 58.3% | 2 | 2 | 0 |

## Per-status metrics

| Status | n | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| Active | 22 | 74.1% | 90.9% | 0.816 |
| Likely Closed | 24 | 75.0% | 37.5% | 0.500 |
| Uncertain | 10 | 28.6% | 40.0% | 0.333 |
| No Web Presence | 2 | 0.0% | 0.0% | 0.000 |

## Confusion matrix

Rows = human label (true), columns = predicted label (AI).

| Predicted \ Human | Active | Likely Closed | Uncertain | No Web Presence |
| --- | --- | --- | --- | --- |
| Active | 20 | 0 | 2 | 0 |
| Likely Closed | 2 | 9 | 8 | 5 |
| Uncertain | 4 | 2 | 4 | 0 |
| No Web Presence | 1 | 1 | 0 | 0 |

## Calibration

| Confidence bucket | n | Agreement rate |
| --- | --- | --- |
| 0–49 | 14 | 28.6% |
| 50–59 | 0 | — |
| 60–69 | 5 | 0.0% |
| 70–79 | 11 | 72.7% |
| 80–89 | 15 | 66.7% |
| 90–100 | 13 | 84.6% |

## Disagreement summary

| Predicted | Human Label | Count |
| --- | --- | --- |
| Uncertain | Likely Closed | 8 |
| No Web Presence | Likely Closed | 5 |
| Active | Uncertain | 4 |
| Active | Likely Closed | 2 |
| Likely Closed | Uncertain | 2 |
| Uncertain | Active | 2 |
| Active | No Web Presence | 1 |
| Likely Closed | No Web Presence | 1 |
