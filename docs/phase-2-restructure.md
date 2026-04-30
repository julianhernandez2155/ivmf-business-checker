# Phase 2 — Restructure + Codex Review #1

**Date:** 2026-04-30
**Outcome:** ✅ Complete
**Tag:** `phase-2-restructure`

## What was done

### Folder rename
- `git mv "Business Checker" business_checker` — root rename via git, history preserved on every renamed file (32 file moves, 100% rename detection).
- No Python imports broken: all imports are `from tools.X` (relative inside `business_checker/`), so the rename was path-only.

### Path-reference updates
Updated 5 files via subagent (Sonnet) — only changed path-like usages, preserved product-name prose:
- `business_checker/CLAUDE.md` (project layout diagram)
- `DEPLOYMENT.md` (Railway commands)
- `docs/PROGRAM_OVERVIEW.md` (run-folder reference)
- `UPGRADE_PLAN.md` (cache file path)
- `docs/superpowers/specs/2026-03-31-ivmf-checker-exe-and-email-workflow.md`
- `.github/workflows/ci.yml` (working-directory)

`BusinessChecker.spec` and `SETUP.md` had no path references to update.

### Packaging additions
- **`business_checker/pyproject.toml`** — project metadata, pytest config (with `pythonpath`, `norecursedirs`, `xfail_strict`), ruff lint config.
- **`business_checker/requirements-dev.txt`** — split dev deps (`pytest`, `ruff`) from runtime `requirements.txt`.
- **`business_checker/requirements.txt`** — pinned to exact versions (`requests==2.33.0`, `pydantic==2.12.5`, etc.). Was unpinned (`>=`) before.
- **`business_checker/.gitignore`** — added `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `cache/`, `*.db`, `*.db-journal`.
- **CI workflow** — installs both `requirements.txt` and `requirements-dev.txt`.

### Test infrastructure
- **`business_checker/tests/conftest.py`** — shared fixtures:
  - `fake_perplexity_key`, `fake_firecrawl_key`, `no_firecrawl_key`
  - `project_root`, `sample_business`
  - **autouse `isolate_env`** — strips real API keys from env for every test, preventing accidental live API calls.

### Cleanup
- Removed `business_checker/archive/business_checker_gui (3).py` (978-line duplicate).
- Moved `Business_Checker_Executive_Summary.{docx,rtf}` → `docs/archive/`.
- Moved `BMOSG_All_Businesses.xlsx` → sibling `data/` folder (gitignored). Application directory is now clean of real workbooks.
- Added `data/README.md` documenting the new location.
- Removed `docs/superpowers/specs/2026-03-31-job-search-automation-design.md` (unrelated to this project; moved to `~/personal/scratch/`).

### Codex Architecture Review #1
- Ran `codex exec` against the full structure. Output saved to `docs/codex-review-1-architecture.md`.
- 12 ranked items returned. Triaged 5 to apply now, 7 deferred.
- **Deferred to post-demo (justification in `codex-review-1-architecture.md`):**
  - Repo-root packaging (#2 — M effort, touches every import + test path)
  - Build-system + console_scripts in pyproject (#3)
  - `workflows/` → `docs/workflows/` move (#4)
  - `BusinessChecker.spec` → `packaging/pyinstaller/` (#5)
  - mypy/pyright + pre-commit (#9)
  - Shared orchestration layer extraction (#11 — M effort)
  - Tkinter vs Flask demotion (#1 — leadership decision, not architecture)

## Bug caught and fixed mid-phase

Adding `business_checker/__init__.py` (Codex item #12) made `business_checker` a package, which broke pytest's import resolution for tests using `from tools.X`. Reverted the `__init__.py` and added `pythonpath = ["."]` to `[tool.pytest.ini_options]` instead. This locks down test-import behavior regardless of pytest's rootdir-finder.

## What was decided

- **Squash, don't reorganize:** kept the existing layout. Repo-root packaging, `src/` layout, type-checker config — all P1 polish, but post-demo. Risk to schedule outweighs benefit.
- **Codex feedback is filed**, not blindly applied. Triage table in `codex-review-1-architecture.md`.
- **Pin requirements:** non-negotiable. Was the biggest reproducibility gap.

## Verification

- `cd business_checker && python3 -m pytest -q` → 90 passed in 0.43s ✓
- `python3 -m tools.check_business` → Active 100% on Target ✓
- CI green on all 4 matrix combinations (Ubuntu/macOS × py3.11/3.12) ✓
- `git ls-files | grep -E "(\.env|BMOSG|Runs/)"` → empty ✓

## Files of note

- `docs/codex-review-1-architecture.md` — review output + Julian's triage decisions
- `business_checker/pyproject.toml` — new packaging metadata + pytest + ruff
- `business_checker/tests/conftest.py` — shared fixtures + autouse env isolation
- `data/` — new sibling folder for input data, gitignored

## Commits

```
3a228ed chore: apply codex architecture review #1 (P0 + selected P1 items)
68e75e2 fix(ci): drop business_checker/__init__.py and add pytest pythonpath
bf8bb43 chore: restructure for production readiness
```

`phase-2-restructure` tag points at the polish commit (3a228ed) — fix commit (68e75e2) follows on main.
