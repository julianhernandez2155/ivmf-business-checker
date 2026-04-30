# Phase 1 — Clean Repo + GitHub Baseline

**Date:** 2026-04-30
**Outcome:** ✅ Complete
**Tag:** `v1.0-baseline`
**Recovery tag:** `pre-squash-archive` (preserves the original 3-commit history)
**Repo:** https://github.com/julianhernandez2155/ivmf-business-checker (private)

## What was done

1. **Pre-flight:** Rotated the Perplexity API key (Julian, manual). Verified `python3 -m tools.check_business` returns Active for Target with 100% confidence.
2. **Created scaffolding:**
   - `.gitignore` (root) — superset gitignore covering secrets, Python, run output, IDE, macOS, Streamlit, agentic tooling artifacts
   - `LICENSE` — MIT, attribution to Julian Hernandez and IVMF, Syracuse University
   - `README.md` — full rewrite (was a placeholder still mentioning Claude API). Sections: What It Does, Architecture (WAT diagram), Installation, Running, Folder Layout, Eval Methodology, Cost & Throughput, Documentation, License, Contact
   - `.github/workflows/ci.yml` — pytest matrix on push/PR for Python 3.11+3.12 × macOS+Ubuntu
3. **Cleaned working tree:** moved `docs/superpowers/specs/2026-03-31-job-search-automation-design.md` (unrelated to this project) to `~/personal/scratch/superpowers-misc/`. Removed `.DS_Store` files.
4. **Squashed history:** tagged old 3-commit history as `pre-squash-archive` for recovery, then created an orphan branch with no parent commit, staged 38 files, and committed as new `main` root.
5. **Tagged baseline:** `v1.0-baseline` annotated tag.
6. **Pushed:** created private GitHub repo via `gh repo create`, pushed main + both tags.
7. **CI green:** all 4 matrix jobs (ubuntu+macos × py3.11+py3.12) passed in 39 seconds.

## What was decided

- **Squash, don't preserve:** old commit messages referenced "Session 1/1.5/2" — internal session language. Clean baseline reads more professionally to outside reviewers.
- **MIT license:** standard permissive license. If IVMF requires proprietary terms later, can be replaced.
- **Private repo:** internal IVMF data + research methodology. Make public only with leadership sign-off.
- **No `.env`, no BMOSG xlsx in repo:** verified `git ls-files | grep -E "(\.env|BMOSG|Runs|DS_Store)"` returns empty.
- **CI uses unittest.mock:** existing test suite has zero live-API calls (verified at `Business Checker/tests/test_scrape_firecrawl.py`). CI passes without secrets.

## What was deferred

- **Folder rename `Business Checker/` → `business_checker/`:** scheduled for Phase 2.
- **`pyproject.toml`:** scheduled for Phase 2.
- **Pinning `requirements.txt`:** scheduled for Phase 2.
- **`docs/codex-review-1-architecture.md`:** scheduled for Phase 2 (post-rename Codex review).

## Verification

- `gh repo view --json visibility -q .visibility` → `PRIVATE` ✓
- `git log --oneline | wc -l` → 1 (single baseline commit) ✓
- `gh run list --limit 1` → status `completed`, conclusion `success`, 39s ✓
- `git ls-files | grep -E "(\.env$|BMOSG|Runs/|\.DS_Store)"` → empty ✓
- All 4 CI matrix jobs green ✓

## Files of note

- `.gitignore` — root level
- `LICENSE` — root level
- `README.md` — root level (full rewrite)
- `.github/workflows/ci.yml` — CI matrix

## Commit

`ca4552a v1.0 — IVMF Business Checker baseline`

38 files, 10,603 lines.
