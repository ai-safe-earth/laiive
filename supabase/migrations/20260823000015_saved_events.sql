-- Saved events: the uid of an event somebody put aside, and nothing else.
--
-- Deliberately not a copy of the card. A saved list is a list of pointers into
-- the graph, and the graph is what an event actually is: a price corrected
-- after a promoter claims a listing, a door time moved, a venue whose pin the
-- repair sweep fixed. All of that has to reach a saved card. A snapshot taken
-- at save time would freeze whichever version happened to be on screen, and
-- nothing here could tell a stale row from a current one. The bodies are
-- re-read from Aura on every open, through the retriever's /events lookup.
--
-- No foreign key on event_uid: that entity lives in Neo4j, not in Postgres. An
-- event deleted from the graph leaves a row that resolves to no card and the
-- list simply does not show it -- the same outcome a cascade would give, with
-- one fewer invariant spanning two databases.
--
-- Read and written straight from the browser under RLS, like profiles. The
-- reasoning is at the top of frontend/src/api/profile.ts and it is unchanged
-- here: "a user may touch only their own rows" is one policy at the point of
-- truth, and restating it in a gateway holding the service-role key turns a
-- typo into a leak of everyone's list instead of nobody's.

create table public.saved_events (
    user_id uuid not null references auth.users (id) on delete cascade,
    event_uid text not null check (length(trim(event_uid)) > 0),
    saved_at timestamptz not null default now(),
    primary key (user_id, event_uid)
);

-- The one read this table has: my list, newest first. The primary key already
-- covers the user_id prefix; this index exists for the ordering.
create index saved_events_user_idx on public.saved_events (user_id, saved_at desc);

alter table public.saved_events enable row level security;

create policy "users read own saved events"
on public.saved_events for select
using (auth.uid() = user_id);

create policy "users save events for themselves"
on public.saved_events for insert
with check (auth.uid() = user_id);

create policy "users unsave their own events"
on public.saved_events for delete
using (auth.uid() = user_id);

-- No update policy on purpose: the row is (who, what, when it was put aside)
-- and none of the three is editable. Unsaving is a delete, and re-saving
-- writes a fresh saved_at, which is the truth about when it was put aside.
-- The revoke is belt and braces -- RLS already refuses an update with no
-- policy -- and follows 20260814000008, which put column authority in grants.
revoke update on public.saved_events from authenticated;
