-- The write verdict: what the pusher actually did to the graph, per attempt.
--
-- The retriever has had an answer-side record since eval phase 0; the pusher
-- has had nothing, which is backwards from risk — a bad answer is ephemeral, a
-- bad write is a row every future retriever turn reads. The failure mode the
-- dedup corpus was born from (services/pusher/evals/dedup_review.csv: under 52
-- realistic cases today's code silently duplicates in 21) is by construction
-- invisible in production, because nothing records that a near-duplicate was
-- created. "21 of 52" is a hand-derivation. This table makes it a measurement.
--
-- Written fire-and-forget by the pusher with the service role, joined to the
-- gateway's conversation_logs on request_id — which only became possible in the
-- same change, since the pusher used to mint its own id. Same posture as
-- eval_records: RLS on with no policies = service-role only.
--
-- One table for creates and edits rather than two: the interesting column is
-- the verdict and both paths produce one, from vocabularies that are already
-- Literals in laiive_shared/neo4j_writer.py (WriteResult.status,
-- UpdateResult.status). Nothing is invented here.
--
-- Deliberately absent: a near-match column. The writer's dedup probe does not
-- surface what it matched against (WriteResult carries no candidate), so a
-- column for it would never be filled. It is the natural second step once
-- multi-signal dedup exists — roadmap Phase 4.

create table public.push_records (
    id bigint generated always as identity primary key,
    request_id text not null,
    -- The gateway-verified X-User-Id, so an anonymous or internal write is null
    -- rather than a lie.
    user_id uuid,
    kind text not null check (kind in ('create', 'edit')),
    entity_type text not null check (entity_type in ('event', 'venue', 'artist')),
    -- WriteResult.status | UpdateResult.status, unconstrained on purpose: the
    -- vocabulary lives in the writer's Literals, and a new verdict there should
    -- show up here as data rather than as a failed insert. Same reasoning as
    -- eval_records' loose query_type.
    writer_verdict text not null,
    entity_uid text,
    entity_name text,
    venue_uid text,
    venue_created boolean,
    artist_uids_created text[],  -- noqa: LT01
    -- The submitted draft (creates) or the writer's own field delta (edits).
    -- The delta is the writer's reading of the node, not the caller's claim.
    draft jsonb,
    changed jsonb,
    warnings text[],  -- noqa: LT01
    message text,
    latency_ms integer,
    created_at timestamptz not null default now()
);

create index push_records_request_idx on public.push_records (request_id);
create index push_records_created_idx on public.push_records (created_at desc);
-- The read that matters: every attempt that was not a clean create, newest
-- first. Partial, because the successes are the bulk and never the question.
create index push_records_verdict_idx on public.push_records (writer_verdict, created_at desc)
where writer_verdict not in ('created', 'updated');

alter table public.push_records enable row level security;

-- Retention, mirroring 20260827000020 but with the pusher's own notion of a
-- labelled row. There is no thumbs control on the publish chat, so the label
-- here is the verdict itself: a clean create or update is the boring case and
-- prunes at 90 days, while duplicate / adopted / invalid / error / not_found
-- are the corpus the dedup work is built from and are kept. Those are rare, so
-- the kept set stays small — the inverse of the retriever, where the kept set
-- is rare because humans rarely complain.
select cron.schedule(
    'retention-push-records',
    '55 4 * * *',
    $$
  delete from public.push_records
   where created_at < now() - interval '90 days'
     and writer_verdict in ('created', 'updated')
    $$
);
