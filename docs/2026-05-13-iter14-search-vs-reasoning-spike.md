# Iter 14 — Search vs. Reasoning Drift Spike (plan)

**Author:** Claude (with Codex concurrence)
**Date:** 2026-05-13
**Status:** REVISION 2 — Codex revision-1 review (verdict: approve-with-comments) flagged 4 remaining issues. All accepted and applied; see "Revision 2 changelog" below. Execute in a fresh session, staged: Phase 0 → checkpoint → A1 → checkpoint → A2/B as needed.
**Predecessor:** `docs/2026-05-12-iter13-stabilization-plan.md` (executed
2026-05-12–13; Phase A2 documented real 13-day Perplexity drift).
**Successor target:** an iter-15 architecture decision (full Exa rebuild,
judge-only swap, or hybrid) backed by measurement, not vibes.

## Revision 1 changelog (2026-05-13)

Codex flagged six issues. All accepted and applied:

1. **Branch A bundled two changes (judge swap + citation scraping).** Split into `v14_branch_a1` (Perplexity-prose → Sonnet judge, nothing else) and `v14_branch_a2` (a1 + scrape top 3 Perplexity citations). Each variant changes exactly one variable from the prior step.
2. **Branch A "same as v11" contradiction.** Earlier draft said "rule scorer + marketplace-residue stay" while also claiming branch A = v11. v11 has `use_marketplace_residue=False`. Branch A1/A2 now explicitly inherit v11's toggle set verbatim: FB on, IG off, metadata off, marketplace-residue off, rule scorer on, verify_flagged on. The *only* change for A1 is "drop Perplexity's prose verdict; Sonnet adjudicates instead."
3. **Branch B FB/IG bundling.** Earlier draft said "FB and IG unchanged" — but v11 has IG off. Branch B now inherits v11 signal toggles exactly: FB on, IG off. An IG-on branch is a separate later experiment.
4. **Pre-adjudication domain filtering.** Earlier draft rejected aggregator/spam/marketplace domains before adjudication. Reframed: those domains are *classified* in the evidence dict (`citation_type: marketplace | aggregator | own_storefront | other`) and passed to the adjudicator with the classification. Filtering would hide stale-record evidence that matters for closure verdicts.
5. **Phase 0 Jaccard too thin.** Added row-level drift buckets — citation-stable + verdict-changed, citation-changed + verdict-changed, citation-changed + verdict-stable. That directly separates retrieval drift from reasoning drift at the row level, not just the median.
6. **Model name aliases.** Verified current model IDs via official Anthropic docs (`platform.claude.com/docs/.../all-models`). Pinned IDs throughout: `claude-sonnet-4-6` for the adjudicator default, `claude-opus-4-7` as the escalation option. `claude-haiku-4-5-20251001` is the current Haiku reference (we are NOT using Haiku as the adjudicator — that's what failed in iter 12). Older `-20250514` IDs are deprecated and not referenced. **(Revision 2 — Codex finding #1: docs sources disagree on which IDs are current. The plan no longer pins a specific ID — the executor verifies via `client.models.list()` at Phase 1 start and pins the latest non-deprecated Sonnet 4.x in the implementation, recording the exact ID in `Adjudicator.MODEL_ID` and in `RUNBOOK.md`.)**

## Revision 2 changelog (2026-05-13)

Codex revision-1 review flagged four issues. All accepted and applied:

1. **Model IDs still need hard verification at execution time.** Anthropic doc pages disagree by index recency; my fetch from `platform.claude.com` listed `claude-sonnet-4-6` / `claude-opus-4-7` as current, Codex's official-docs hit listed `claude-sonnet-4-20250514` / `claude-opus-4-1-20250805`. Plan no longer hard-codes a specific ID. Phase 1 step 1 is now: **call `anthropic.Anthropic().models.list()` and pin the latest non-deprecated Claude 4.x Sonnet (or 4.x Opus if Sonnet missing).** The pinned ID is recorded in `business_checker/tools/adjudicator.py` as `MODEL_ID` and printed in every run log so future drift is auditable.
2. **Build A1 before A2/B and checkpoint.** The strongest version of this plan is staged. After Phase 0 + Phase 1 + A1 the executor reviews variance — if A1 stabilizes (< ±2pp same-day variance), A2 becomes "confirmatory" rather than "required" and B becomes "optional, run only if A1 didn't reproduce variance fix." Saves $5–11 of API budget when A1 already answers the question. Plan now explicitly inserts checkpoint gates between phases.
3. **A1 framing.** Moving marketplace-residue logic into the adjudicator's prompt means A1 isn't purely "same reasoning rules, different model" — it's "same signals, new adjudication policy." Documented explicitly in Phase 2.a1 so the iter-15 decision memo doesn't overclaim what A1 isolates.
4. **`compare_configs.py` N-input extension.** Extended to accept N inputs before Phase 4, not pairwise. Moved into Phase 1 as a small prep task so the comparison tool is ready when Phase 4 lands.

---

## Goal

Determine **which layer** of the current pipeline produced the 21-of-60
verdict drift Phase A2 surfaced:

- **Retrieval drift** — Perplexity is finding different source URLs and
  snippets on repeat runs (search-index churn, ranking changes).
- **Reasoning drift** — Perplexity sees roughly the same evidence but
  emits a different verdict because its prose-layer behavior shifted.

These have different fixes. If retrieval dominates, the right iter-15
move is **Exa + Firecrawl** as the gather layer. If reasoning dominates,
the right iter-15 move is **swap Perplexity's prose verdict for an
external judge** (Sonnet/Opus) and keep Perplexity as a pure search
backend.

**The non-negotiable design rule going forward:** no search model emits
the final status. Search gathers evidence. A separate adjudicator
decides. That's the actual iter-14 restructure Codex flagged.

**Success definition (binary):** at end of spike we can answer "which
layer is the bigger drift contributor" with measured numbers across two
branches against a current Perplexity baseline.

---

## Non-goals (explicit)

- ❌ Full Exa rebuild of the pipeline. The spike runs Exa as one branch,
  not the production path.
- ❌ Re-labeling the eval. We're measuring drift against `v11 fresh
  2026-05-13`, not chasing accuracy improvements.
- ❌ New signals. The 5 signals from iter-12 are still parked. Iter 14
  doesn't unstick them.
- ❌ 709-row production run.
- ❌ Prompt tuning beyond what each branch's adjudicator inherently
  needs.
- ❌ Scope creep into "scrape every Perplexity citation by default" —
  that's an iter-15 decision once we know which branch wins.

---

## Baseline of record

**Comparison target for both branches: `v11 fresh 2026-05-13`** — not
the saved iter-11 CSV.

| Metric | Target value | Source |
|---|---|---|
| decisive_accuracy | 66.0% | `eval/reports/v11_fresh/report.md` |
| harmful_flips_total | 8 | same |
| harmful_flips_active_to_closed | 7 | same |
| reachable decisive | 81.5% | same |
| reachable harmful | 2 | same |

The saved iter-11 CSV (`bmosg_v1_iteration_11_fb.csv`) stays useful as
the **determinism gate** for the scoring code itself (72.0% / 5 harmful
must always reproduce on it via `score()`). It's no longer the
production baseline.

---

## The architectural rule (applies to both branches)

```
[Gather layer]            [Adjudication layer]
  finds evidence       →    decides the verdict
  emits structured        consumes the structured
  evidence dict            evidence and a prompt
                           → returns one of:
                             Active / Likely Closed /
                             Uncertain / No Web Presence
```

The **adjudication layer is shared between branches** — same Sonnet
prompt, same Pydantic output schema. Only the gather layer differs.
This is what makes the side-by-side honest: any decisive-accuracy
delta between branches is attributable to retrieval, not reasoning.

The shared evidence shape (drafted, will refine in implementation):

```python
class CitationType(str, Enum):
    OWN_STOREFRONT = "own_storefront"
    MARKETPLACE = "marketplace"
    AGGREGATOR = "aggregator"
    DIRECTORY = "directory"
    SOCIAL = "social"
    PRESS = "press"
    OTHER = "other"


@dataclass(frozen=True)
class CitationHit:
    url: str
    title: str | None
    snippet: str | None         # search-result snippet (Perplexity or Exa)
    scraped_text: str | None    # full text via Firecrawl (A2 + B only)
    citation_type: CitationType  # classified, NOT filtered — Codex finding #4
    relevance_score: float | None  # Exa returns this; Perplexity doesn't


@dataclass(frozen=True)
class BusinessEvidence:
    name: str
    website: str | None
    city: str
    state: str
    metadata: BusinessMetadata | None  # owner, dates, category
    own_website_scrape: ScrapeResult   # what scrape_website() returns today
    citation_hits: list[CitationHit]   # full list — adjudicator decides
    facebook_signal: FacebookSignal | None  # existing Apify output
    instagram_signal: InstagramSignal | None  # always None in iter-14 branches
    perplexity_prose: str | None       # A1/A2 only; B is None
```

Both branches populate this shape with the same field semantics — the
adjudicator cannot tell A1, A2, or B apart from the schema alone, which
is what makes the side-by-side honest. Branches differ only in *which
fields are populated* (e.g., `scraped_text` is None in A1, populated in
A2/B) and *which search backend produced the citations*.

---

## Sequencing — staged with checkpoints

**Codex revision-1 finding #2:** the strongest version of this plan is
staged. Don't burn the full A2 + B budget if A1 already answers the
question. The executor pauses at each checkpoint, looks at the
measured variance, and decides whether downstream phases are
"required," "confirmatory," or "skip."

Decision tree:

```
Phase 0 (retrieval stability, ~$2)
        │
        ├─ checkpoint #1 ── reasoning-dominant?  → A1 priority
        │                  retrieval-dominant?   → B priority (still run A1 as control)
        │                  both?                 → full sequence
        │
Phase 1 (adjudicator + model-ID resolution + compare_configs N-input ext)
        │
Phase 2.a1 (~$4)
        │
        ├─ checkpoint #2 ── A1 variance < ±2pp?  → A2 + B are confirmatory; run if budget permits
        │                  A1 variance ≥ ±2pp?   → A2 + B required
        │
Phase 2.a2 (~$5, optional/confirmatory after checkpoint #2)
Phase 3   (~$6, optional/confirmatory after checkpoint #2 unless B was promoted by Phase-0 result)
        │
Phase 4 (decision memo)
```

Minimum spike if every checkpoint signals "stop early": Phase 0 + Phase
1 + A1 + Phase 4 = ~$8, ~9 hours. Full spike if every checkpoint signals
"keep going": ~$22, ~17 hours.

### Phase 0 — Retrieval-stability ground truth (cheap, do first)

**Why first:** before either branch is built, we need to know whether
Perplexity's **gather** layer alone is stable. If we run `--pipeline v11`
twice in the same hour and get the same citation URLs both times,
retrieval is stable and the drift is downstream. If citations shift,
retrieval is unstable and that's the signal to take Exa seriously.

**Implementation:** a small script `eval/measure_retrieval_stability.py`
that runs the 60-row eval **twice** under `--pipeline v11`, captures for
each row both the citation set **and** the verdict (status +
confidence), and emits two analyses:

**Analysis 1 — Median Jaccard** (already in revision 0):
median citation-set Jaccard similarity across all 60 rows.

**Analysis 2 — Row-level drift buckets** (Codex finding #5):
classify each row into one of four buckets based on what changed between
pass 1 and pass 2:

| Bucket | Citation set | Verdict | What it implies |
|---|---|---|---|
| `stable_stable` | same (Jaccard ≥ 0.80) | same | row is reproducible end-to-end |
| `stable_drift` | same | changed | **reasoning drift dominates** for this row — Perplexity saw the same evidence and changed its mind |
| `drift_drift` | changed (Jaccard < 0.80) | changed | retrieval drift may have caused verdict drift; can't fully attribute |
| `drift_stable` | changed | same | Perplexity is robust to retrieval churn for this row — reasoning is stable |

Aggregate counts per bucket are the headline. If `stable_drift` dominates,
reasoning is the bigger problem; if `drift_drift` dominates, retrieval is
the bigger problem. The mixed buckets quantify how much each layer
contributes independently.

**Cost:** 2× a v11 60-row run ≈ $1.50–2.50 total Perplexity + Apify.

**Output:** `eval/reports/iter14_phase0_retrieval_stability.md` —
one-page report with:
- Median Jaccard + distribution histogram.
- Bucket counts (`stable_stable` / `stable_drift` / `drift_drift` / `drift_stable`).
- The 10 most-divergent rows (highest citation-set delta).
- All `stable_drift` rows enumerated (these are the cleanest evidence
  of reasoning drift — Perplexity saw the same URLs both times and
  changed its verdict).
- Classification:

  - **reasoning-dominant** (`stable_drift` ≥ 25% of rows AND median
    Jaccard ≥ 0.65): Branch A1 (judge swap) is the prime suspect for
    iter-15. Build it first; Branch B becomes a check.
  - **retrieval-dominant** (`drift_drift` + `drift_stable` ≥ 50% AND
    median Jaccard < 0.50): retrieval is the bigger driver. Branch B
    (Exa) is the prime suspect. Branch A still informative because the
    Sonnet judge may stabilize even noisy retrieval.
  - **both** (anything else): both branches needed; the spike's
    side-by-side will decide.

This narrows the iter-15 decision before we spend a day building either
branch.

**Gate:** report exists + classification recorded. **Checkpoint #1:**
the executor pauses here, reviews the classification, and records the
budget commitment for downstream phases:

- **reasoning-dominant** → A1 priority. Plan still calls for A2 + B
  as confirmatory; if they're skipped, document why.
- **retrieval-dominant** → B priority. A1 still runs as a control.
- **both** → full sequence.

Always proceed to Phase 1 regardless. Phase 1 is cheap and the
adjudicator + `compare_configs` extension are needed no matter which
branch wins.

---

### Phase 1 — Adjudicator + prep work

**Why:** both Branch A and Branch B need the same adjudicator. Build
once, share between branches. Locks the reasoning layer so any branch
delta is purely retrieval. This phase also resolves the model ID and
extends `compare_configs.py` to N inputs so Phase 4 isn't bottlenecked
on tooling.

#### Phase 1 step 1: resolve the adjudicator model ID

**Codex revision-1 finding #1:** Anthropic doc pages disagree on which
IDs are current (`claude-sonnet-4-20250514` per one index, `claude-sonnet-4-6`
per another). Do not hard-code. At Phase 1 start:

```python
import os
import anthropic
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
models = client.models.list()
# Pick the most recent non-deprecated Sonnet 4.x by created_at descending.
# Print full list to stdout so the choice is auditable.
for m in models.data:
    print(m.id, getattr(m, "created_at", None), getattr(m, "display_name", None))
```

Record the chosen ID in `business_checker/tools/adjudicator.py` as a
module-level constant `MODEL_ID = "<exact-id>"`. Log it in every
adjudicator call result so `run.log` proves which model produced each
verdict. Escalation: if Sonnet goldens fail, repeat the selection
process for Opus 4.x and re-pin.

**Haiku is explicitly out of scope as the adjudicator.** The current
Haiku reference (`claude-haiku-4-5-20251001` per `platform.claude.com`)
is fine for low-stakes utility calls, but the whole point of iter 14
is "stop trusting a small model as the final reasoner" — Haiku as
audit judge over-applied skepticism in iter 12.

#### Phase 1 step 2: extend `eval/compare_configs.py` to N inputs

**Codex revision-1 finding #4:** Phase 4 needs to compare 4 candidates
(baseline + A1 + A2 + B). Pairwise comparisons are messier and easier
to misread. Extend the existing tool:

- CLI: `--inputs label1=path1.csv label2=path2.csv ...` (N pairs).
  Backwards-compatible: `--baseline` + `--candidate` still work for
  the 2-input case.
- Markdown table: one row per metric, one column per input + a
  delta-vs-first column. Verdict (✅/⚠️/❌) is computed per input
  vs. the first input (the baseline).
- Exit code: 1 if any input crossed the red threshold vs. baseline.
- Existing tests stay green; add tests for N=3 and N=4 cases.

This is small (~1 hour) but doing it now in Phase 1 means Phase 4 is
a memo-write, not a tool-extend.

#### Phase 1 step 3: build the adjudicator

**Files touched (NEW):**

- `business_checker/tools/evidence_schema.py` — the `BusinessEvidence`
  dataclass + the `CitationHit` / `FacebookSignal` types (full schema
  in the "architectural rule" section above). Frozen dataclasses
  for inputs; Pydantic for LLM output.
- `business_checker/tools/adjudicator.py` — `adjudicate(evidence,
  api_key) -> AdjudicationResult` calling the pinned Sonnet ID with
  prompt caching on the system prompt + schema enforcement on the
  output. `MODEL_ID` is a module-level constant set from Phase 1
  step 1.
- `business_checker/prompts/adjudicator_v1.md` — the prompt text,
  versioned so we can diff it later.
- `business_checker/tests/test_adjudicator.py` — golden-evidence inputs
  → expected verdicts. ~10 fixtures across the four statuses + edge
  cases (residue-only, dead-site + active-FB, NWP).

**Implementation rules:**

- **No tools.** The adjudicator does not call search itself. Evidence
  in, verdict out. This is what makes "search emits no verdict" enforceable.
- **Pydantic output schema** identical to current `check_business`
  return: `status`, `confidence` (int 0–100), `evidence` (one-sentence
  explanation citing what tipped the decision), `requires_review`
  (bool), `review_reason` (str | None).
- **Prompt cache the system prompt** (~1500 tokens of decision rules)
  and reachability rubric. With ~58 eval rows × up to 4 branch variants
  × 2 runs, cache hits matter.
- **No retries on schema failure** — surface as Uncertain + flag for
  review. We want the noise visible.
- **Citation classification convention** (Codex revision-0 finding #4):
  the `CitationHit` type carries a `citation_type` enum:
  `own_storefront | marketplace | aggregator | directory | social | press | other`.
  Branch B's gather layer assigns this using the existing
  `tools.check_business._is_third_party_marketplace` and
  `_is_aggregator_url` helpers. Branch A inherits Perplexity's
  citations and classifies them after the fact. The adjudicator
  prompt treats `own_storefront` and `press` as high-trust,
  `marketplace` and `aggregator` as weak signal, and a citation set
  that's *all* marketplace/aggregator as a closure indicator (the
  iter-12 residue rule, but now stated in the prompt instead of
  overridden by deterministic code).

**Gate:** `pytest tests/test_adjudicator.py` passes on 10 golden
fixtures. `compare_configs.py` N-input test passes. Adjudicator call
cost on the goldens recorded. `MODEL_ID` constant pinned.

**Estimated effort:** 4 hours (1h model-ID resolution + N-input
`compare_configs` extension; 3h adjudicator + golden tests).

---

### Phase 2 — Branch A: Perplexity gather → Sonnet judge

**Hypothesis under test:** if we keep Perplexity's search but stop
trusting its prose verdict, decisive accuracy stabilizes.

Codex finding #1: branch A originally bundled "judge swap" with
"scrape Perplexity citations." Those are two distinct retrieval changes
and would have made the result un-attributable. Split into two
sub-branches, each changing exactly one variable:

#### Phase 2.a1 — Branch A1: same signals, new adjudication policy

**The minimal contrast.** v11's gather pipeline runs end-to-end exactly
as it does today, *except* the Haiku audit judge is removed and the
final verdict is decided by the Sonnet adjudicator instead of
Perplexity's prose layer.

**What A1 actually isolates** (Codex revision-1 finding #3): this is
not "same reasoning rules, different model." The adjudicator's prompt
encodes the marketplace-residue logic textually instead of relying on
the deterministic post-processor that v11 used. So A1 isolates **"same
signals, new adjudication policy."** The signals fed to the adjudicator
(Perplexity prose + scrape + FB recency + rule-scorer caps) are
identical to v11's, but the verdict policy is "prompt-encoded
guidance for a large reasoner" instead of "Perplexity prose + Haiku
override + deterministic residue rule." The iter-15 decision memo
must not overclaim A1's result as "Sonnet is more stable than
Perplexity at the same task" — the task changed shape slightly.

**Toggle parity with v11** (Codex finding #2 — no marketplace-residue
sneaking back in):

| Toggle | v11 | v14_branch_a1 |
|---|---|---|
| `use_facebook_recency` | True | True |
| `use_instagram_fallback` | False | False |
| `use_metadata` | False | False |
| `use_marketplace_residue` | False | **False** (do NOT re-enable) |
| `use_rule_scorer` | True | True |
| `verify_flagged` | True | True |
| Final-verdict source | Perplexity prose + Haiku judge | **Sonnet adjudicator** |

The marketplace-residue logic moves into the adjudicator's prompt as
a textual rule (Codex finding #4: classify, don't pre-filter), not as
a deterministic post-processing step. That keeps the toggle set
identical to v11 while still expressing the residue logic for the
adjudicator to apply or reject.

**Files touched (NEW):**

- `business_checker/tools/check_business_branch_a.py` — copies the
  current `check_business()` gather pipeline (website scrape, FB
  recency, Perplexity call, rule scorer), but does **not** invoke the
  Haiku judge and does **not** trust Perplexity's prose verdict. Returns
  a `BusinessEvidence` dict.
- `business_checker/tools/pipeline_configs.py` — add `v14_branch_a1`
  config. v11 retained unchanged.

**Gate (A1):**
- Run `--pipeline v14_branch_a1` on the 60-row eval twice.
- Score each run vs. original human labels.
- Compare against `v11 fresh 2026-05-13`.
- **Headline: decisive-accuracy variance across the two A1 runs.** If
  variance is < ±2pp, the new adjudication policy stabilizes verdicts
  even when Perplexity's search results drift. That's the iter-15
  evidence for "policy swap on top of Perplexity is enough."

**Checkpoint #2:** the executor pauses here and reviews A1 variance.

- **A1 variance < ±2pp AND A1 decisive ≥ 66.0% (matches v11 fresh):**
  the adjudicator stabilized verdicts on Perplexity's existing search.
  A2 and B become *confirmatory* — run them only if budget permits or
  if Phase 0 flagged retrieval-dominant. Iter 15 is likely the A1
  path.
- **A1 variance ≥ ±2pp:** the adjudicator alone is not enough; either
  retrieval drift dominates (proceed to B) or richer evidence per row
  is needed (proceed to A2). Both A2 and B are *required* in this
  case.
- **A1 decisive < 66.0% even with low variance:** the new adjudication
  policy regressed accuracy — investigate the prompt before any
  downstream phase. May be a Phase 1 issue (golden tests missed an
  edge case), not a retrieval issue.

**Estimated effort:** 3 hours.

**Estimated cost:** ~$2 × 2 runs = $4 (Perplexity + Apify FB + Sonnet
adjudication ~$0.005/row).

#### Phase 2.a2 — Branch A2: A1 + scrape Perplexity citations (conditional on checkpoint #2)

**Run when:** checkpoint #2 classified A1 as ≥ ±2pp variance, OR A1
stabilized but Phase 0 flagged retrieval-dominant (A2 then confirms
"richer evidence isn't what fixed it"), OR budget permits a
confirmatory run.

**Builds on A1 by adding exactly one retrieval change:** Firecrawl
scrapes the top 3 Perplexity citation URLs (max 600 chars each, same
convention as the existing `scrape_website` call) and includes that
page text in the evidence dict. The adjudicator is identical, the
Perplexity gather is identical, the toggle set is identical — the only
difference vs. A1 is "the citations have full text attached."

**Why split it out:** if A1 stabilizes and A2 also stabilizes,
citation-scraping was unnecessary work. If A1 doesn't stabilize but
A2 does, the wins are coming from richer evidence per row, not from the
judge swap — which is a much bigger architectural signal.

**Files touched:**

- `business_checker/tools/check_business_branch_a.py` — add an
  `enable_citation_scraping` flag; A1 leaves it False, A2 sets True.
- `business_checker/tools/pipeline_configs.py` — add `v14_branch_a2`
  config.

**Gate (A2):**
- Same protocol as A1: two same-day runs, variance is headline.
- **Comparison of interest:** A2 decisive vs. A1 decisive. Positive
  delta means the citation text added information the adjudicator
  used.

**Estimated effort:** 2 hours.

**Estimated cost:** ~$2.50 × 2 = $5 (adds Firecrawl ~$0.01/row on
top of A1).

---

### Phase 3 — Branch B: Exa search + Firecrawl scrape → Sonnet judge (conditional on checkpoint #2)

**Run when:** checkpoint #2 flagged A1 as unstable (≥ ±2pp variance), OR
Phase 0 classified retrieval-dominant (B is required regardless of A1),
OR budget permits a confirmatory run after A1+A2 stabilized (to prove
Exa wasn't needed).

**Hypothesis under test:** if we replace Perplexity entirely with a raw
search backend (Exa) plus citation scraping (Firecrawl), decisive
accuracy holds or improves vs. branch A2 (the closest gather-layer
analogue: Sonnet judge + scraped citations).

**Toggle parity with v11** (Codex finding #3 — no bundled IG-on
experiment):

| Toggle | v11 | v14_branch_b |
|---|---|---|
| `use_facebook_recency` | True (Apify) | True (Apify) |
| `use_instagram_fallback` | False | **False** (do NOT enable) |
| `use_metadata` | False | False |
| `use_marketplace_residue` | False | False (logic in adjudicator prompt) |
| `use_rule_scorer` | True | True |
| `verify_flagged` | True | N/A (no Perplexity to re-call; the Sonnet adjudicator either commits or returns Uncertain in one pass) |
| Search backend | Perplexity | **Exa + Firecrawl** |
| Final-verdict source | Perplexity prose + Haiku judge | Sonnet adjudicator |

An IG-on Exa branch is a *future* experiment. Bundling it here would
recreate the iter-12 mistake.

**Files touched (NEW):**

- `business_checker/tools/exa_client.py` — thin wrapper around the Exa
  HTTP API. Query construction: `"<business name> <city> <state>"`,
  num_results=10, autoprompt=true. **No include/exclude domain
  filtering at search time** (Codex finding #4 — classify, don't
  pre-filter). Returns a list of `(url, title, snippet, score)`
  tuples. Cost ~$0.005 per query.
- `business_checker/tools/check_business_branch_b.py` — orchestrates the
  branch:
    1. `scrape_website(listed_website)` — unchanged.
    2. `exa_search(name, city, state)` — top 10 hits with snippets.
    3. **Classify** each hit's domain using the existing
       `_is_third_party_marketplace` and `_is_aggregator_url` helpers;
       attach `citation_type` to each. Do **not** filter — every hit
       carries forward into the evidence dict. The adjudicator sees
       "all 10 citations were marketplace residue" as a closure signal,
       just like the residue rule in iter 12 did, but now expressed as
       evidence the adjudicator weighs.
    4. Pick the top 5 by Exa relevance score for **scraping**
       (Firecrawl, max 600 chars each, parallelized). Hits 6–10 still
       appear in the evidence dict as `(url, title, snippet,
       citation_type)` tuples without scraped text — the adjudicator
       can see they exist.
    5. FB recency via Apify — unchanged (v11 had this).
    6. **No IG fallback.**
    7. Package as `BusinessEvidence`.
    8. `adjudicate(evidence)` — same Sonnet adjudicator as branch A.
- `business_checker/tools/pipeline_configs.py` — `v14_branch_b` config.
- `business_checker/tests/test_exa_client.py` — unit tests with mocked
  HTTP responses (no live calls in CI).

**Implementation rules:**

- **No Perplexity in branch B.** That's the point — we're isolating
  retrieval from a different backend.
- **Scrape budget per row:** 1 (own site) + 5 (top citations) = 6
  Firecrawl calls max. At ~$0.003/scrape that's $0.018/row, plus
  Exa's $0.005/row, plus Apify FB ~$0.005–0.025, plus Sonnet
  ~$0.005. Per row cost ~$0.035–0.06, so 60 rows ≈ $2–3.50 per run.
- **Same adjudicator prompt as branch A.** Do not adapt the prompt for
  Exa-shaped evidence. The evidence dict shape is identical between
  branches by construction; if the prompt needs adapting, we've broken
  the branch-comparison rule.
- **Don't reject aggregator/marketplace hits** before adjudication
  (Codex finding #4). The adjudicator's prompt knows what to do with
  them. Pre-filtering would hide closure-evidence patterns like "every
  hit is a stale marketplace listing."

**Gate (branch B):**
- Run `--pipeline v14_branch_b` on the 60-row eval twice (same day).
- Score each run vs. original human labels.
- Compare side-by-side with `v11 fresh 2026-05-13`, `v14_branch_a1`,
  and `v14_branch_a2` using the existing `eval/compare_configs.py`
  (extend it to accept 4 inputs, or run three pairwise comparisons).
- **Headline: decisive-accuracy variance across the two B runs.**
  Plus a secondary headline: B-vs-A2 delta, which isolates "different
  search backend, same adjudicator + same scraping convention."

**Estimated effort:** 6 hours (Exa client is the biggest unknown).

**Estimated cost:** ~$3 × 2 runs = $6.

---

### Phase 4 — Decision document

**Why:** the whole spike exists to produce one decision: which
direction does iter-15 go.

**File touched (NEW):**

- `docs/2026-05-13-iter14-decision.md` — one-page memo. Format:

```markdown
# Iter 14 spike — decision

## Measured

### Phase 0 — Perplexity retrieval stability

| Metric | Value |
|---|---|
| Median citation-set Jaccard (same-day, n=60) | X.XX |
| `stable_stable` rows (citations same, verdict same) | N |
| `stable_drift` rows (citations same, verdict changed → reasoning drift) | N |
| `drift_drift` rows (citations changed, verdict changed) | N |
| `drift_stable` rows (citations changed, verdict same → reasoning robust) | N |
| Phase-0 classification | reasoning-dominant / retrieval-dominant / both |

### Branch decisive-accuracy across same-day re-runs

| Branch | Run 1 | Run 2 | Variance (pp) | Harmful run 1 | Harmful run 2 | Reachable run 1 | Reachable run 2 |
|---|---|---|---|---|---|---|---|
| `v11 fresh 2026-05-13` (baseline) | 66.0% | — | — | 8 | — | 81.5% | — |
| `v14_branch_a1` (Perplexity + Sonnet judge) | _ | _ | _ | _ | _ | _ | _ |
| `v14_branch_a2` (a1 + scrape Perplexity citations) | _ | _ | _ | _ | _ | _ | _ |
| `v14_branch_b` (Exa + Firecrawl + Sonnet judge) | _ | _ | _ | _ | _ | _ | _ |

## Decision

[ ] Iter 15 = A1 path (judge-only swap; Perplexity stays as search backend)
[ ] Iter 15 = A2 path (judge swap + scrape Perplexity citations; still on Perplexity)
[ ] Iter 15 = B path (Exa replaces Perplexity entirely; Sonnet judge)
[ ] Iter 15 = Hybrid (e.g., Exa primary + Perplexity supplement, or branch-aware routing)
[ ] Inconclusive — extend spike with [specific next step]

## Reasoning

(Short. The headline number is **variance across same-day re-runs**,
not raw accuracy. Goal of iter 14 was to isolate retrieval drift vs.
reasoning drift, then pick the architecture that survives both.
Reference Phase 0's bucket counts to argue which layer dominated.
Reference the branch variances to argue which architecture stabilizes
the worst-affected layer.)

## Cost projection for 709-row production run

- A1: $X per 709 rows.
- A2: $Y per 709 rows.
- B: $Z per 709 rows.
- Quality-vs-cost frontier note.

## Model IDs of record (filled in at execution time)

- Adjudicator: `<exact ID from Phase 1 step 1, e.g. claude-sonnet-4-6 or claude-sonnet-4-20250514 — verify via client.models.list() before pinning>` (escalation: latest Opus 4.x non-deprecated).
- Branch A still uses Perplexity sonar.
- Branch B uses Exa (no model ID — HTTP API).
```

**Gate:** decision recorded, signed off, commit lands.

---

## Total estimated effort: 8–18 hours over 2–3 sessions (depends on checkpoints)

The plan is staged. Two checkpoints decide whether downstream phases
run. Both numbers below are upper bounds — early termination at either
checkpoint saves the rest.

- Phase 0: 2 hours, ~$2 (script + 2 paid runs). **Always runs.**
- Phase 1: 4 hours, ~$0.50 (model-ID resolution + N-input
  `compare_configs` extension + adjudicator + golden tests). **Always
  runs.**
- Phase 2.a1: 3 hours, ~$4 (Branch A1 + 2 paid runs). **Always runs
  unless Phase 0 classified retrieval-dominant AND budget is tight.**
- Phase 2.a2: 2 hours, ~$5 (Branch A2 + 2 paid runs). **Conditional
  on checkpoint #2.**
- Phase 3: 6 hours, ~$6 (Branch B + Exa client + 2 paid runs).
  **Conditional on checkpoint #2.**
- Phase 4: 1 hour, $0 (decision memo). **Always runs.**

**Minimum spike** (Phase 0 + 1 + A1 + 4): ~9 hours, ~$8.
**Full spike** (every phase runs): ~18 hours, ~$22.

Worth it either way to make the iter-15 architecture call with
measurement, not vibes.

---

## What this plan does NOT decide

- The exact production architecture for iter 15. Phase 4 picks the
  direction; iter 15 is the rebuild.
- Whether to re-label the eval. If the spike reveals the 60-row eval
  is too small to discriminate between branches, that's an iter-15
  pre-req — not iter-14 work.
- Sonnet vs. Opus for the judge. Default Sonnet 4.6 for cost; if
  Phase 1 golden tests fail too often, escalate to Opus.

---

## Risks

1. **Branch A and Branch B both regress vs. baseline.** Possible if the
   Sonnet adjudicator is the actual problem (e.g., over-skeptical like
   Haiku was in iter 12). Mitigation: Phase 1 golden tests catch this
   before we burn the paid run budget.
2. **Same-day Perplexity is stable, week-over-week isn't.** The 21-of-60
   drift we measured was over 13 days. Phase 0 might show low variance
   over 1 hour but mask the underlying problem. Acceptable risk —
   if same-day is stable but week-over-week isn't, that's still
   actionable (cache aggressively, re-run weekly).
3. **Exa coverage gaps.** Exa may simply not index some of the obscure
   veteran-owned business sites Perplexity finds. Branch B may legitimately
   produce fewer citations on some rows. The adjudicator must handle
   "thin evidence" gracefully — its prompt should treat low-citation
   rows as Uncertain by default.
4. **Adjudicator prompt drift.** If we tune the Sonnet prompt between
   branches, the comparison is invalid. Strict rule: prompt frozen
   after Phase 1, no edits until Phase 4 decision.

---

## Open questions for the executing session

1. **Adjudicator model ID:** ✅ resolved by revision 2 — no hard-code.
   Phase 1 step 1 runs `client.models.list()` and pins the latest
   non-deprecated Sonnet 4.x; result recorded in
   `adjudicator.py:MODEL_ID`.
2. **Citation-scrape isolation:** ✅ resolved by revision 1 — A1
   (judge swap only) vs. A2 (judge + scrape) split.
3. **`compare_configs.py` N-input extension:** ✅ resolved by revision
   2 — moved into Phase 1 step 2.
4. **Exa API key:** Julian to provision before Phase 3 *if* Phase 3
   runs (now conditional on checkpoint #2). No quota concern at
   ~$0.30 per 60-row spike run.
5. **Branch C (pure-Exa snippets, no scraping):** still parked. If
   A1/A2/B converge on similar variance, revisit C as a cost-cut
   experiment. Otherwise skip.
