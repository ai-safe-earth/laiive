-- Sweep reports for the SEARCH service (Phase 5): each dry-run persists its
-- candidates + dedup verdicts here so approve replays from the stored report
-- and reports outlive a restart. Written only by the search service with the
-- service role — RLS on with no user policies, like conversation_logs.

create table public.search_reports (
    id uuid primary key default gen_random_uuid(),
    city text not null,
    status text not null default 'dry_run'
    check (status in ('dry_run', 'approved')),
    candidates jsonb not null default '[]'::jsonb,
    stats jsonb not null default '{}'::jsonb,
    write_results jsonb,
    approved_by uuid,
    approved_at timestamptz,
    created_at timestamptz not null default now()
);

create index search_reports_created_idx on public.search_reports (created_at desc);
create index search_reports_city_idx on public.search_reports (city, created_at desc);

alter table public.search_reports enable row level security;
