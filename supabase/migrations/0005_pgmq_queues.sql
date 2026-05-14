-- Phase 0 / Plan 02 — pgmq queue creation (D-00-09).
-- The pgmq extension is enabled via Supabase Dashboard → Database → Extensions → pgmq
-- (Supabase Queues GA). This migration only creates the two queues.
--
-- NOTE: vt (visibility timeout) is configured at the consumer call site per-read,
-- NOT at queue create time. pgmq.create() does NOT accept a vt argument in
-- tembo-pgmq-python 0.10. Worker uses read_with_poll(queue, vt=300, qty=1,
-- max_poll_seconds=20) — see worker/workers/lib/pgmq_client.py (Plan 00-05).

select pgmq.create('q_verify');
select pgmq.create('q_aggregator');
