# Handoff — Business Checker iter 12 → next session (2026-05-12, evening)

> **Superseded 2026-05-12 by iter 13 stabilization.** The "iter 11 shippable
> command" in this doc is not reproducible as written — see
> [`RUNBOOK.md`](RUNBOOK.md) for the new canonical invocations using
> `--pipeline {v10,v11,v12_current_prod,v12_full}`. The body below is
> preserved as a historical record of the iter 12 diagnosis.

## TL;DR for the next session

We built 5 new signals on top of iter 11 (the FB-recency baseline) and **iter 12 regressed**. Iter 11 is still the best version we have. Code is shipped but defaults are OFF — re-enabling the new signals requires explicit kwargs.

The codex adversarial-review attempt failed (sandbox / arg-parser issues) and we ran out of session bandwidth. The next session should pick up by running the adversarial review through Julian's separate VS Code Codex panel — the prompt is already written, just needs to be pasted in.

**Do not start by re-reading the entire transcript.** Read this file, then jump to "What to do next."

---

## Current state of the pipeline

**Iter 11 is the shippable baseline:**
- `python run_checker.py --input ../data/BMOSG_All_Businesses.xlsx --workers 3 --verify-flagged --enable-facebook-recency`
- 72.0% decisive accuracy on the 60-row eval, 5 harmful flips, $0.81 per 60-row eval run
- Unreachable-social subset: 64.3% decisive (was 27.3% in iter 10)
- Reachable subset: 86.2% decisive, 0 harmful flips
- Projected 709-row production cost: ~$15-25 (Perplexity + Apify FB + Haiku)

**Iter 12 (DO NOT SHIP):**
- 5 new signals all defaulted to OFF. Re-enable individually via:
  - `--enable-instagram-fallback` on `run_checker.py` / `eval/rerun_sample.py`
  - `metadata=...` kwarg on `check_business`
  - The marketplace-residue rule fires automatically when AI returns Active+residue-only citations
- Net regression: 72.0% → 68.8% decisive, 0 → 1 reachable harmful flips, 5 → 7 total harmful flips.

---

## What got built this session

All under `business_checker/tools/` and `business_checker/tests/`:

### New tools (all defaults OFF, plumbed through `check_business`)
1. `tools/apify_client.py` — thin actor-runner shell, $0.10 hard cost cap per call, fail-open
2. `tools/check_facebook_recency.py` — FB page lookup with 4 candidate strategies:
   - Strategy 1: extract FB link from business's own website HTML
   - Strategy 2-4: synthesized slug variants (naive, &→and expanded, suffix-stripped)
   - **Plus** new SERP fallback via `scraperlink/google-search-results-serp-scraper`
3. `tools/check_instagram_recency.py` — same shape as FB, no SERP fallback yet
4. `tools/business_metadata.py` — `BusinessMetadata` dataclass + `metadata_from_row()` extractor
5. `tools/columns.py` — extended `HEADER_HINTS` to detect 10 columns (Date Added, Date Verified, First/Last Name, Category, Description)

### Modified
- `tools/check_business.py` — added `use_facebook_recency`, `use_instagram_fallback`, `metadata` kwargs; injected metadata block + FB section + IG section into prompt; added marketplace-residue override; FB no-found framing is now context-aware (neutral when site alive, corroborating closure when site dead)
- `tools/check_business.py` — added `THIRD_PARTY_MARKETPLACES` and `OWNED_STOREFRONT_PATTERNS` constants
- `eval/rerun_sample.py` — added `--enable-facebook-recency` and `--enable-instagram-fallback` CLI flags
- `run_checker.py` — extracts `BusinessMetadata` from spreadsheet rows
- `tests/conftest.py` — `isolate_env` autouse fixture now strips `APIFY_API_TOKEN` and `ANTHROPIC_API_KEY` too

### Tests
- 400+ unit tests pass (2 skipped — both live-API integration tests gated by env vars)
- Live integration tests: 1 in `test_apify_client.py` (skipped unless `APIFY_API_TOKEN_LIVE` set), 1 in `test_judge.py` (skipped unless `ANTHROPIC_API_KEY` set)
- New test files: `test_apify_client.py`, `test_check_facebook_recency.py`, `test_check_instagram_recency.py`, `test_business_metadata.py`, `test_marketplace_residue.py`, `test_check_business_fb_wired.py`, `test_tier1_tier2_wired.py`, `iter11_fb_standalone_validation.py` (one-off, not a test)

### Docs
- `docs/EVAL_BASELINES.md` — canonical baselines table, updated with iter 12 numbers + ship-decision
- `docs/2026-05-12-reachability-ceiling.md` — full reachability analysis (31 reachable, 16 unreachable-social, 8 judgment, 3 metadata, 2 other)
- `docs/2026-05-12-iter11-apify-facebook-spec.md` — iter 11 spec (mostly historical now)
- `docs/iter11-fb-validation-targets.csv` — 19 FB-cited eval rows with expected outcomes
- `business_checker/eval/datasets/bmosg_v1_reachability_tags.csv` — row-by-row reachability tags

---

## Eval results — full history

| Subset | Iter 9 dec | Iter 10 dec | Iter 11 dec | Iter 12 dec | I9 hf | I10 hf | I11 hf | I12 hf |
|---|---|---|---|---|---|---|---|---|
| Full eval (58 rows) | 67.4% | 59.1% | **72.0%** | 68.8% | 4 | 9 | **5** | 7 |
| Reachable only (31) | 85.2% | **95.8%** | 86.2% | 81.5% | 0 | 0 | **0** | 1 |
| Unreachable only (27) | 42.1% | 15.0% | **52.4%** | 52.4% | 4 | 9 | 5 | 6 |
| Unreachable-social (16) | 55.6% | 27.3% | **64.3%** | 61.5% | 2 | 6 | 3 | 4 |

---

## What went wrong in iter 12 — diagnosed

Four reachable rows regressed (Bundook, Travel Halo, GAP, 27 West, Back Office, One Fire Fight). Pattern: **adding more evidence sections gave Perplexity + Haiku more rope.**

- **Travel Halo** (correct in iter 11, wrong in iter 12): ZoomInfo "2009-present, as of 2026" trusted over FB-last-post-2020. Metadata block + marketplace-residue rule together confused the verdict.
- **Bundook**: IG tool extracted `bundookmilpackage` from website footer, found "recent" post — but that brand never operationalized. **IG handle from website HTML is not always the same brand as the queried business.**
- **27 West, Back Office, GAP**: Haiku judge over-applied skepticism on information-rich prompts, downgrading correct Actives to Uncertain.

The 5 changes individually unit-test cleanly. Stacked, they over-fire on edge cases.

---

## The codex adversarial-review situation (unresolved)

Julian wanted Codex (different model family) to challenge the architecture. We hit blockers:

1. macOS Gatekeeper flagged the codex binary as malware (notarization issue, GitHub issue #5787)
2. `/codex:adversarial-review` slash command requires the codex CLI; installing via `npm install -g @openai/codex` worked but the CLI's `--uncommitted` flag has an argument-parser bug — can't combine with a custom prompt or stdin
3. Plugin's companion wrapper returned `verdict: needs-attention, "blocked from repository reads"` even though `sandbox: "read-only"` was set in `executeReviewRun`

**Resolution Julian chose:** he has the VS Code Codex panel open in a separate window. The next session should paste the prepared prompt there (see "What to do next").

---

## What to do next

### Option A — Finish the adversarial review (recommended first)

1. Open Julian's VS Code Codex panel (separate window from this Claude Code session)
2. Paste the prompt below. It includes the adversarial-review skill framing prepended onto Julian's original four-dimension prompt:

```
You are running an adversarial code review on this working tree.

Position this as a challenge review that questions the chosen implementation, design choices, tradeoffs, and assumptions. It is NOT just a stricter pass over implementation defects. Keep the framing focused on whether the current approach is the right one, what assumptions it depends on, and where the design could fail under real-world conditions. Do not fix issues, apply patches, or suggest that you are about to make changes — review only.

The target is the entire uncommitted working tree (modified + untracked files). Read what you need, but ground every finding in exact file:line references where possible.

---

Read docs/EVAL_BASELINES.md and docs/2026-05-12-reachability-ceiling.md first — they contain the full iteration history (iter 1 through iter 12), the reachable/unreachable framing, and the iter 12 failure diagnosis. Your review should sit on top of those, not duplicate them.

Then challenge our approach across four dimensions:

(1) Architecture: Iter 12 regressed vs iter 11 despite adding 5 well-tested signals (metadata passthrough, marketplace-residue rule, FB no-found prompt fix, Google SERP FB fallback, IG fallback). We're seeing oscillation — each iteration fixes one failure mode and introduces a new one. Is the layered post-processing architecture (Perplexity verdict → aggregator override → marketplace-residue rule → rule scorer cap → Haiku judge → triage flag) fundamentally the wrong shape? Should we restructure entirely?

(2) Model choices: We're using Perplexity Sonar (cheapest tier, ~$0.005/call) + Haiku 4.5 as judge. Would upgrading to Sonar Pro or Sonar Reasoning materially improve accuracy on the failure modes we keep hitting? Should the judge be Sonnet 4.6 instead of Haiku? Or is the entire Perplexity-as-search-backbone choice wrong — would Claude Sonnet 4.6 with native web search, or GPT-5 with browsing, handle aggregator/marketplace residue better? Is multi-model voting (Perplexity + GPT + Claude majority) worth ~3x cost?

(3) Eval set: Is the 60-row hand-labeled eval (24 Likely Closed, 10 Uncertain — weighted toward hard cases) the right optimization target? Or are we overfitting to a stress test that doesn't represent the real 709-row distribution (~86% Active)? The reachable/unreachable tagging treats some rows as "unfixable without scrapers" — is that distinction real, or are we letting the eval shape what we build?

(4) Diminishing returns: We've gone from ~64% → 67% → 51% → 59% → 67% → 64% decisive across iterations. Are we at the noise floor of a 60-row eval (95% CI ±12 points)? Should we stop iterating against this eval entirely and instead invest in a 200-row labeled set, or production feedback loops on actual IVMF outcomes?

The strongest possible finding would be: "you're solving the wrong problem with the wrong tools — here's what to do instead." Don't just patch the current design. The goal is to maximize accuracy on the real 709-row production run and minimize the human-review queue — not to win the eval.

---

Output format:
- Verdict: one of [approve / approve-with-comments / needs-attention / blocked]
- Summary: 2-3 sentences
- Findings: each with severity [critical/high/medium/low], file:line reference, the issue, and a recommendation
- Strategic recommendation: if the right answer is "stop and restructure," say so explicitly
```

3. Once Codex returns the review, paste it back into the new Claude Code session
4. Weigh Codex's findings against shipping iter 11 vs. building further

### Option B — Skip Codex, ship iter 11 now

If Julian wants to move on, just run the 709:
```bash
cd ~/workspace/ivmf/code/ivmf-business-checker/business_checker
python run_checker.py \
  --input ../data/BMOSG_All_Businesses.xlsx \
  --workers 3 \
  --verify-flagged
```

To include FB recency (adds ~$5-10 in Apify cost on 709 rows), there's no production CLI flag yet — `run_checker.py` doesn't have `--enable-facebook-recency`. **This is a known gap.** You'd need to add it to `run_checker.py` before running production. The flag exists in `eval/rerun_sample.py` only.

Estimated production cost without FB: $10-15. With FB: $15-25.

### Option C — Investigate iter 12 failures before re-enabling any signals

The four reachable regressions in iter 12 are likely **fixable** with targeted patches:
- **Bundook fix:** require name-match between extracted IG handle and business name before trusting site-extracted IG (fuzzy threshold ≥ 75 like FB already does — IG just bypasses this check currently)
- **Travel Halo / GAP fix:** marketplace-residue rule should fire even when FB *was* found but is dormant (>18 months). Currently the rule only fires on dead-site condition, not on dead-site-AND-dormant-FB condition combined.
- **Judge over-correction:** the Haiku judge needs prompt tuning when many evidence sections are present. Possibly switch to Sonnet 4.6 for the judge (per the codex review dimension #2).

---

## Files to read first when picking this up

1. **This file.**
2. `docs/EVAL_BASELINES.md` — canonical table, gives you the iter 12 verdict in one glance
3. `docs/2026-05-12-reachability-ceiling.md` — the reachable/unreachable framing
4. `tools/check_business.py:298-880` — the full pipeline (single-pass + verify-flagged), all 5 new kwargs visible at function signatures

## Files to NOT read

- The conversation transcript itself — context was getting heavy near the end
- The earlier handoffs (`2026-05-12-iter9-handoff.md`, `2026-05-12-iter11-apify-facebook-spec.md`) — superseded by this one
- The full diff of all 25 modified/new files — too much. Stick to the function signatures in `check_business.py` and the `EVAL_BASELINES.md` table.

---

## Critical context that won't survive context compaction

- **Julian is on the Apify FREE plan** (~$5/month credit). The 709-row run with FB will exceed this. Recommend Starter ($49/mo) before production.
- **Apify token verified working**: authenticated as `coral_beaver` on FREE.
- **Anthropic key is set** in `business_checker/.env` (judge works).
- **Perplexity key is set** in `business_checker/.env`.
- **macOS Gatekeeper still has the codex binary flagged** if Julian tries `/codex:` slash commands again — VS Code panel codex is fine, but the npm-installed CLI used by the plugin may still hit it. Don't waste another hour debugging this; just paste into the VS Code panel.

---

## Things Julian was specifically asking about at end of session

1. **"How do we maximize accuracy and minimize human review?"** — The answer right now is "ship iter 11, accept the ~50-row human review queue on 709 rows, and invest in better labeling (200-row set) before iterating further." The 60-row eval has hit its noise floor.

2. **Stronger models / multi-model voting** — Worth Codex's opinion. My pre-Codex take: Sonnet 4.6 as judge instead of Haiku is the cheapest, highest-leverage change. Multi-model voting (Perplexity + GPT + Claude majority) is the most expensive and only worth it if a 200-row eval shows a >5pp ceiling lift.

3. **Did NOT settle:** whether to invest more time on iter 12 patches (Option C) or just ship iter 11 (Option B). Defer to Codex's read.

4. **Note from earlier**: Julian explicitly said "I really want to make this program as accurate as possible and minimize human review." That's the real success metric — not "win the eval." Codex's review is meant to challenge whether we're optimizing for the right thing.

---

## How to pick this up cleanly in a new session

Paste this as the first message:

> Continuing the IVMF business checker iter 12 work. Read `docs/2026-05-12-iter12-handoff.md` and `docs/EVAL_BASELINES.md`, then ask me whether I've gotten the Codex review back yet. If yes, I'll paste it and we weigh findings. If no, recommend Option A (paste prompt to VS Code Codex panel), Option B (ship iter 11 as-is), or Option C (patch iter 12 failures targeted at Bundook + Travel Halo + judge over-correction). Don't re-read the prior conversation.

That lands the new session in the right place without context drift.
