# STATE.md

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-12 — Milestone v1.1 started

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)

**Core value:** Trustworthy bulk verification of veteran/minority-owned business lists with append-only audit history.
**Current focus:** Milestone v1.1 — Web Platform Pivot

## Accumulated Context

**v1.0 (desktop) is feature-complete and frozen.** All verification logic in `business_checker/tools/` (check_business, scrape_website, cache, checkpoint, build_output, columns) is preserved and ported as-is into the Railway worker. The Tkinter GUI and `run_checker.py` are not maintained going forward.

**Eval gold set lives at `business_checker/eval/`** and must run in CI on every worker deploy with a regression gate.

**Reference Run folders kept:** `business_checker/Runs/BMOSG_All_Businesses_2026-04-30_1619/` and `business_checker/Runs/Alabama_Product_Based_VOBs_2026-04-07_131659_7288/` — used as regression baselines.

**Repo cleanup completed 2026-05-12:** 22 MB → 8.2 MB. Removed stale runs, .DS_Store, __pycache__, .pytest_cache, .superpowers, and a duplicate `Business Checker/.env` that contained a real Perplexity key. **Perplexity key rotation recommended.**

**Architecture locked-in (see PROJECT.md Key Decisions):**
- Next.js on Vercel (UI + auth + lightweight API)
- Supabase (Postgres + Auth + Realtime + pgmq + Storage)
- Railway (Python FastAPI worker pulling pgmq, runs existing check_business.py)
- Resend (transactional email on IVMF subdomain)

**Open externally-blocked items:**
- IVMF subdomain + Resend DNS records (SPF/DKIM/DMARC) — IT ticket
- PII boundary signoff (owner names + addresses to Perplexity) — Jim/compliance
- Hosting residency confirmation — Jim/IT
- Data retention policy decision — Jim
