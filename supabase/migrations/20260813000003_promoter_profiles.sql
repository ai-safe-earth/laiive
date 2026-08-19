-- Promoter (pro) signup data per D8: what they manage/own, collected at
-- registration. Free-form jsonb arrays — the graph is the source of truth
-- for the entities themselves; ownership links live in public.ownerships.

create table public.promoter_profiles (
    user_id uuid primary key references auth.users (id) on delete cascade,
    org_name text not null,
    website text,
    phone text,
    managed_venues jsonb not null default '[]'::jsonb,
    managed_artists jsonb not null default '[]'::jsonb,
    managed_events jsonb not null default '[]'::jsonb,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.promoter_profiles enable row level security;

create policy "pros read own promoter profile"
on public.promoter_profiles for select
using (auth.uid() = user_id);

create policy "pros insert own promoter profile"
on public.promoter_profiles for insert
with check (auth.uid() = user_id);

create policy "pros update own promoter profile"
on public.promoter_profiles for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);
