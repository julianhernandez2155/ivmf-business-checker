# IVMF Business Checker

> Automated operational status verification for veteran-owned businesses, built at the Institute for Veterans and Military Families (IVMF), Syracuse University.

[![CI](https://github.com/JulianHernandez2155/ivmf-business-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/JulianHernandez2155/ivmf-business-checker/actions/workflows/ci.yml)

## Project Status (as of 2026-05-14)

This repo is mid-rebuild. **v1.0** is a working Python desktop tool that's processed ~20,000 records in production at IVMF. **v1.1** is an in-progress web platform pivot — Supabase + Next.js + a Railway worker that imports the v1.0 verification engine unchanged.

### Milestone v1.1 — Web Platform Pivot

| Phase | Scope | Status |
|------:|:------|:-------|
| 0 | Foundation: Supabase schema + RLS + magic-link auth + codegen drift CI + Railway worker scaffold + eval-CI gate | **In progress** — 5/6 plans complete; final plan paused at Resend ticket (human action) |
| 1 | Cache-only verification (upload → canonical match → XLSX export, zero API calls) | Planned |
| 2 | Live verification (real Perplexity + FireCrawl, multi-pass aggregator, pause/resume) | Planned |
| 3 | Manual workflows (review queue, random-sample labeling) | Planned |
| 4 | Email outreach (admin-approved, HMAC-tokenized form responses) — blocked on IVMF IT DNS | Planned |
| 5 | Analytics & receipts (cache hit rate, spend, status distribution) | Planned |
| 6 | Decommission desktop (regression vs BMSG + Alabama VOB baselines) | Planned |

Full roadmap: [`.planning/ROADMAP.md`](.planning/ROADMAP.md). Phase-by-phase context, research, plans, and execution evidence live under [`.planning/phases/`](.planning/phases/).

### Triage, not oracle

A 2026-05-13 framing decision ([`.planning/2026-05-13-decision-triage-not-oracle.md`](.planning/2026-05-13-decision-triage-not-oracle.md)) reframed the system: the AI is a **triage engine** that routes verification work into one of 6 labels (auto-accepted / manual review / outreach recommended / etc.). Final status changes always come from a human or a business owner's response — never the AI alone.

### What's in this repo right now

- **`business_checker/`** — the v1.0 Python application (verification engine, Tkinter GUI, eval harness, gold dataset). This code is frozen and reused, not maintained, going forward.
- **`web/`** — Next.js 16 app shell (sign-in, `/me`, middleware allowlist) — Phase 0 deliverable.
- **`worker/`** — Railway-bound FastAPI worker (pgmq long-poll, heartbeat, db pool) — Phase 0 deliverable.
- **`supabase/migrations/`** — Postgres schema + RLS + append-only triggers + pgmq queues — Phase 0 deliverable.
- **`.github/workflows/`** — CI (eval regression gate, codegen drift gate).
- **`.planning/`** — Get-Shit-Done methodology artifacts: roadmap, requirements, per-phase context/research/plans/evidence. Read these to see the decision trail.

The v1.0 application (everything below) still runs as documented. v1.1 builds on top; it does not replace v1.0 in this repo until Phase 6.

---

## What It Does

Given a spreadsheet of businesses (name, city, state, optional website), the tool determines whether each business is still actively operating. For every record it produces a four-part verdict — **status** (Active / Likely Closed / Uncertain / No Web Presence), **confidence** (0–100), **one-sentence evidence**, and **source URLs** — written into a color-coded Excel report alongside the original data.

The tool replaces a manual review process where two staff members Googling the same business often produced two different answers with no audit trail. It standardizes that decision and produces written evidence for every verdict.

## Architecture

The project follows the **WAT pattern**:

```
Workflows (markdown SOPs)
    ↓
   Agent (Perplexity Sonar + structured prompt)
    ↓
   Tools (deterministic Python: scrape, cache, checkpoint, build output)
```

Per-row pipeline:

```
Row → Cache lookup → Website scrape (Firecrawl or direct HTTP) →
Perplexity Sonar w/ structured JSON output → Post-process →
Checkpoint → (repeat in parallel) → Final Excel build
```

## Installation

Requirements: Python 3.11+, a Perplexity API key. See [`business_checker/SETUP.md`](business_checker/SETUP.md) for a non-technical walk-through.

```bash
git clone https://github.com/JulianHernandez2155/ivmf-business-checker.git
cd ivmf-business-checker/business_checker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in PERPLEXITY_API_KEY
```

## Running

**Headless (recommended for batches):**
```bash
cd business_checker
python run_checker.py --input businesses.xlsx --workers 3
```

**GUI (Tkinter):**
```bash
cd business_checker
python business_checker_gui.py
```

**Web dashboard (Flask):**
```bash
cd business_checker
python business_checker_app.py
```

Stop with Ctrl+C; re-run the same command to resume from the checkpoint.

## Folder Layout

```
ivmf-business-checker/
├── business_checker/         # Application
│   ├── tools/                # Deterministic Python (API, scrape, cache, checkpoint, output)
│   ├── tests/                # Pytest suite (90+ tests, all mocked)
│   ├── workflows/            # Markdown SOPs (the W in WAT)
│   ├── eval/                 # Evaluation harness (Phase 4 onward)
│   ├── templates/            # Flask HTML
│   ├── run_checker.py        # Headless CLI batch runner
│   ├── business_checker_gui.py    # Tkinter desktop GUI
│   ├── business_checker_app.py    # Flask web dashboard
│   ├── main.py               # PyInstaller entry
│   └── BusinessChecker.spec  # PyInstaller build spec
├── docs/                     # Architecture + leadership documents
└── .github/workflows/        # CI
```

## Evaluation Methodology

This tool is evaluated against a human-labeled ground-truth dataset. Methodology, agreement rates, calibration analysis, and known limitations are documented in [`docs/IVMF_BUSINESS_CHECKER_LEADERSHIP_REPORT.md`](docs/IVMF_BUSINESS_CHECKER_LEADERSHIP_REPORT.md) (added in Phase 8) and the eval folder ([`business_checker/eval/`](business_checker/eval/)).

## Cost & Throughput

- **Per-record cost:** ~$0.005–$0.008 (Perplexity Sonar + optional Firecrawl scrape).
- **Throughput:** ~1 record/sec/worker. Worker count is gated by Perplexity tier (1/3/8 QPS).
- **Sample budgets:** 709 records ≈ $5–$10. 20,000 records ≈ $100–$160.
- **Cache:** 30-day TTL. Re-runs against overlapping datasets are essentially free.

## Documentation

- [`business_checker/SETUP.md`](business_checker/SETUP.md) — non-technical setup guide
- [`business_checker/CLAUDE.md`](business_checker/CLAUDE.md) — agent operating instructions
- [`business_checker/workflows/check_business_status.md`](business_checker/workflows/check_business_status.md) — workflow SOP
- [`docs/PROGRAM_OVERVIEW.md`](docs/PROGRAM_OVERVIEW.md) — full architecture and prompt reference
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — Railway web deployment guide

## License

MIT — see [`LICENSE`](LICENSE).

## Contact

Julian Hernandez · IVMF · Syracuse University · julianhernandez2155@gmail.com
