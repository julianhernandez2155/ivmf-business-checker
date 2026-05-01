# PRD — Future Evaluation Features (v2+)

**Status:** Draft, parking lot for ideas surfaced during v1 eval design.
**Author:** Julian Hernandez
**Last updated:** 2026-05-01
**Audience:** Future-Julian, future-collaborators, leadership reviewing v2 proposals.

---

## Why this document exists

During v1 eval design (Phase 4), a Claude review surfaced ~10 rigor concerns about the labeling methodology — IRR, anchoring controls, calibration rounds, per-row metadata, etc. Most were valid points calibrated for academic-grade evaluation, but applying them in v1 would have:

- Doubled the eval timeline before any leadership demo
- Required a second labeler we don't have
- Introduced workflow complexity that the single-user pilot doesn't need

This PRD captures those ideas so they survive past v1 without polluting v1 scope. **Do not ship any of these in v1.** Revisit when (a) a second labeler is available, (b) the tool is being deployed cross-department, or (c) a leadership stakeholder asks specifically about methodology rigor.

---

## Feature 1 — In-app continuous spot-check (highest-value)

**Origin:** Julian's own idea during the Phase 4 review discussion.

**Description:** When an IVMF employee runs the Business Checker on a dataset, the program randomly selects X% of records (configurable, default 10%) and routes them through a manual review interface before the run completes. The employee labels each spot-check row, optionally adds a comment, and the system stores their label alongside the AI prediction in a long-running quality-tracking database.

**Why it's better than a separate eval ritual:**
- Eval happens continuously as a side-effect of normal usage, not as a one-time exercise
- Captures real-world drift over time (model accuracy may change as the web ages and the AI is updated)
- Builds a multi-rater dataset organically without recruiting a dedicated second labeler
- Departments that use the tool more get more eval signal — proportional to deployment risk
- Provides ongoing inter-rater data when multiple departments are running it

**v2 implementation sketch:**
- `--spotcheck-pct N` CLI flag (default 10)
- After the AI run completes, spawn the Streamlit review app pre-populated with N% of rows sampled at random
- Run is marked "complete" only after the user labels all spot-check rows (or explicitly skips them)
- Spot-check labels persisted to a SQLite quality-database (`business_checker/quality/quality.db`) shared across runs
- Periodic `report` command that summarizes accuracy across all spot-check labels collected to date

**Effort estimate:** M (~3 days of focused work). Reuses `eval/review_app.py` infrastructure.

---

## Feature 2 — Multi-labeler IRR (Cohen's kappa)

**Description:** When a second labeler is available, double-label a stratified subset of any eval dataset, compute Cohen's kappa, and use it as a ceiling on claimed AI accuracy.

**v1 limitation it addresses:** Single-labeler eval cannot distinguish AI errors from labeler errors. Reported "AI accuracy" is actually "AI agreement with the one labeler." If labeler is biased (and they are), the AI looks better/worse than reality.

**v2 implementation sketch:**
- `eval/sample.py --double-label-pct N` flag — duplicates N% of sampled rows under a different `row_index` so the labeler can't tell which are duplicates (or, better: a separate "labeler 2" workflow with the duplicates blinded)
- `eval/score.py` adds Cohen's kappa computation when `human_label_2` column is present
- Markdown report adds an "Inter-rater reliability" section with kappa + interpretation guide
- Per-status agreement matrix between labelers (helps identify which categories are systematically ambiguous)

**Honesty mechanism:** if AI/labeler agreement exceeds inter-rater agreement, the report flags it and refuses to call the higher number "accuracy" — the AI cannot be more accurate than the ceiling set by labeler agreement.

**Effort estimate:** S (~1 day) for the scoring side. Recruiting a second labeler is the actual bottleneck — that's a process problem, not a code problem.

---

## Feature 3 — Anchoring-controlled labeling mode

**Description:** Optional workflow where the labeler writes their label and justification *before* seeing the AI's prediction. Defends against confirmation bias.

**v1 limitation it addresses:** The current Streamlit UI shows the AI prediction up front. The labeling protocol warns against letting it bias the label, but warnings don't fix workflow-level bias.

**v2 implementation sketch:**
- `--blind-labeling` flag on `eval/review_app.py`
- In blind mode, the AI prediction panel is hidden behind a collapsible expander
- Labeler must enter their label + justification → submit a "draft" → only then is the AI prediction revealed
- After reveal, labeler can revise (revision is logged with timestamp so we can quantify how often the AI changed their mind)
- `eval/score.py` adds a "post-AI revision rate" metric

**Why deferred:** in a single-labeler v1 pilot, this doubles the per-row friction (write blind, then read AI, then optionally revise) for marginal bias reduction. Worth it when the eval becomes externally publishable or when leadership specifically asks about anchoring.

**Effort estimate:** S (~1 day). UI changes only.

---

## Feature 4 — Per-row session metadata

**Description:** Capture session number, position-within-session, and time-spent-per-row for each label. Enables post-hoc analysis of calibration drift.

**v1 limitation it addresses:** The labeling protocol's session-hygiene section warns that label quality degrades after row 30 of a session. There's no data to verify this is actually happening, or to detect it if it is.

**v2 implementation sketch:**
- `eval/review_app.py` adds 3 columns to the labeled CSV: `session_number`, `position_in_session`, `seconds_spent`
- Session boundary detected by ≥30-min gap between consecutive `reviewed_at` timestamps
- `eval/score.py` adds an optional drift-analysis chart: agreement rate vs position-in-session

**Why deferred:** at n=60 per dataset, session-drift signal is too weak to act on. The data becomes valuable when datasets are large (n=500+) or when multiple labelers are involved.

**Effort estimate:** XS (~2 hours). 3 column additions + simple plot.

---

## Feature 5 — Pre-eval calibration round

**Description:** Before the production labeling session, the labeler labels a 10-row "calibration set" against pre-known answers. Catches systematic biases (too generous on Uncertain, too strict on Active, etc.) before they contaminate the real dataset.

**v1 limitation it addresses:** A labeler's first 10–20 rows of any new task tend to be calibration noise — they're still figuring out where the lines are. Currently the protocol says "re-review the first 10 of each new session," which catches drift but not systematic bias.

**v2 implementation sketch:**
- A curated `eval/datasets/calibration_set.csv` file with 10 hand-vetted rows (5 from each of: clearly-Active, clearly-Closed, ambiguous-Uncertain, marketplace-only-Active, dead-domain-but-active-social — i.e., one row per common failure mode the AI is known to have)
- Each row has a "ground truth" label and a 1-paragraph rationale
- `eval/review_app.py --calibration` mode: labeler labels the 10 rows blind, then sees the ground truth + rationale per row, then proceeds to production labeling
- Results stored separately so they don't pollute the production eval

**Why deferred:** in v1, *Julian* would write the calibration set's ground truth, then label against his own answer key. That's not calibration, that's theater. This feature only becomes valuable when an external authority (a second senior labeler, or aggregated v1 results) defines the calibration set.

**Effort estimate:** S (~1 day for the workflow), but blocked on ground-truth source.

---

## Feature 6 — Tighter Unable-to-Determine vs Uncertain definitions

**Description:** Refine the protocol distinction between "I can't identify which business this is" and "I found the business, can't tell its status."

**v1 limitation it addresses:** The current protocol says "Unable to Determine" should be <10% of labels but the boundary with Uncertain is fuzzy.

**v2 implementation sketch:** purely documentation; no code change. Clearer boundary rules, with examples drawn from v1 labeling experience.

**Why deferred:** we don't yet know how often this confusion actually arises. Decide based on v1 labeling justifications.

**Effort estimate:** XS (~1 hour) post-v1.

---

## Decision rules — when to ship which feature

| Trigger | Ship |
|---|---|
| Tool deployed to a 2nd department | Feature 1 (in-app spot-check) — proportional eval signal |
| A senior reviewer is recruited | Feature 2 (IRR) + Feature 5 (calibration) |
| Leadership asks "how do you know this isn't confirmation bias?" | Feature 3 (anchoring control) |
| Eval datasets exceed n=500 | Feature 4 (per-row metadata) |
| v1 labeling reveals UTD/Uncertain confusion in justifications | Feature 6 |

None of these block v1. None of them ship in v1.

---

## Things we explicitly rejected (not deferred — rejected)

**MCC (Matthews Correlation Coefficient) as headline metric.** Statistically solid but too opaque for non-technical leadership. Stick with overall agreement + macro-F1.

**Confidence × status double stratification at n=60.** Cell counts collapse to ~5 per cell — too small for any inference. Revisit only if n increases significantly.

**Replacing the Streamlit UI with something more sophisticated.** It's good enough. The bottleneck is human time, not UI.

---

## How to update this PRD

When you encounter a new "we should add X" idea during eval work:
1. Decide if it's v1-blocking. If yes, ship it. If no, add to this document.
2. Each entry needs: description, what it solves, sketch, effort, deferral rationale, trigger that would un-defer it.
3. Don't write tickets here — write *informed proposals* that future-you can act on without rebuilding context.
