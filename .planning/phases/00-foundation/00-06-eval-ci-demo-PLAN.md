---
phase: 00-foundation
plan: 06
type: execute
wave: 5
depends_on: [01, 02, 03, 04, 05]
files_modified:
  - .github/workflows/eval-ci.yml
  - business_checker/eval/score.py
  - business_checker/eval/routing_labels.py
  - business_checker/eval/baseline.json
  - business_checker/eval/README.md
  - .planning/phases/00-foundation/00-EVIDENCE.md
  - .planning/STATE.md
autonomous: false
requirements:
  - ANALYTICS-04
must_haves:
  truths:
    - "GitHub Actions eval-ci workflow runs on every PR + push to main and exits non-zero if accuracy regresses below baseline"
    - "eval-ci asserts n_examples >= 20 (Pitfall P8 defense) — false-pass on empty gold set is structurally prevented"
    - "eval_result.json contains a routing_distribution object with counts for all 6 routing-label buckets (D-00-12 measurement surface); informational only in Phase 0, gated in Phase 2"
    - "business_checker/eval/routing_labels.py exports the 6-value RoutingLabel enum imported by score.py (single source of truth for Phase 2)"
    - "Resend account exists; DKIM/SPF/DMARC records for IVMF subdomain are generated in the Resend dashboard"
    - "IT ticket is filed with the exact DNS records and the ticket ID is recorded in STATE.md"
    - "scripts/phase0-demo.sh executes against the dev Supabase project and confirms items 1, 4, 5 of D-00-11"
    - "00-EVIDENCE.md has all 6 D-00-11 items checked or has documented blockers"
  artifacts:
    - path: .github/workflows/eval-ci.yml
      provides: "Eval regression gate workflow"
      contains: "eval_result.json"
    - path: business_checker/eval/baseline.json
      provides: "Frozen baseline JSON used by the eval-ci comparison"
      contains: "accuracy"
    - path: .planning/phases/00-foundation/00-EVIDENCE.md
      provides: "Phase 0 exit evidence log with all 6 D-00-11 items resolved"
      contains: "D-00-11"
  key_links:
    - from: ".github/workflows/eval-ci.yml"
      to: "scripts/eval-ci.sh"
      via: "bash invocation"
      pattern: "bash scripts/eval-ci\\.sh"
    - from: "scripts/eval-ci.sh"
      to: "business_checker.eval.score module"
      via: "python -m invocation"
      pattern: "python -m business_checker\\.eval\\.score"
    - from: ".planning/phases/00-foundation/00-EVIDENCE.md"
      to: "Phase 0 exit demo (D-00-11)"
      via: "evidence cross-reference"
      pattern: "D-00-11 Item"
---

<objective>
Close out Phase 0 by landing the eval-CI regression gate (ANALYTICS-04), creating the Resend account and filing the IVMF subdomain DNS ticket with IT (D-00-11 item 6), and recording all evidence for the 6-item exit demo. This is the only plan in Phase 0 that requires human checkpoints (Resend ticket filing + demo PRs).

Purpose: Ship the last Phase 0 requirement (ANALYTICS-04) AND prove the entire phase works end-to-end via the D-00-11 walkthrough. The drift-trip PR and eval-regression PR are opened HERE so the gates are demonstrably alive, not just configured.

Output: eval-ci workflow, baseline.json, Resend ticket evidence, updated STATE.md, complete 00-EVIDENCE.md with all 6 demo items resolved.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/00-foundation/00-CONTEXT.md
@.planning/phases/00-foundation/00-RESEARCH.md
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@.planning/phases/00-foundation/00-EVIDENCE.md
@scripts/eval-ci.sh
@scripts/phase0-demo.sh
@business_checker/eval

<interfaces>
Eval score module contract (verify shape with `python -m business_checker.eval.score --help` before drafting workflow):

  python -m business_checker.eval.score --gold business_checker/eval/gold.json --out eval_result.json

Expected JSON output shape in eval_result.json:
  { "accuracy": 0.93, "n_examples": 124, "details": [...] }

If the existing score.py does NOT emit this exact shape, a thin shim is acceptable
(per Research Open Question 2). Do NOT modify the engine logic.

Resend DNS record set (Resend dashboard generates exact values):
  - SPF (TXT):   v=spf1 include:_spf.resend.com -all
  - DKIM (CNAME × 3):  resend._domainkey, resend2._domainkey, resend3._domainkey
  - DMARC (TXT) at _dmarc.<subdomain>:  v=DMARC1; p=none; rua=mailto:dmarc@<subdomain>
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Verify + adapt eval scorer output shape; add routing-label measurement surface (D-00-12); freeze baseline.json</name>
  <files>business_checker/eval/score.py, business_checker/eval/routing_labels.py, business_checker/eval/baseline.json, business_checker/eval/README.md</files>
  <read_first>
    - business_checker/eval/score.py (existing v1.0 scorer — current output shape)
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-12 — routing-aware measurement surface)
    - .planning/2026-05-13-decision-triage-not-oracle.md (canonical 6-value routing schema; mapping rules table)
    - .planning/phases/00-foundation/00-RESEARCH.md (Open Question 2 at lines 746-749; Pattern 7 at lines 575-611)
    - .planning/research/PITFALLS.md (P8 RLS-filtered gold set / n_examples assertion)
    - scripts/eval-ci.sh (the script that will consume the JSON output)
  </read_first>
  <action>
    First inspect the existing scorer:
    ```bash
    cd business_checker
    python -m eval.score --help 2>&1 || python eval/score.py --help 2>&1
    ls eval/
    cat eval/gold.json | head -5 2>/dev/null || echo "gold.json missing"
    ```

    Three possible outcomes:

    **Outcome A — scorer already emits `{"accuracy": ..., "n_examples": ...}`:**
    No code change needed. Run it once to produce `eval_result.json`, then copy that file to `business_checker/eval/baseline.json`:
    ```bash
    cd business_checker
    python -m eval.score --gold eval/gold.json --out /tmp/eval_result.json --dry-run
    # Verify shape
    python -c "import json; d=json.load(open('/tmp/eval_result.json')); assert 'accuracy' in d and 'n_examples' in d, f'shape mismatch: {list(d.keys())}'; print(d)"
    cp /tmp/eval_result.json eval/baseline.json
    ```

    **Outcome B — scorer emits different keys (e.g., `score`, `count`):**
    Add a thin output adapter at the END of `business_checker/eval/score.py` — do NOT modify the existing scoring logic. Append something like:
    ```python
    # Phase 0 ANALYTICS-04 adapter — emit standardized JSON shape.
    # Wraps existing score output to {accuracy, n_examples, details}.
    if __name__ == "__main__":
        import json, sys, argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--gold", default="business_checker/eval/gold.json")
        parser.add_argument("--out", default="eval_result.json")
        parser.add_argument("--dry-run", action="store_true",
                            help="Skip API calls; use cached/synthetic predictions")
        args, _ = parser.parse_known_args()

        # Call the existing scoring function (whatever it's named — adjust)
        # Example shape — replace with the real function call:
        try:
            from business_checker.eval.score import run_scoring  # adjust import
            raw = run_scoring(gold_path=args.gold, dry_run=args.dry_run)
        except ImportError:
            # Fallback: assume the file already runs and emits to stdout
            print("WARN: run_scoring import failed; running fallback", file=sys.stderr)
            raw = {"accuracy": 0.0, "n_examples": 0}

        # Normalize keys
        out = {
            "accuracy": float(raw.get("accuracy") or raw.get("score") or 0.0),
            "n_examples": int(raw.get("n_examples") or raw.get("count") or 0),
            "details": raw.get("details", []),
        }
        with open(args.out, "w") as fh:
            json.dump(out, fh, indent=2)
        print(json.dumps({"accuracy": out["accuracy"], "n_examples": out["n_examples"]}))
    ```
    Adjust function names to match what's actually in `score.py`. Keep changes minimal — the goal is `python -m business_checker.eval.score --gold X --out Y` produces the expected JSON.

    **Outcome C — scorer does not have a `__main__` entry point or eval/ is partially shipped:**
    Add the minimal `__main__` block above to `business_checker/eval/__main__.py` (new file) so `python -m business_checker.eval.score` works. If `gold.json` doesn't exist, document the gap in `business_checker/eval/README.md` and create a placeholder gold.json with at least 20 example records FROM THE BMSG/Alabama VOB reference runs (these are already in `business_checker/Runs/`). Defer real population to Phase 2.

    **Routing-label measurement surface (D-00-12) — REQUIRED in all three outcomes.**

    Create `business_checker/eval/routing_labels.py` as the single source of truth for the 6-value routing schema. Phase 2 imports this same enum for the production mapping function; Phase 0 only uses it for the eval distribution report.

    ```python
    """Routing labels for triage output (locked 2026-05-13).

    Single source of truth for the 6-value schema defined in
    .planning/2026-05-13-decision-triage-not-oracle.md.

    Phase 0: imported by eval/score.py to emit a distribution report (informational).
    Phase 2: imported by the worker's post-adjudicator mapping function (gated).
    """
    from enum import Enum
    from typing import Any


    class RoutingLabel(str, Enum):
        ACTIVE_AUTO_ACCEPTED = "Active - auto accepted"
        LIKELY_CLOSED_STRONG_EVIDENCE = "Likely Closed - strong evidence"
        UNCERTAIN_MANUAL_REVIEW = "Uncertain - manual review recommended"
        UNCERTAIN_OUTREACH = "Uncertain - outreach recommended"
        LIKELY_CLOSED_OUTREACH = "Likely Closed - outreach recommended"
        NO_CONTACT_AVAILABLE = "No contact available"


    def stub_label_from_gold(example: dict[str, Any]) -> RoutingLabel:
        """Phase 0 stub mapping — uses ONLY v1.0 gold-set fields.

        Phase 2 replaces this with a real mapping over
        (verdict, confidence, requires_review, contact_available)
        per the triage decision doc. Phase 0 does not have requires_review
        or contact_available, so we approximate from verdict + confidence only.

        DO NOT use this stub for production routing. It exists so the
        eval-CI report has a populated distribution column from day one.
        """
        verdict = (example.get("expected_status") or example.get("verdict") or "").lower()
        confidence = float(example.get("expected_confidence") or example.get("confidence") or 0.0)
        if verdict == "active" and confidence >= 0.70:
            return RoutingLabel.ACTIVE_AUTO_ACCEPTED
        if verdict in ("likely_closed", "closed") and confidence >= 0.70:
            return RoutingLabel.LIKELY_CLOSED_STRONG_EVIDENCE
        if verdict in ("likely_closed", "closed"):
            return RoutingLabel.LIKELY_CLOSED_OUTREACH
        return RoutingLabel.UNCERTAIN_MANUAL_REVIEW


    def empty_distribution() -> dict[str, int]:
        return {label.value: 0 for label in RoutingLabel}
    ```

    Update the scorer's `__main__` block (whichever outcome above applied) to compute and emit a `routing_distribution` field. After computing `out["accuracy"]` and `out["n_examples"]`, add:

    ```python
    from business_checker.eval.routing_labels import (
        stub_label_from_gold,
        empty_distribution,
    )

    dist = empty_distribution()
    for ex in raw.get("details", []) or []:
        dist[stub_label_from_gold(ex).value] += 1
    out["routing_distribution"] = dist
    ```

    If the scorer doesn't surface per-example records in `details`, read the gold file directly inside the `__main__` block and iterate over it for the distribution count — the distribution is over the gold set, NOT the predictions, because Phase 0 doesn't run the adjudicator.

    Create `business_checker/eval/baseline.json` (after running scorer once):
    ```json
    {
      "accuracy": 0.93,
      "n_examples": 124,
      "routing_distribution": {
        "Active - auto accepted": 70,
        "Likely Closed - strong evidence": 25,
        "Uncertain - manual review recommended": 20,
        "Uncertain - outreach recommended": 0,
        "Likely Closed - outreach recommended": 9,
        "No contact available": 0
      },
      "recorded_at": "2026-05-12T00:00:00Z",
      "note": "Phase 0 baseline — locked. Update only after explicit accuracy improvement. routing_distribution is informational in Phase 0; Phase 2 gates on drift."
    }
    ```
    The `accuracy`, `n_examples`, and `routing_distribution` values must come from the actual scorer output. If the run produces accuracy=0.87 with n_examples=42 and a different distribution, those become the baseline.

    Create or update `business_checker/eval/README.md`:
    ```markdown
    # Eval Harness

    ## How to run
    ```
    cd business_checker
    python -m business_checker.eval.score --gold eval/gold.json --out eval_result.json
    ```

    Output JSON shape (required by ANALYTICS-04 CI gate):
    ```json
    {
      "accuracy": 0.93,
      "n_examples": 124,
      "routing_distribution": {
        "Active - auto accepted": 70,
        "Likely Closed - strong evidence": 25,
        "Uncertain - manual review recommended": 20,
        "Uncertain - outreach recommended": 0,
        "Likely Closed - outreach recommended": 9,
        "No contact available": 0
      },
      "details": [...]
    }
    ```

    ## Baseline
    `eval/baseline.json` is the frozen accuracy floor. CI compares each run against it and
    fails if `accuracy < baseline.accuracy - 0.01`. Update only after intentional improvement.

    ## Pitfall P8 defense
    The CI gate also asserts `n_examples >= 20`. If you see CI fail with "gold set too small",
    do NOT shrink the threshold — investigate why the gold set is shorter than expected.

    ## Routing-label distribution (D-00-12)
    `routing_distribution` is informational in Phase 0 — the eval-CI workflow uploads it as
    an artifact but does NOT fail on drift. The 6-value `RoutingLabel` enum lives in
    `business_checker/eval/routing_labels.py` and is the single source of truth.
    Phase 2 will import the same enum for the production mapping function and add a
    distribution-drift gate on top of the existing accuracy gate.

    ## Adding gold examples
    See `manual_labels` table (Phase 3) for the canonical source. Currently the gold set
    lives in `eval/gold.json` and is hand-curated from the BMSG and Alabama VOB runs.
    ```
  </action>
  <verify>
    <automated>cd business_checker && python -m eval.score --help 2>&1 | head -20 || python eval/score.py --help 2>&1 | head -20; test -f business_checker/eval/routing_labels.py && python -c "from business_checker.eval.routing_labels import RoutingLabel, empty_distribution; assert len(list(RoutingLabel)) == 6; d = empty_distribution(); assert set(d.keys()) == {l.value for l in RoutingLabel}; print('routing OK')" && test -f business_checker/eval/baseline.json && python -c "import json; d=json.load(open('business_checker/eval/baseline.json')); assert 'accuracy' in d and 'n_examples' in d and d['n_examples'] >= 0; assert 'routing_distribution' in d and isinstance(d['routing_distribution'], dict) and len(d['routing_distribution']) == 6; print('OK', list(d.keys()))" && test -f business_checker/eval/README.md && grep -q "ANALYTICS-04" business_checker/eval/README.md && grep -q "n_examples >= 20" business_checker/eval/README.md && grep -q "routing_distribution\\|D-00-12" business_checker/eval/README.md</automated>
  </verify>
  <acceptance_criteria>
    - `python -m business_checker.eval.score --gold business_checker/eval/gold.json --out /tmp/test.json` exits 0 (after possible shim addition)
    - `/tmp/test.json` parses as JSON AND contains keys `accuracy` (float) AND `n_examples` (int) AND `routing_distribution` (dict with all 6 RoutingLabel keys)
    - `business_checker/eval/routing_labels.py` exists AND exports a `RoutingLabel` Enum with exactly the 6 string values listed in `.planning/2026-05-13-decision-triage-not-oracle.md`
    - `business_checker/eval/routing_labels.py` exports `stub_label_from_gold` (callable) AND `empty_distribution` (returns dict with all 6 keys zero)
    - `business_checker/eval/baseline.json` exists AND contains `accuracy` AND `n_examples` AND `routing_distribution` (dict with all 6 keys) AND `recorded_at`
    - `business_checker/eval/baseline.json` n_examples is ≥ 20 (Pitfall P8 floor) OR a gap note in `business_checker/eval/README.md` explains the path to ≥ 20 by Phase 2
    - `business_checker/eval/baseline.json` routing_distribution sums to exactly `n_examples` (sanity check — every gold example maps to exactly one bucket)
    - `business_checker/eval/README.md` documents the JSON output shape AND references ANALYTICS-04 AND Pitfall P8 AND mentions D-00-12 / routing distribution
    - No modifications to `business_checker/tools/` (engine is preserved per STATE.md)
  </acceptance_criteria>
  <done>Eval scorer emits standardized JSON; baseline.json frozen; CI has a stable contract to compare against.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: GitHub Actions eval-ci workflow</name>
  <files>.github/workflows/eval-ci.yml</files>
  <read_first>
    - .planning/phases/00-foundation/00-RESEARCH.md (Pattern 7 full YAML at lines 575-611)
    - scripts/eval-ci.sh (already created in Wave 0 — workflow delegates to it)
    - business_checker/eval/baseline.json (just created)
    - .github/workflows/codegen-drift.yml (Wave 2 — match conventions: actions/checkout@v4, setup-python@v5, etc.)
    - .planning/research/PITFALLS.md (P8 n_examples assertion at lines 184-196)
  </read_first>
  <action>
    Create `.github/workflows/eval-ci.yml`:
    ```yaml
    name: eval-ci
    on:
      pull_request:
        paths:
          - 'business_checker/eval/**'
          - 'business_checker/tools/**'
          - 'business_checker/pyproject.toml'
          - 'scripts/eval-ci.sh'
          - '.github/workflows/eval-ci.yml'
      push:
        branches: [main]
      workflow_dispatch:

    jobs:
      eval:
        runs-on: ubuntu-latest
        timeout-minutes: 20
        steps:
          - uses: actions/checkout@v4

          - uses: actions/setup-python@v5
            with:
              python-version: '3.12'
              cache: 'pip'

          - name: Install business_checker
            run: |
              pip install -e ./business_checker

          - name: Run eval (dry-run if no API key)
            env:
              PERPLEXITY_API_KEY_EVAL: ${{ secrets.PERPLEXITY_API_KEY_EVAL }}
              EVAL_GOLD: business_checker/eval/gold.json
              EVAL_BASELINE: business_checker/eval/baseline.json
            run: bash scripts/eval-ci.sh

          - name: Upload result artifact
            if: always()
            uses: actions/upload-artifact@v4
            with:
              name: eval-result
              path: eval_result.json
              if-no-files-found: warn

          - name: Surface failure context
            if: failure()
            run: |
              echo "::group::eval_result.json"
              cat eval_result.json 2>/dev/null || echo "no output"
              echo "::endgroup::"
              echo "::group::baseline.json"
              cat business_checker/eval/baseline.json
              echo "::endgroup::"
              echo "::error::Eval regression or gold-set size violation. See artifacts."
    ```
  </action>
  <verify>
    <automated>test -f .github/workflows/eval-ci.yml && python -c "import yaml; w=yaml.safe_load(open('.github/workflows/eval-ci.yml')); assert 'eval' in w['jobs']; assert any('bash scripts/eval-ci.sh' in str(s) for s in w['jobs']['eval']['steps']); print('OK')" && grep -q "PERPLEXITY_API_KEY_EVAL" .github/workflows/eval-ci.yml && grep -q "upload-artifact" .github/workflows/eval-ci.yml</automated>
  </verify>
  <acceptance_criteria>
    - `.github/workflows/eval-ci.yml` exists and is valid YAML
    - Workflow triggers on `pull_request`, `push` to main, `workflow_dispatch`
    - Workflow path filter includes `business_checker/eval/**` and `business_checker/tools/**`
    - Workflow invokes `bash scripts/eval-ci.sh` (delegates to Wave 0 script — single source of truth)
    - Workflow exposes `PERPLEXITY_API_KEY_EVAL` env var from secrets
    - Workflow uploads `eval_result.json` as an artifact (debugging)
    - Workflow surfaces baseline + result on failure via GitHub `::group::` annotations
    - `PERPLEXITY_API_KEY_EVAL` is documented as a required GitHub Actions secret (in the SUMMARY)
  </acceptance_criteria>
  <done>ANALYTICS-04 is structurally enforced; any PR that lowers eval accuracy fails CI.</done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 3: Create Resend account + file IVMF subdomain DNS ticket with IT (D-00-11 item 6)</name>
  <what-built>
    The architectural plan, schema, auth, codegen gate, worker, and eval gate are all live.
    The Phase 0 exit demo requires one human-only action: filing the IT ticket for Resend
    DNS records on the IVMF subdomain. This is the only Phase 0 step Claude cannot automate
    (per Pitfall research — IT-controlled DNS is path-critical for Phase 4 and must be filed
    at Phase 0 entry per STATE.md preconditions).
  </what-built>
  <how-to-verify>
    Complete these steps in order; record evidence in `.planning/phases/00-foundation/00-EVIDENCE.md`:

    1. **Create Resend account** (free tier, ~5 min):
       - Sign up at https://resend.com using a Corsico/IVMF email
       - Verify the account email
       - Note: keep the API key — Phase 4 will store it in `api_keys` table

    2. **Add the IVMF subdomain** in Resend dashboard:
       - Resend → Domains → Add Domain
       - Domain: the subdomain Jim/IT will provision (e.g., `outreach.ivmf.syr.edu` or whatever IT confirms)
       - Resend will display the exact DNS records required: SPF (1 TXT), DKIM (3 CNAMEs), DMARC (1 TXT)

    3. **File IT ticket** with these EXACT records:
       - Use the existing IVMF IT ticketing system (whatever Julian uses for ivmf.syr.edu tickets)
       - Subject: "Resend DNS records for [subdomain] — IVMF Business Checker v1.1"
       - Body: paste the SPF/DKIM/DMARC records VERBATIM from Resend dashboard
       - Reference: "Phase 0 exit gate per .planning/phases/00-foundation/00-CONTEXT.md D-00-11 item 6"
       - Note that propagation is non-blocking for Phase 0; the *ticket existing* is the deliverable.

    4. **Record evidence** in `.planning/phases/00-foundation/00-EVIDENCE.md`:
       - IT ticket ID (e.g., `IVMF-IT-####`)
       - Date filed (today)
       - Resend domain ID (if Resend displays one)
       - Screenshot or text copy of the records you requested

    5. **Update `.planning/STATE.md`** with the ticket ID under "Open Externally-Blocked Items".
  </how-to-verify>
  <resume-signal>
    Type "ticket filed: IVMF-IT-####" with the actual ticket ID, OR "ticket-blocker: <reason>" if you can't file it today (with a plan to revisit before Phase 4 starts).
  </resume-signal>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Finalize 00-EVIDENCE.md + update STATE.md + run phase0-demo.sh</name>
  <files>.planning/phases/00-foundation/00-EVIDENCE.md, .planning/STATE.md</files>
  <read_first>
    - .planning/phases/00-foundation/00-EVIDENCE.md (current state from Wave 2)
    - .planning/STATE.md (current state)
    - .planning/phases/00-foundation/00-CONTEXT.md (D-00-11 — 6 demo items)
    - scripts/phase0-demo.sh (Wave 0)
    - All SUMMARY.md files from waves 1-4
  </read_first>
  <action>
    First execute the automated portion of the Phase 0 demo and capture output:
    ```bash
    bash scripts/phase0-demo.sh 2>&1 | tee /tmp/phase0-demo.log
    ```
    The script confirms D-00-11 items 4 (append-only) and 5 (heartbeat). Item 1 (auth) requires a manual browser test.

    Open the demo-trip PR for D-00-11 item 2 (codegen drift gate).

    **CRITICAL — why a sed of the migration file alone will NOT trip the gate:**
    The drift workflow runs `drizzle-kit pull` against the LIVE dev DB (not the migration
    file). If we only edit the SQL file, the live DB still has `normalized_name`,
    `drizzle-kit pull` regenerates the existing schema.ts unchanged, the diff is empty,
    and CI passes green. To actually trip the gate we must mutate the LIVE dev DB so the
    introspection produces a smaller schema.ts than the committed one.

    Execute in this order:
    ```bash
    # 1. Alter the LIVE dev DB so introspection produces drift
    psql "$SUPABASE_DEV_DB_URL" -c "alter table public.businesses drop column normalized_name;"

    # 2. (Optional but recommended) Also edit the migration file so the PR diff shows
    #    intent to a reviewer. The CI doesn't read this — but a human PR reviewer will.
    git checkout -b demo/codegen-drift-trip
    sed -i.bak 's/  normalized_name text,//' supabase/migrations/0001_init_schema.sql
    rm -f supabase/migrations/0001_init_schema.sql.bak

    # 3. Push and open PR
    git add supabase/migrations/0001_init_schema.sql
    git commit -m "demo: intentionally drop normalized_name to trip drift gate"
    git push -u origin demo/codegen-drift-trip
    gh pr create --title "[DEMO] Trip codegen drift gate" \
      --body "Intentional column drop on dev DB + migration file to verify D-00-11 item 2. DO NOT MERGE. Will be closed after evidence captured. Restore script in task acceptance."
    ```

    Wait for the codegen-drift workflow to fail. The failure mode: `drizzle-kit pull`
    regenerates `web/db/schema.ts` WITHOUT `normalized_name`; the script then runs
    `git diff --exit-code -- web/db/schema.ts` which exits non-zero. Capture:
    - the failing run URL (`gh run list --workflow codegen-drift.yml --limit 1 --json url`)
    - a screenshot of the failing GitHub check (for 00-EVIDENCE.md)

    **Restore the live dev DB schema** (the migration file is non-idempotent — re-running
    0001 would fail on `create table public.businesses`; do a targeted ALTER instead):
    ```bash
    # Restore the column on the live dev DB
    psql "$SUPABASE_DEV_DB_URL" -c "alter table public.businesses add column normalized_name text;"
    # Verify column is back
    psql "$SUPABASE_DEV_DB_URL" -tAc \
      "select 1 from information_schema.columns where table_schema='public' and table_name='businesses' and column_name='normalized_name'"
    # Returns: 1

    # Close the PR (do NOT merge) and delete the local branch
    gh pr close demo/codegen-drift-trip --comment "Evidence captured; restoring."
    git checkout main
    git branch -D demo/codegen-drift-trip
    git push origin --delete demo/codegen-drift-trip
    ```

    TODO (deferred to Phase 0 polish PR — see plan 02 same TODO): make
    `supabase/migrations/0001_init_schema.sql` idempotent (`create table if not exists ...`)
    so future demo runs can use `psql -f 0001_init_schema.sql` to restore. For now, the
    targeted ALTER is the correct restore step.

    Open the demo-trip PR for D-00-11 item 3 (eval regression gate):
    ```bash
    git checkout -b demo/eval-regression-trip
    # Flip an expected label in gold.json to lower measured accuracy
    python -c "
    import json
    p = 'business_checker/eval/gold.json'
    g = json.load(open(p))
    if isinstance(g, list) and g:
        # Flip the first example's expected_status
        g[0]['expected_status'] = 'closed' if g[0].get('expected_status') == 'active' else 'active'
        json.dump(g, open(p, 'w'), indent=2)
        print('Flipped:', g[0])
    "
    git add business_checker/eval/gold.json
    git commit -m "demo: flip gold-set label to trip eval gate"
    git push -u origin demo/eval-regression-trip
    gh pr create --title "[DEMO] Trip eval regression gate" --body "Intentional label flip to verify D-00-11 item 3."
    ```
    Wait for the eval-ci workflow to fail (the assertion `accuracy >= baseline - 0.01` should fire). Capture URL + screenshot. Close PR without merging. Restore gold.json (git checkout).

    Now finalize `.planning/phases/00-foundation/00-EVIDENCE.md` — replace the Wave 2 template with completed entries:
    ```markdown
    # Phase 0 — Evidence Log

    Phase 0 exit demo (D-00-11) artifacts. Each item must be checked before declaring Phase 0 complete.

    ## D-00-11 Item 1 — Magic-link login + middleware allowlist
    - [x] `@syr.edu` magic-link round-trip succeeded — see screenshot/Loom: `<path or URL>`
    - [x] `@gmail.com` 403 confirmed — text response: "Sign-in restricted to allowed domains: syr.edu..."
    - **Verified:** 2026-MM-DD by Julian Hernandez (manual browser walkthrough)

    ## D-00-11 Item 2 — Codegen drift PR fails CI
    - [x] Demo PR: `<gh pr url>`
    - [x] Failing codegen-drift workflow run: `<run url>`
    - [x] PR closed without merging on YYYY-MM-DD

    ## D-00-11 Item 3 — Eval-CI regression PR fails CI
    - [x] Demo PR: `<gh pr url>`
    - [x] Failing eval-ci workflow run: `<run url>`
    - [x] PR closed without merging on YYYY-MM-DD

    ## D-00-11 Item 4 — verifications append-only
    - [x] `bash scripts/phase0-demo.sh` output showing P0001 on UPDATE attempt:
      ```
      <paste relevant lines from /tmp/phase0-demo.log>
      ```

    ## D-00-11 Item 5 — Worker heartbeat row
    - [x] psql query result showing recent heartbeat:
      ```
      <paste output of: psql "$SUPABASE_DEV_DB_URL" -c "select * from worker_heartbeats">
      ```

    ## D-00-11 Item 6 — Resend DNS ticket
    - [x] IT ticket ID: `IVMF-IT-####`  (from Task 3)
    - [x] Date filed: YYYY-MM-DD
    - [x] Resend dashboard domain: `<subdomain>`
    - [x] Records requested: SPF (1 TXT), DKIM (3 CNAMEs), DMARC (1 TXT)
    ```

    Update `.planning/STATE.md` — change Phase 0 status:
    - Set current Phase to "Phase 1 — Cache-Only Verification (next)"
    - Mark Phase 0 as complete in Progress block: `- [x] Phase 0: Foundation`
    - Add ticket ID under "Open Externally-Blocked Items" → "Resend DNS ticket IVMF-IT-####" with file date
    - Append a line to Session Continuity: "Phase 0 complete YYYY-MM-DD. Next: `/gsd:plan-phase 1`"
  </action>
  <verify>
    <automated>test -f .planning/phases/00-foundation/00-EVIDENCE.md && ! grep -c "_pending_" .planning/phases/00-foundation/00-EVIDENCE.md | awk '{exit ($1 > 0)}' && grep -c "\\[x\\]" .planning/phases/00-foundation/00-EVIDENCE.md | awk '{exit ($1 < 6)}' && grep -q "IVMF-IT\\|ticket-blocker" .planning/phases/00-foundation/00-EVIDENCE.md && grep -q "Phase 0: Foundation" .planning/STATE.md && grep -q "\\[x\\] Phase 0" .planning/STATE.md</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/phases/00-foundation/00-EVIDENCE.md` has ALL 6 D-00-11 items marked `[x]`
    - Each item has concrete evidence: PR URL, workflow run URL, psql output, or ticket ID (no `_pending_` placeholders remain)
    - The two demo PRs (codegen-drift, eval-regression) were opened, failed CI as expected, and closed without merging
    - The dev Supabase project's schema is restored after the demo PRs (normalized_name column present; gold.json original labels restored)
    - `.planning/STATE.md` marks Phase 0 complete in the Progress section
    - `.planning/STATE.md` Session Continuity line points to `/gsd:plan-phase 1` as next action
    - `bash scripts/phase0-demo.sh` exits 0 against the dev DB
    - If Task 3 was blocked (ticket couldn't be filed today), the evidence log marks item 6 with the blocker reason AND there's a documented follow-up date before Phase 4 starts
  </acceptance_criteria>
  <done>Phase 0 is officially complete. All 6 D-00-11 demo items have evidence. STATE.md is updated. Next phase is teed up.</done>
</task>

</tasks>

<verification>
- ANALYTICS-04 verified: a PR that intentionally regresses accuracy fails CI (demonstrated in Task 4).
- All 6 D-00-11 items have concrete evidence in 00-EVIDENCE.md.
- STATE.md reflects Phase 0 complete; Phase 1 is the next target.
- `make demo` (calls scripts/phase0-demo.sh) exits 0.
- `make eval` runs locally and matches the CI baseline.
</verification>

<success_criteria>
1. eval-ci workflow exists and blocks accuracy regressions below baseline.
2. n_examples >= 20 floor is enforced (Pitfall P8 closed).
3. Resend account exists; IT ticket filed with exact DNS records; ticket ID in STATE.md.
4. Phase 0 exit demo (D-00-11) is fully evidenced.
5. Phase 0 is closed; Phase 1 is the next planning target.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-06-eval-ci-demo-SUMMARY.md` documenting:
- Eval scorer output shape (was it already standard, or was a shim added?)
- Baseline accuracy, n_examples, and routing_distribution values
- Routing-label surface: confirmation that `business_checker/eval/routing_labels.py` exports the 6-value enum and that Phase 2 can import it unchanged
- Resend ticket ID + date filed (or blocker reason)
- Demo PR URLs (codegen-drift, eval-regression) — both closed without merging
- Requirements closed: ANALYTICS-04
- D-00-12 measurement surface live (informational; Phase 2 adds the gate)
- Phase 0 fully closed; STATE.md updated; recommend `/clear` then `/gsd:plan-phase 1`
</output>
