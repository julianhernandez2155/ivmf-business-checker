# Feature Research

**Domain:** Hosted bulk business-verification / data-enrichment SaaS (with manual review + outreach workflows)
**Researched:** 2026-05-12
**Confidence:** HIGH (patterns drawn from well-documented comparables: Clearbit/HubSpot Breeze Intelligence, ZoomInfo, Apollo.io, Dun & Bradstreet Hoovers, Hunter.io, NeverBounce, ZeroBounce, Middesk, Bench/Truework KYB platforms)

**Reading guide for downstream selection:**
Every row is tagged for the milestone scoping multi-select:
- `Category`: auth | canonical-matching | jobs | manual-workflows | outreach | analytics | export | cache
- `Tag`: table-stakes | differentiator | anti-feature
- `Complexity`: S (day) | M (week) | L (multi-week)
- `Depends on v1.0`: explicit handoff from preserved Python engine

---

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any of these makes the platform feel broken to an IVMF staff user pivoting off the desktop app, or to anyone who's used a comparable verification/enrichment SaaS.

| # | Feature | Category | Why Expected | Complexity | Depends on v1.0 | Notes |
|---|---------|----------|--------------|------------|-----------------|-------|
| TS-1 | Email/password + magic-link login | auth | Every B2B SaaS in 2026 has it (Supabase Auth ships it free); password-only feels archaic for non-technical staff | S | No | Use Supabase Auth, gate with email-domain allowlist (`@syr.edu`, `@ivmf.syracuse.edu`) so randoms can't sign up |
| TS-2 | Two-role RBAC (admin vs user) with route + RLS enforcement | auth | Without this, every user can rotate API keys / approve outreach; PROJECT.md locks in admin+user only | M | No | Role on `auth.users.app_metadata` (not user_metadata — that's client-editable); enforce in middleware **and** RLS. Common Supabase mistake: relying on client-side checks only |
| TS-3 | CSV/XLSX upload with column mapping UI | jobs | Every enrichment SaaS (Clearbit, Apollo) does this; users have wildly inconsistent column names ("BusinessName" vs "Company" vs "DBA") | M | Reuses v1.0 column normalization logic from `tools/columns.py` | Preview first 5 rows, let user map → canonical fields, store mapping for re-use per user |
| TS-4 | Pre-flight cost estimate before run starts | jobs | NeverBounce, ZeroBounce, Hunter all show "this will cost ~$X / Y credits" before commit; without it a 50k-row upload at $0.005 = $250 surprise | S | Multiply rows × expected API calls × per-call cost; subtract estimated cache-hit rate | Show estimate, require explicit "Start run" click, log estimate vs actual for analytics |
| TS-5 | Real-time progress bar (rows processed / total, ETA, current status) | jobs | Browser-close-safe progress is the **whole point** of the pivot vs desktop; users will refresh constantly to check | M | Worker writes batched progress to Supabase Realtime channel; UI subscribes | Batch updates to ≤1/sec to avoid Realtime quota burn (common gotcha at 50k rows × per-row update = 50k events) |
| TS-6 | Resumable jobs surviving browser close, crash, credit exhaustion | jobs | Stated in PROJECT.md as a core pivot reason; pgmq visibility-timeout + heartbeat watchdog is the standard pattern | L | Reuses v1.0 checkpoint semantics, but persisted to Postgres `verifications` instead of CSV file | Worker pulls from pgmq with visibility timeout (e.g., 60s); heartbeat extends; if worker dies, message becomes visible again. Idempotency key on `verifications` prevents double-write on retry |
| TS-7 | Run history / "my runs" list with status, row count, $ spent, started_at | jobs | Every batch-processing SaaS shows a runs table; users need it to find prior work | S | New table; FK from `runs` → `auth.users` | Sort by `started_at desc`, filter by status (running, paused, complete, failed) |
| TS-8 | Download results as XLSX with AI columns appended | export | This is the core deliverable; downstream IVMF workflows depend on the exact column layout | S | **Direct reuse of v1.0 `tools/build_output.py`** — must produce byte-identical column order | Generate XLSX on worker, upload to Supabase Storage, signed URL in UI. Don't generate on Vercel (50MB / timeout limits) |
| TS-9 | Run-completion email receipt | jobs/outreach | Hours-long jobs without completion email = user has to keep tab open; Resend integration trivial | S | Resend; same template engine used for outreach | Include: run name, rows processed, $ spent, cache hit %, link to results |
| TS-10 | Shared cache layer (canonical business DB) | cache | Stated as pivot reason in PROJECT.md; users expect "I already checked this last month, don't re-charge me" | M | Replaces v1.0 SQLite cache; same TTL concept (30 days) but in Postgres with canonical match instead of name+city+state hash | Cache hit = read latest `business_current_state` row matching canonical_id; cache miss = enqueue verification |
| TS-11 | Canonical matching: EIN auto-merge | canonical-matching | Industry-standard primary key for US businesses; D&B, Middesk, Truework all key on EIN when available | M | Net-new (v1.0 had no EIN field) | Unique constraint on `canonical_businesses.ein` where EIN is not null; auto-merge during ingest |
| TS-12 | Canonical matching: 2-of-N field consensus → review queue | canonical-matching | PROJECT.md decision: shared addresses (registered agents), shared domains (holding co's), shared phones (answering services) make silent merges unsafe | L | Net-new | Trigram similarity on name + exact match on 2 of {address, phone, domain, city+state}; matches without EIN → `merge_review` queue, not auto-merge |
| TS-13 | Admin-managed API keys with monthly budget cap + hard stop | auth/jobs | Stated pivot reason; standard pattern in Stripe/Twilio/etc. — usage caps prevent runaway spend | M | Net-new; reuses Perplexity/FireCrawl client classes from v1.0 | Encrypted at rest (pgcrypto or Supabase Vault); worker reads cap before each call; reaches cap → pauses run with `paused_credit_exhausted` status (resumable by admin after raising cap) |
| TS-14 | Manual review queue for uncertain / merge_review / outreach_response | manual-workflows | Without review UI, the 2-of-N matches stay stuck and "uncertain" rows never get resolved → product becomes a write-only system | M | Reads aggregator outputs; status field already exists in v1.0 logic | One unified inbox with type filters; row-level "accept / reject / request outreach" actions; writes a new `verifications` row (append-only) |
| TS-15 | Run-level error log / failure inspection | jobs | When 5k of 50k rows fail, the user needs to see why and retry; v1.0 had `retry-failed-rows`, web version needs equivalent | S | Reuses v1.0 retry-failed-rows logic, surfaced as a UI button | Filter row list by `status = failed`, show error message, "Retry failed rows" button |
| TS-16 | Audit log on admin DB edits | manual-workflows | Stated in PROJECT.md constraints: "admin edits create new verifications, never overwrite" — IVMF will be asked to justify status decisions | M | Append-only `verifications` ledger pattern | Every admin "edit" = new verification row with `source = manual_admin`, `actor_id = auth.uid()`, optional `reason` text. Old rows never updated |

### Differentiators (Improve Quality / Trust / Cost)

These are where the platform earns trust beyond a generic enrichment SaaS — especially for a government-adjacent / compliance-watched buyer like IVMF.

| # | Feature | Category | Value Proposition | Complexity | Depends on v1.0 | Notes |
|---|---------|----------|-------------------|------------|-----------------|-------|
| D-1 | Append-only verifications ledger w/ idempotency keys | canonical-matching | "We can prove what we said about this business on any date, and re-runs don't double-bill or double-write" — major trust signal for IVMF compliance | M | Net-new persistence; aggregator logic preserved | Idempotency key = hash(canonical_id + run_id + pass_number + provider). Unique index. Insert-or-skip on conflict. This is the moat against silent corruption |
| D-2 | Multi-pass aggregator with override logic running on worker | canonical-matching | Already shipped in v1.0; need to port. Producing higher-confidence statuses than single-pass competitors (Clearbit returns one answer, no consensus) | M | **Direct reuse of v1.0 aggregator** | Worker reads N pass results from `verifications`, runs aggregator, writes to `business_current_state` materialized table. Aggregator code unchanged |
| D-3 | Eval harness in CI with regression gate on worker deploy | analytics/jobs | "Our model+prompt changes can't silently degrade" — stated in PROJECT.md constraints; competitors don't expose this | M | **Reuses v1.0 eval harness + gold set** | GitHub Actions runs `pytest business_checker/eval/` on PR; fails build if accuracy drops below baseline. Block merge |
| D-4 | Weekly eval drift alert (production drift detection) | analytics | LLMOps requirement (from your global rules); sends email if weekly eval score drops >10% from baseline | M | Reuses v1.0 eval harness | Scheduled function (Supabase cron) runs eval against current prompt + model, emails admin if drift detected |
| D-5 | Random-sample labeling UI for ongoing gold-set growth | manual-workflows | Differentiator vs all consumer enrichment tools — gives admin a way to **expand** the gold set from real production runs, not just static baseline | M | Writes to a new `labels` table; eval harness reads it | Admin picks a run → sample N rows → blind-label → label diffed against AI output → contributes to drift metric |
| D-6 | Email outreach with tokenized response forms (admin-approved) | outreach | Closes the "uncertain" loop without manual phone calls; competitors don't do this (they just return "unknown") | L | Net-new; Resend + signed tokens | Admin clicks "request outreach" on a row → ticket created → admin approves batch → Resend sends email with tokenized form URL → response writes to outreach_responses → admin **manually** approves response → new verification row |
| D-7 | Tokenized form responses with admin approval gate before write | outreach | PROJECT.md decision: "Auto-acceptance of email outreach form responses — Rejected; token URLs can be spoofed" — making this an explicit gate is the differentiator | M | Net-new | Form response = `outreach_response` row with status=pending; admin reviews in queue; approval = new `verifications` row with `source = outreach_confirmed` |
| D-8 | Pre-flight estimate uses **predicted** cache hit rate from historical data | analytics/jobs | Better than naive "rows × cost" estimate; competitors don't show this | S | Reads historical cache hit % from analytics | Show: "Est. 12,000 rows × $0.005 − ~40% cache hit = ~$36" with link to historical hit rates |
| D-9 | Cache hit rate trending over time (per user, global) | analytics | Visualizes the core ROI of the pivot ("look, we're paying less per row over time"); great pitch for IVMF leadership | S | Net-new | Stacked area chart: cache hits vs misses per week. Highlight cost saved |
| D-10 | Per-API-key spend dashboard with cap utilization gauge | analytics | Admin needs to know "we're at 80% of monthly cap, raise it or pause new runs" | S | Net-new | One row per key: spent / cap / % used, with color tier (green/amber/red) |
| D-11 | Status distribution chart (active/likely_closed/closed/uncertain) per run + global | analytics | Both a sanity check (did the aggregator break?) and a useful artifact for IVMF reports | S | Reads `business_current_state` | Pie + over-time line chart |
| D-12 | Outreach response rate analytics (sent / opened / submitted / approved) | analytics/outreach | Justifies the outreach feature's existence; if response rate <5%, kill it | M | Resend webhook → updates `outreach_tickets` | Funnel viz; per-template breakdown if multiple templates exist |
| D-13 | Manual queue depth + aging alerts | analytics/manual-workflows | "12 rows have been in merge_review for >7 days" — keeps the human-in-the-loop honest | S | Reads queue table | Dashboard tile + email if any item > N days old |
| D-14 | Per-row provenance: which provider, which pass, which run produced each verification | canonical-matching | Click any row → full history of every check ever done on this business across all uploads. Audit gold | S | Reads `verifications` ledger | This basically falls out of the append-only design for free |
| D-15 | Admin: pause / resume / cancel any run (mid-flight) | jobs | Competitors don't expose this; useful for "stop, we just realized this is the wrong dataset" | M | Worker checks run status before each row | Soft signal via Supabase channel + DB status check; worker exits gracefully on pause |
| D-16 | Run-level "share read-only link" for non-admin stakeholders | jobs/auth | Jim/leadership wants to see results without getting an account | S | Signed URL → read-only run view | Tokenized URL with optional expiry; logs each view |
| D-17 | Bulk CSV reupload that auto-deduplicates against existing canonical DB before any API call | cache/jobs | Powerful demo moment: "you uploaded 50k rows, 38k were already verified within TTL, the run will only check 12k" | M | Combines TS-10 + TS-11 + TS-12 | This is the cost-trends-to-zero story made visible |
| D-18 | Idempotent run resumption: same CSV uploaded twice = same run, not two | jobs | Prevents accidental duplicate billing when a user refreshes mid-upload | S | Hash CSV → run lookup | Show modal: "you uploaded this file 3 minutes ago, resume that run?" |

### Anti-Features (Tempting but Cause Regret)

Each row includes the specific failure mode and the better alternative — these get auto-rejected during scoping.

| # | Feature | Category | Why Tempting | Failure Mode | Better Alternative |
|---|---------|----------|--------------|--------------|--------------------|
| AF-1 | Auto-merge canonical businesses on **any** 2-of-N field match (no EIN) | canonical-matching | "Less manual review work for admin!" | Shared registered-agent addresses, holding-co domains, answering-service phones cause silent merges of distinct businesses → gold set corruption → eval scores rise falsely → IVMF acts on wrong data | EIN auto-merge only; 2-of-N → `merge_review` queue (PROJECT.md decision, keep it) |
| AF-2 | Auto-accept email outreach form responses as verifications | outreach | "Tokens are signed, why not skip admin review?" | Token URLs leak in email forwards, get clicked by mailroom staff, submitted by competitors or scrapers; verifications corrupted with no recourse | Admin approval gate on every outreach response (PROJECT.md decision); rate-limit per token; log IP + user-agent (D-7) |
| AF-3 | User-supplied API keys ("BYOK") | auth | "Cleaner billing separation" | Each non-technical IVMF staff member managing a Perplexity key = key leaks, expired keys, inconsistent tiers, support burden; defeats the entire pivot rationale | Admin-managed keys with per-user run caps (PROJECT.md decision) |
| AF-4 | Real-time per-row updates via Realtime (no batching) | jobs | "Maximum responsiveness!" | 50k rows × Realtime event per row = burns Supabase quota, jams browser, slows worker due to network overhead | Batch progress to 1/sec or every 100 rows (TS-5 implementation note) |
| AF-5 | Soft-delete on `verifications` (allow admin to "delete" a verification) | manual-workflows | "Admin made a mistake, let them undo it" | Breaks append-only audit guarantee; IVMF cannot prove what was claimed when; creates the exact data-integrity gap the ledger was designed to prevent | Append-only forever; admin "corrections" = new verification row with reason; soft hide only at the UI layer if needed (D-14) |
| AF-6 | More than two RBAC roles in v1.1 | auth | "Future-proof for partners / read-only stakeholders" | Tripling permission matrix complexity; RLS policies explode combinatorially; YAGNI hits hard when external partners aren't onboarding yet | Two roles only; use signed share links (D-16) for external read-only access; revisit roles only if external partner deal closes |
| AF-7 | Multi-tenant data isolation across IVMF departments | auth | "Departmental clean-room data!" | RLS scoped by department doubles every policy, breaks shared canonical DB (whole pivot point), and IVMF hasn't asked for it | RLS scoped by user only (PROJECT.md decision); revisit at v2 if data-sharing concerns surface |
| AF-8 | Auto-retry failed rows infinitely with exponential backoff | jobs | "Maximum reliability!" | FireCrawl 429s or provider outages cause runaway retry storms that burn the entire monthly budget cap in a loop; cost spikes with no signal to admin | Max-N retry (e.g., 3) with backoff, then mark row `failed` and surface in error log; admin chooses to retry-failed-rows (TS-15) |
| AF-9 | Auto-extending budget cap when reached | jobs | "Don't interrupt long runs!" | Defeats the entire purpose of a hard cap; turns a $250 surprise into a $2,500 surprise. Stripe/Twilio learned this lesson decades ago | Hard pause on cap reached with admin email; resume requires admin action to raise cap (TS-13) |
| AF-10 | "AI explains its reasoning" surfaced to all users for every row | manual-workflows | "Transparency!" | Reasoning text is verbose, often hallucinated, and leaks internal prompt structure; novice users treat it as ground truth and trust wrong answers | Surface reasoning only on rows where status = uncertain OR admin opens detail view; never use as decision input |
| AF-11 | Browser-side run execution (Edge Function or client-side worker) | jobs | "Saves Railway costs!" | Vercel Edge has 30s timeout, Lambda has 15min; hours-long runs literally cannot complete (PROJECT.md constraint) | Railway worker is the locked-in decision; don't relitigate |
| AF-12 | Custom user-defined prompts per run | jobs | "Power user feature!" | Eval harness covers ONE prompt; user-edited prompts silently bypass the regression gate; quality becomes unmeasurable per-run | Single admin-managed prompt; eval enforces stability (D-3) |
| AF-13 | "Smart" auto-categorization that auto-applies admin-approved labels to similar rows | manual-workflows | "Save admin time on review queue!" | A wrong label cascades silently across the canonical DB; one bad admin click corrupts hundreds of rows; no easy undo with append-only ledger | One row at a time; admin can multi-select for **identical** action, never for "smart" auto-apply |
| AF-14 | Webhook out to external systems on every verification | jobs | "Integrate with CRM!" | Becomes a contract you can't break; webhook reliability becomes your problem; not asked for by IVMF | Defer to v2; XLSX export (TS-8) is the integration point for now |
| AF-15 | Storing raw Perplexity/FireCrawl response bodies indefinitely | jobs | "Maximum traceability!" | PII (owner names + addresses) in JSON blobs; Storage costs balloon; compliance review gets harder, not easier | Store hash + structured aggregator output only; retain raw body for 30 days then purge (matches v1.0 cache TTL) |

---

## Feature Dependencies

```
[TS-2 Two-role RBAC]
    └──required-by──> [TS-13 Admin-managed API keys]
                            └──required-by──> [TS-6 Resumable jobs] (worker reads key)
                                                    └──required-by──> [TS-5 Realtime progress]
                                                                            └──required-by──> [TS-8 XLSX export]
                                                                                                    └──required-by──> [TS-9 Run completion email]

[TS-3 CSV upload + mapping]
    └──required-by──> [TS-4 Pre-flight estimate]
                            └──required-by──> [D-8 Cache-hit-aware estimate]
                            └──required-by──> [TS-6 Resumable jobs]

[TS-11 EIN auto-merge]
    └──enables──> [TS-10 Shared cache]
                        └──required-by──> [D-9 Cache hit trending]
                        └──required-by──> [D-17 Reupload dedupe demo]

[TS-12 2-of-N → merge_review]
    └──required-by──> [TS-14 Manual review queue]
                            └──required-by──> [D-6 Outreach tickets]
                                                    └──required-by──> [D-7 Outreach approval gate]
                                                                            └──required-by──> [D-12 Outreach response rate analytics]

[D-1 Append-only verifications]
    └──required-by──> [D-2 Multi-pass aggregator on worker]
                            └──required-by──> [D-3 Eval harness in CI]
                                                    └──required-by──> [D-4 Weekly drift alert]
                                                                            └──required-by──> [D-5 Random-sample labeling]
    └──required-by──> [TS-16 Audit log on admin edits]
    └──required-by──> [D-14 Per-row provenance]

[D-15 Pause/resume mid-flight] ──conflicts──> [AF-8 Infinite auto-retry]
[D-16 Share read-only link] ──substitutes──> [AF-6 >2 RBAC roles]
[D-17 Reupload dedupe] ──substitutes──> [AF-3 BYOK]
```

### Dependency Notes

- **Auth before anything writes data:** TS-1/TS-2 must land before any feature that calls `auth.uid()` in RLS — i.e., before everything else. This locks the foundation phase ordering.
- **Append-only ledger is the spine:** D-1 must land before D-2 (aggregator), D-3 (eval), TS-14 (review queue), and TS-16 (audit). It's the keystone — get the schema wrong here and every downstream feature has to be rewritten.
- **Canonical matching unlocks cache:** TS-11 + TS-12 are prerequisites for TS-10. Without canonical IDs, the cache layer is just the v1.0 SQLite cache in Postgres clothing.
- **Outreach is the longest dependency chain:** TS-14 (manual queue) → D-6 (outreach send) → D-7 (approval gate) → D-12 (analytics). Plus external blockers: IVMF subdomain DNS + Resend SPF/DKIM/DMARC + Jim/compliance PII signoff. Schedule outreach **last** in milestone.
- **Eval harness is the safety net for everything aggregator-related:** D-3 must run in CI before D-2's aggregator is touched, or override logic rots silently.
- **D-15 (pause/resume) directly contradicts AF-8 (infinite retry):** if you ship D-15 you cannot also ship AF-8 — they fight over run state.

---

## Milestone v1.1 Phase Recommendation

Ordered by dependency graph, not preference.

### Phase F: Foundation (must-land-first)
- TS-1 auth, TS-2 RBAC, TS-13 admin API keys (minus budget cap enforcement, just storage), worker scaffold, pgmq, schema migrations, D-1 append-only verifications with idempotency keys

### Phase C: Cache-Only Verification (no live API yet)
- TS-3 CSV upload + mapping, TS-11 EIN merge, TS-12 2-of-N + merge_review queue, TS-10 cache reads, TS-8 XLSX export, TS-7 run history, D-14 per-row provenance, D-17 reupload dedupe demo

### Phase L: Live Verification
- TS-6 resumable jobs, TS-5 Realtime progress (batched), TS-13 budget cap enforcement, TS-4 pre-flight estimate, D-2 aggregator on worker, D-3 eval harness in CI, TS-15 error log + retry, TS-9 run-completion email, D-8 cache-aware estimate, D-15 pause/resume, D-18 idempotent run resumption

### Phase M: Manual Workflows
- TS-14 unified review queue, TS-16 audit log on admin edits, D-5 random-sample labeling UI, D-13 queue aging alerts

### Phase O: Outreach (blocked by IT + compliance)
- D-6 outreach tickets, D-7 approval gate, D-12 response analytics
- **Cannot start until:** IVMF subdomain DNS, Resend SPF/DKIM/DMARC, Jim PII signoff

### Phase A: Analytics
- D-9 cache trending, D-10 spend dashboard, D-11 status distribution, D-4 weekly drift alert, D-16 share read-only link

---

## Feature Prioritization Matrix (P1 = must-have for v1.1, P2 = should-have, P3 = nice-to-have)

| # | Feature | User Value | Implementation Cost | Priority |
|---|---------|------------|---------------------|----------|
| TS-1 | Auth | HIGH | LOW | P1 |
| TS-2 | RBAC | HIGH | MEDIUM | P1 |
| TS-3 | CSV upload + mapping | HIGH | MEDIUM | P1 |
| TS-4 | Pre-flight estimate | HIGH | LOW | P1 |
| TS-5 | Realtime progress | HIGH | MEDIUM | P1 |
| TS-6 | Resumable jobs | HIGH | HIGH | P1 |
| TS-7 | Run history | HIGH | LOW | P1 |
| TS-8 | XLSX export | HIGH | LOW | P1 |
| TS-9 | Completion email | MEDIUM | LOW | P1 |
| TS-10 | Shared cache | HIGH | MEDIUM | P1 |
| TS-11 | EIN auto-merge | HIGH | MEDIUM | P1 |
| TS-12 | 2-of-N review queue | HIGH | HIGH | P1 |
| TS-13 | Admin API keys + caps | HIGH | MEDIUM | P1 |
| TS-14 | Manual review queue | HIGH | MEDIUM | P1 |
| TS-15 | Error log / retry | HIGH | LOW | P1 |
| TS-16 | Admin edit audit log | HIGH | MEDIUM | P1 |
| D-1 | Append-only ledger | HIGH | MEDIUM | P1 |
| D-2 | Aggregator on worker | HIGH | MEDIUM | P1 |
| D-3 | Eval harness in CI | HIGH | MEDIUM | P1 |
| D-14 | Per-row provenance | HIGH | LOW | P1 |
| D-15 | Pause/resume runs | MEDIUM | MEDIUM | P2 |
| D-17 | Reupload dedupe | HIGH | MEDIUM | P1 |
| D-18 | Idempotent run resume | MEDIUM | LOW | P2 |
| D-4 | Weekly drift alert | MEDIUM | MEDIUM | P2 |
| D-5 | Random-sample labeling | HIGH | MEDIUM | P2 |
| D-6 | Outreach tickets | HIGH | HIGH | P2 (blocked by IT/compliance) |
| D-7 | Outreach approval gate | HIGH | MEDIUM | P2 (chained to D-6) |
| D-8 | Cache-aware estimate | MEDIUM | LOW | P2 |
| D-9 | Cache hit trending | MEDIUM | LOW | P2 |
| D-10 | Spend dashboard | MEDIUM | LOW | P2 |
| D-11 | Status distribution | MEDIUM | LOW | P2 |
| D-12 | Outreach analytics | MEDIUM | MEDIUM | P3 (post-outreach launch) |
| D-13 | Queue aging alerts | LOW | LOW | P3 |
| D-16 | Share read-only link | MEDIUM | LOW | P3 |

---

## Comparable Product Feature Analysis

Drawn from public docs / product pages of comparables. Used to validate "what users expect."

| Feature | Clearbit / HubSpot Breeze | ZoomInfo | Apollo.io | Middesk (KYB) | NeverBounce | IVMF Business Checker v1.1 |
|---------|---------------------------|----------|-----------|---------------|-------------|----------------------------|
| Bulk CSV upload | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ TS-3 |
| Pre-flight cost estimate | ✗ (subscription) | ✗ | ✗ | ✓ | ✓ | ✓ TS-4 + D-8 (better: cache-aware) |
| Shared cache across uploads | Implicit (Clearbit owns the data) | Implicit | Implicit | Implicit | N/A | ✓ TS-10 (transparent to user — they see hit rate) |
| Canonical entity matching | EIN + name+domain | EIN + DUNS | Name + domain | EIN + Sec of State | N/A | ✓ TS-11 + TS-12 (EIN auto, 2-of-N review) |
| Resumable hours-long jobs | API-level only | ✓ | ✓ | ✓ | ✓ | ✓ TS-6 (pgmq + heartbeat) |
| Real-time progress | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ TS-5 (batched) |
| Manual review queue | ✗ | Partial (suppressions) | ✗ | ✓ (KYB requires it) | ✗ | ✓ TS-14 (differentiator vs enrichment SaaS) |
| Append-only audit ledger | ✗ | ✗ | ✗ | ✓ (regulated) | ✗ | ✓ D-1 (differentiator) |
| Email outreach to verify | ✗ | ✗ | ✓ (outbound sales) | ✗ | ✗ | ✓ D-6 (unique use: verification, not sales) |
| Eval harness / regression gate | ✗ (closed) | ✗ | ✗ | ✗ | ✗ | ✓ D-3 (rare; major trust differentiator) |
| Admin-managed shared keys | Org-level subscription | Org-level | Org-level | Org-level | Per-key billing | ✓ TS-13 (admin sets, users consume) |

**Read:** the *Middesk* row is the closest analog (KYB / business verification with compliance posture). The append-only ledger + manual review queue + outreach loop is essentially Middesk-shaped, plus IVMF-specific: random-sample labeling, eval harness in CI, and outbound email outreach to confirm operating status.

---

## Sources

- Middesk product docs — KYB workflow, business graph model (https://www.middesk.com)
- Clearbit/HubSpot Breeze Intelligence docs — bulk enrichment, canonical matching
- ZoomInfo Engage — bulk processing, cache patterns
- Apollo.io product docs — bulk enrichment + outreach
- NeverBounce / ZeroBounce — pre-flight cost estimate UX, bulk validation jobs
- Hunter.io — outreach + verification pattern (response gate is similar)
- Dun & Bradstreet Hoovers — EIN/DUNS canonical key precedent
- Supabase docs (Auth, pgmq, Realtime, RLS) — implementation patterns for table-stakes
- Resend docs — transactional + SPF/DKIM/DMARC setup pattern for outreach
- Existing v1.0 codebase (`business_checker/`) — feature inventory of what's preserved
- PROJECT.md + STATE.md (2026-05-12) — confirmed pivot rationale + locked decisions

---

*Feature research for: hosted bulk business-verification SaaS with audit + outreach*
*Researched: 2026-05-12*
