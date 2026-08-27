-- Telemetry retention: conversation_logs and eval_records hold user-derived
-- text (full chat histories, answers) with no TTL until now. Nightly, prune
-- rows older than 90 days — unless the turn was thumbed down: a turn_feedback
-- row marks a labeled turn, and the labeled corpus is the point of keeping
-- any of this, so those rows are kept indefinitely. turn_feedback itself is
-- never pruned (a few rows per human complaint; it stays small).
--
-- pg_cron so the schedule lives in the database: flows/serve.py is not
-- running, and neither the gateway nor the retriever should carry a janitor.
-- Both tables already have a created_at desc index, so the age scan is cheap.
--
-- Numbering note: this takes 20, so phase G's review-signal columns (which
-- 19 pointed at 20) move to 21.

create extension if not exists pg_cron;

select cron.schedule(
    'retention-conversation-logs',
    '45 4 * * *',
    $$
  delete from public.conversation_logs c
   where c.created_at < now() - interval '90 days'
     and not exists (
       select 1 from public.turn_feedback f where f.request_id = c.request_id
     )
    $$
);

select cron.schedule(
    'retention-eval-records',
    '50 4 * * *',
    $$
  delete from public.eval_records e
   where e.created_at < now() - interval '90 days'
     and not exists (
       select 1 from public.turn_feedback f where f.request_id = e.request_id
     )
    $$
);
