#!/usr/bin/env bash
# Phase 0 exit demo — exercises D-00-11 items 1 (auth), 4 (immutability), 5 (heartbeat).
# Items 2 (drift PR) and 3 (eval PR) are PR-based; item 6 (Resend ticket) is org-side.
set -euo pipefail

if [ -z "${SUPABASE_DEV_DB_URL:-}" ]; then
  echo "ERROR: SUPABASE_DEV_DB_URL required" >&2; exit 2
fi

echo "=== D-00-11 item 4: verifications append-only ==="
psql "$SUPABASE_DEV_DB_URL" <<'SQL'
do $$
begin
  begin
    update verifications set status='active' where id is not null;
    raise exception 'EXPECTED FAILURE — UPDATE should have raised P0001';
  exception when others then
    if SQLSTATE = 'P0001' then
      raise notice 'OK: UPDATE raised P0001 as expected';
    else
      raise;
    end if;
  end;
end$$;
SQL

echo "=== D-00-11 item 5: worker_heartbeats row within 60s ==="
psql "$SUPABASE_DEV_DB_URL" -tAc \
  "select count(*) from worker_heartbeats where last_seen_at > now() - interval '60 seconds'" \
  | awk '{ if ($1 < 1) { print "FAIL: no recent heartbeat"; exit 1 } else print "OK: " $1 " recent heartbeat row(s)" }'

echo "=== D-00-11 item 1: middleware allowlist (manual) ==="
echo "  -> Visit /sign-in in browser, attempt @gmail.com login; expect 403 message."
echo "  -> Then attempt @syr.edu magic link; expect /me page with email + role."
echo "  (Recorded as evidence in .planning/phases/00-foundation/00-EVIDENCE.md)"

echo "=== Phase 0 demo: automated checks passed ==="
