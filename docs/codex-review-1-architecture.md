# Codex Architecture Review #1

**Date:** 2026-04-30
**Reviewer:** Codex CLI 0.117.0 (gpt-5)
**Scope:** Phase 2 architecture review — folder structure, packaging, entry-point duplication, leadership-demo readiness.
**Tokens used:** 67,989

## Codex's findings (verbatim ranking)

| # | Priority | Effort | Item |
|---|---|---|---|
| 1 | P0 | S | Choose one demo surface and demote the other (Tkinter vs Flask vs CLI) |
| 2 | P1 | M | Make repo root the real project root (move pyproject up, install/test from root, package as `business_checker.tools...`) |
| 3 | P1 | S | Add `[build-system]`, dependency declaration, `console_scripts` to pyproject |
| 4 | P1 | S | Move `workflows/` out of the application tree to `docs/workflows/` |
| 5 | P1 | S | Move `BusinessChecker.spec` to `packaging/pyinstaller/`; keep `main.py` with entry points |
| 6 | P1 | S | Tighten pytest config: add `norecursedirs`, `xfail_strict = true`, `pythonpath` |
| 7 | P1 | S | Add `conftest.py` for shared test setup |
| 8 | P1 | S | Split runtime and dev dependencies (`requirements-dev.txt`) |
| 9 | P1 | S | Add type-checker config (mypy or pyright) + pre-commit hooks |
| 10 | P1 | S | Clean non-source artifacts (`.pytest_cache`, `.tmp_uploads`, `Runs/`, real workbook) out of `business_checker/` |
| 11 | P2 | M | Extract shared orchestration/service layer between the 3 entry points |
| 12 | P2 | XS | Add package-root `__init__.py` for `business_checker/` |

## Julian's triage decisions

**Apply now (Phase 2):**
- **#7** — Add `conftest.py` (XS effort, professionalism signal).
- **#6** — Tighten pytest config (`norecursedirs`, `xfail_strict`).
- **#8** — Split `requirements-dev.txt` (clean signal, 5-min change).
- **#10** — Move `BMOSG_All_Businesses.xlsx` out of `business_checker/` to a sibling `data/` folder (gitignored). Cleans the source tree without affecting code.
- **#12** — Add empty `business_checker/__init__.py` (XS).

**Defer to Phase 3 or later:**
- **#1** — Demoting Tkinter vs Flask is a leadership decision, not an architecture one. README already lists CLI as primary ("recommended for batches"). For the demo Julian will choose. Do NOT delete either UI before the eval result is in.
- **#2** — Repo-root packaging (M effort). Touches imports, tests, CI all at once. Defer until after the eval phase. Risk to schedule outweighs benefit pre-demo.
- **#3** — Build-system + console_scripts. Useful but not blocking. Add when promoting repo root.
- **#4** — Move `workflows/` to `docs/workflows/`. Defer — `workflows/` is referenced by the WAT pattern documentation. Moving requires coordinated doc updates. Worth doing post-demo.
- **#5** — Move `.spec` to `packaging/`. Cosmetic; defer.
- **#9** — Type checker + pre-commit. Adds CI complexity; defer to post-demo polish.
- **#11** — Extract shared orchestration. M effort, real value, but post-demo.

**Reject:**
- None outright. All Codex suggestions are valid; just timed wrong.

## Apply order this session

1. Add `business_checker/__init__.py` (empty).
2. Add `business_checker/tests/conftest.py` with shared fixtures.
3. Tighten `pyproject.toml` pytest section.
4. Split `requirements-dev.txt` from `requirements.txt`; update CI.
5. Move `BMOSG_All_Businesses.xlsx` to sibling `data/` (gitignored).

After these: 90 tests still pass, structure is cleaner, but no breaking changes to imports or run commands. Phase 3 starts next.
