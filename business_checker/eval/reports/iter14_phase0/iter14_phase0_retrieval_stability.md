# Iter 14 — Phase 0: Perplexity retrieval-stability report

**Generated:** 2026-05-13 09:50:10
**Pipeline:** v11
**Pass 1 ran at:** 2026-05-13 09:30:51
**Pass 2 ran at:** 2026-05-13 09:41:26
**Rows compared:** 60
**Total cost:** $1.6625 (pass 1 $0.8204 + pass 2 $0.8421)

## Headline

- **Median citation-set Jaccard:** 0.304
- **Classification:** **retrieval-dominant**

## Drift buckets

| Bucket | Count | % | Meaning |
| --- | ---: | ---: | --- |
| `stable_stable` | 10 | 16.7% | citations same (Jaccard ≥ 0.80), verdict same — reproducible row |
| `stable_drift` | 2 | 3.3% | citations same, verdict CHANGED — **reasoning drift signal** |
| `drift_drift` | 9 | 15.0% | citations changed AND verdict changed — retrieval may have caused it |
| `drift_stable` | 39 | 65.0% | citations changed, verdict same — Perplexity robust to retrieval churn |

## Classification rule applied

Per the plan:
- `reasoning-dominant` if `stable_drift` ≥ 25% of rows AND median Jaccard ≥ 0.65 → Branch A1 priority.
- `retrieval-dominant` if (`drift_drift` + `drift_stable`) ≥ 50% AND median Jaccard < 0.50 → Branch B priority.
- `both` otherwise → full sequence.

## 10 most-divergent rows (lowest citation-set Jaccard)

| row_index | name | jaccard | status p1 → p2 | bucket |
| ---: | --- | ---: | --- | --- |
| 18 | Deep Sea Salt Company | 0.00 | Likely Closed → Likely Closed | drift_stable |
| 111 | CRSpices, ll | 0.00 | Active → Active | drift_stable |
| 163 | Dashfire Beards | 0.00 | Likely Closed → Likely Closed | drift_stable |
| 217 | ViTAC Solutions | 0.00 | Active → Active | drift_stable |
| 268 | One Fire Fight | 0.00 | Likely Closed → Likely Closed | drift_stable |
| 286 | Sword & Plough | 0.00 | Uncertain → Likely Closed | drift_drift |
| 375 | Chosun4u | 0.00 | Likely Closed → Likely Closed | drift_stable |
| 624 | Casa Los Juanes | 0.00 | Active → Active | drift_stable |
| 413 | Granted Advocacy Partners, Inc. (GAP, Inc.) | 0.08 | Likely Closed → Likely Closed | drift_stable |
| 424 | JMCO Consulting | 0.08 | Uncertain → Active | drift_drift |

## `stable_drift` rows (n=2)

These are the cleanest evidence of reasoning drift — Perplexity saw
the same URLs on both passes and emitted a different verdict.

| row_index | name | status p1 | status p2 | confidence p1 | confidence p2 |
| ---: | --- | --- | --- | ---: | ---: |
| 85 | Reflections of Service | Uncertain | Active | 60 | 75 |
| 258 | L'aube Boutique | Likely Closed | Uncertain | 70 | 50 |

## Checkpoint #1 — budget commitment

→ **B priority.** Branch A1 still runs as a control. A2 conditional
on checkpoint #2 variance.

Always proceed to Phase 1 — adjudicator + compare_configs N-input ext.
