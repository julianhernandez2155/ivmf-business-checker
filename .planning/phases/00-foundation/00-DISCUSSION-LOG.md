# Phase 0: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 00-foundation
**Areas discussed:** Repo & deploy layout, Local dev experience, Migration tooling, Phase 0 "done" demo, Auth UX

---

## Initial Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Repo & deploy layout | Monorepo vs split repos | ✓ |
| Local dev experience | Supabase local (Docker) vs cloud-only dev project | ✓ |
| Migration tooling | Supabase CLI only vs Drizzle migrations on top | ✓ |
| Phase 0 "done" demo | What concretely proves Phase 0 is shipped | ✓ |

**User's choice:** Deferred to Claude's recommendation across all four ("what would you recommend?").

**Notes:** Julian asked for recommendations rather than picking individually. All four areas treated as a single decision batch.

---

## Repo & Deploy Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Monorepo | Single repo with `web/`, `worker/`, `supabase/` subdirs; Vercel + Railway both deploy from subdirectories | ✓ |
| Split repos | Three repos — one per service. Each deploys cleanly to its target. | |

**User's choice:** Monorepo (accepted recommendation).
**Notes:** Trade-off — bigger PRs vs atomic schema changes. Recommendation favored atomicity given solo-builder reality and the locked decision that schema changes ripple through all three deploy targets.

---

## Local Dev Experience

| Option | Description | Selected |
|--------|-------------|----------|
| Cloud-only dev (dedicated dev Supabase project) | No Docker; dev = small Supabase project; prod = separate project | ✓ |
| Supabase local (Docker) | Full offline dev; matches prod via local stack | |

**User's choice:** Cloud-only (accepted recommendation).
**Notes:** Julian builds from a laptop between class/work; Docker friction not justified for a solo build. Cloud free tier covers dev project cost.

---

## Migration Tooling

| Option | Description | Selected |
|--------|-------------|----------|
| Supabase CLI as single source of truth; Drizzle introspect-only | Hand-written/exported SQL migrations; Drizzle generates TS types via `drizzle-kit pull`; datamodel-code-generator does same for Python | ✓ |
| Drizzle migrations on top of Supabase | Drizzle owns schema; Supabase CLI only for RLS/triggers | |

**User's choice:** Supabase CLI only (accepted recommendation).
**Notes:** Two migration tools = drift. Research already pinned RLS/triggers/cron to Supabase CLI; making Drizzle introspect-only removes the conflict surface. A CI guard forbids `drizzle-kit generate`.

---

## Phase 0 "Done" Demo

| Option | Description | Selected |
|--------|-------------|----------|
| The drift-trip PR demo | Intentional schema drift PR fails CI; `/me` page round-trips magic-link login; append-only assertion test; eval-CI regression test; worker heartbeat; Resend DNS ticket filed | ✓ |
| No demo, mark phase done when all 10 ROADMAP success criteria are checked | Less ceremony; rely on success criteria alone | |

**User's choice:** Drift-trip PR demo (accepted recommendation).
**Notes:** Without a concrete demo, Phase 0 can "look done" while quietly broken on the gates that protect every later phase. Six concrete acceptance items added to CONTEXT.md as D-00-11.

---

## Auth UX (follow-up question)

| Option | Description | Selected |
|--------|-------------|----------|
| Magic-link only | One input on sign-in page; AUTH-01 satisfied via "or" clause; smallest Phase 0 surface | ✓ |
| Magic-link + password | Both options at launch; password reset flow included | |

**User's choice:** Magic-link only (accepted recommendation).
**Notes:** Password UX can be added later if IVMF staff push back on email friction. Deferred to a future v1.2 minor phase.

---

## Claude's Discretion

The planner has flexibility on:
- Exact Postgres column types (Drizzle/datamodel-code-generator defaults)
- Folder layout inside `web/`, `worker/`, and `supabase/`
- CI provider (GitHub Actions default unless stronger reason)
- Heartbeat watchdog mechanism in Phase 0 (pg_cron vs worker self-loop)
- Test framework choices (pytest + vitest standard picks)
- `/me` page styling beyond "shows email and role"

## Deferred Ideas

- Password authentication UX → v1.2 minor phase
- CI on Railway/Vercel instead of GitHub Actions → defer
- Supabase local (Docker) dev → defer indefinitely
- Staging environment between dev and prod → defer
- Audit log retention/archival → v1.2+
- Outreach token HMAC implementation → Phase 4 scope
