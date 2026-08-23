-- What discovery has learned about where to look and how to ask (Phase D).
--
-- Two things are learned from the same signal — whether a page yielded real,
-- future, not-already-known events — and both feed the next sweep: which
-- domains to steer Tavily toward or away from, and which phrasings are worth
-- spending a credit on. Written only by the search service with the service
-- role: RLS on with no user policies, like conversation_logs and
-- search_reports.
--
-- The counters decay rather than accumulate (see the `decay` note on each
-- table). A three-week festival otherwise earns a permanent promotion on one
-- month's evidence, and a site that has since gone quiet keeps its rank
-- forever. Decay is applied by the writer, not here.

create table public.search_sources (
    domain text primary key,
    -- Decayed counters: every value is (previous * decay) + observed.
    pages real not null default 0,
    pages_with_events real not null default 0,
    drafts real not null default 0,
    candidates_new real not null default 0,
    -- Written at approve time, so it survives even if the report is deleted.
    events_written real not null default 0,
    -- Tavily's own relevance score, averaged over the pages it returned.
    mean_score real not null default 0,
    status text not null default 'candidate'
    check (status in ('candidate', 'trusted', 'blocked')),
    -- Per-site instructions appended to the extraction prompt. Owner-authored:
    -- the table holds the text and the prompt consumes it, but nothing
    -- generates it yet.
    extraction_hints text not null default '',
    hints_updated_at timestamptz,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);

-- The ranking read: trusted first, then whatever has yielded most.
create index search_sources_rank_idx on public.search_sources (status, candidates_new desc);

alter table public.search_sources enable row level security;

-- Query phrasings, scored the same way. A sweep spends most of its credits on
-- the phrasings that have earned it and reserves one slot for a trial, so the
-- vocabulary keeps growing instead of ossifying around whatever was written
-- into the file first.
create table public.search_queries (
    -- The template itself, with its {city} and {month_year} slots.
    template text primary key,
    status text not null default 'trial'
    check (status in ('trial', 'standing', 'retired')),
    -- Runs is a plain count, not decayed: it is how much evidence there is,
    -- and evidence does not expire the way relevance does.
    runs integer not null default 0,
    -- Decayed, like the source counters above.
    pages real not null default 0,
    pages_with_events real not null default 0,
    candidates_new real not null default 0,
    -- Share of returned pages on a domain in the sweep's own country. The
    -- English templates scored 2-3 of 9 here against 7 of 9 for the Italian
    -- ones, which is the measurement that removed them.
    local_domain_share real not null default 0,
    first_seen_at timestamptz not null default now(),
    last_used_at timestamptz
);

create index search_queries_rank_idx on public.search_queries (status, candidates_new desc);

alter table public.search_queries enable row level security;
