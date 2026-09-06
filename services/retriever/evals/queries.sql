-- Error analysis (eval phase 3) — the weekly read.
--
-- Paste into the Supabase SQL editor. The point of this file is that reading
-- the corpus is five minutes on a Monday, not a project: the phase-2 explain
-- doc argues that a corpus nobody reads is just storage cost, and the harness
-- (phase 4) is only worth building once these queries have produced a list of
-- named failure modes. The judge rubric comes from that list. It is not
-- written in advance.
--
-- Three tables, one key. The gateway writes conversation_logs (the request,
-- with the full client-sent history — chat is stateless, so the payload is a
-- complete snapshot of the turn). The retriever writes eval_records (the
-- answer). The gateway writes turn_feedback (the label). All three carry
-- request_id.
--
-- Schemas: supabase/migrations/20260813000006_conversation_logs.sql,
-- 20260826000018_eval_records.sql, 20260826000019_turn_feedback.sql.
-- Background: docs/explain/eval-phases-0-1.html §5, docs/explain/eval-phase-2.html.
--
-- ⚠ turn_feedback.rating arrives with migration 20260827000021, which was
--   unapplied as of 2026-09-01. Until it lands, drop the `rating` predicates:
--   every row written before that column existed was a down, which is exactly
--   what its `default 'down'` encodes. Queries 1 and 4 say where.


-- ── 1 · The complaint queue ─────────────────────────────────────────────────
-- Every thumbs-down with the conversation that led to it and the answer it
-- got. This is the one to read weekly; the rest are for when it looks thin.
-- A down posts immediately with a null reason and an optional typed reason
-- arrives as a second row for the same request_id, hence the max().
-- Pre-migration-21: delete the `where f.rating = 'down'` line.

select f.created_at,
       max(f.reason)                        as reason,
       c.payload -> 'messages'              as conversation,
       e.query_type,
       e.moment,
       e.final_text,
       e.row_count,
       e.cyphers,
       e.errors,
       e.latency_ms,
       c.duration_ms - e.latency_ms         as edge_overhead_ms
from turn_feedback f
join eval_records e using (request_id)
left join conversation_logs c on c.request_id = f.request_id
where f.rating = 'down'
group by f.request_id, f.created_at, c.payload, e.query_type, e.moment,
         e.final_text, e.row_count, e.cyphers, e.errors, e.latency_ms,
         c.duration_ms
order by f.created_at desc
limit 100;


-- ── 2 · Failures nobody complained about ────────────────────────────────────
-- The pipeline recorded an error and the user did not thumb it down — either
-- they did not notice, or they left. Feedback is a biased sample of failure;
-- this is the unbiased half, and it needs no labels to be worth reading.

select e.created_at,
       e.query_type,
       e.errors,
       e.row_count,
       e.latency_ms,
       left(e.final_text, 160) as answer_head,
       c.payload -> 'messages' as conversation
from eval_records e
left join conversation_logs c on c.request_id = e.request_id
where array_length(e.errors, 1) > 0
order by e.created_at desc
limit 100;


-- ── 3 · Empty-handed turns ──────────────────────────────────────────────────
-- No error, no cards: the pipeline worked and found nothing. For a discovery
-- product this is the failure mode that matters most, because it is usually
-- about supply — a city with no events, a genre nobody tagged — rather than
-- about the model. Read the questions, not the answers: they are a shopping
-- list for the sweep.

select e.created_at,
       e.query_type,
       e.moment,
       e.cyphers,
       c.payload -> 'messages' -> -1 ->> 'content' as last_user_message
from eval_records e
left join conversation_logs c on c.request_id = e.request_id
where coalesce(e.row_count, 0) = 0
  and coalesce(array_length(e.errors, 1), 0) = 0
order by e.created_at desc
limit 100;


-- ── 4 · Weekly pulse ────────────────────────────────────────────────────────
-- One row. Is it getting worse? Run it before reading anything else — if
-- these numbers have not moved, the ten minutes are better spent elsewhere.
-- Pre-migration-21: replace both rating filters with `true` and `false`.

select date_trunc('week', e.created_at)                             as week,
       count(*)                                                     as turns,
       count(*) filter (where array_length(e.errors, 1) > 0)         as error_turns,
       count(*) filter (where coalesce(e.row_count, 0) = 0)          as empty_turns,
       count(distinct f.request_id) filter (where f.rating = 'down') as downs,
       count(distinct f.request_id) filter (where f.rating = 'up')   as ups,
       percentile_disc(0.5) within group (order by e.latency_ms)     as p50_ms,
       percentile_disc(0.95) within group (order by e.latency_ms)    as p95_ms
from eval_records e
left join turn_feedback f on f.request_id = e.request_id
group by 1
order by 1 desc;


-- ── 5 · Slowest turns ───────────────────────────────────────────────────────
-- Latency by shape, worst first. query_type and the generated Cypher together
-- usually say whether a slow turn is the model thinking or the graph scanning.

select e.created_at,
       e.query_type,
       e.latency_ms,
       c.duration_ms - e.latency_ms as edge_overhead_ms,
       e.row_count,
       e.cyphers
from eval_records e
left join conversation_logs c on c.request_id = e.request_id
where e.latency_ms is not null
order by e.latency_ms desc
limit 50;
