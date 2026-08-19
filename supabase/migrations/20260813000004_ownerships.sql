-- Ownership of graph entities (venues/artists/events live in Neo4j and carry
-- owner_id; this table is the authoritative, RLS-protected registry).
-- Shared: several rows may point at the same entity. Transferable: insert the
-- new owner's row, delete the old one (service role / admin tooling).

create table public.ownerships (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users (id) on delete cascade,
    entity_type text not null check (entity_type in ('venue', 'artist', 'event')),
    entity_uid text not null,
    granted_by uuid references auth.users (id),
    created_at timestamptz not null default now(),
    unique (owner_id, entity_type, entity_uid)
);

create index ownerships_entity_idx on public.ownerships (entity_type, entity_uid);
create index ownerships_owner_idx on public.ownerships (owner_id);

alter table public.ownerships enable row level security;

create policy "owners read own ownerships"
on public.ownerships for select
using (auth.uid() = owner_id);

-- grants/transfers go through the service role, not end users
