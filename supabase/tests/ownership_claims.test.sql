-- Behaviour check for 20260827000022_ownership_claims.sql.
--
-- Not a framework, and not wired into CI: there is no pgTAP here and this
-- migration did not justify introducing one. It is one file you can run when
-- the authorization logic changes, because "it applied" is not the same claim
-- as "it refuses the right people", and user_may_edit decides who may rewrite
-- somebody else's venue.
--
-- Run it (Docker, ~20s, touches nothing outside the container):
--
--   docker run --rm -d --name laiive-mig-test -e POSTGRES_PASSWORD=x postgres:16-alpine
--   docker exec -i laiive-mig-test psql -U postgres -v ON_ERROR_STOP=1 -q \
--     < supabase/tests/ownership_claims.test.sql
--   docker rm -f laiive-mig-test
--
-- It stubs the Supabase surface the migrations expect (auth.users, auth.uid,
-- the three roles), replays 20260819000011 verbatim so the constraint name
-- dropped below is the real one, then applies 22 and exercises it. Every
-- PASS/FAIL is a raise notice; a failure aborts under ON_ERROR_STOP=1.
--
-- Last run 2026-09-01: all nine checks passed.

\set ON_ERROR_STOP on
\echo '=== stubbing the Supabase surface ==='
-- Minimum Supabase surface the two dependency migrations touch, so the real
-- migration files can be replayed unedited against a plain Postgres.
create schema if not exists auth;

create table auth.users (id uuid primary key);

create function auth.uid() returns uuid
language sql stable as $$ select null::uuid $$;

do $$
begin
  execute 'create role anon';
  execute 'create role authenticated';
  execute 'create role service_role';
exception when duplicate_object then null;
end $$;

-- Superseded by entity_ownership; 20260819000011 drops it at the end.
create table public.ownerships (id bigint generated always as identity primary key);

-- Only referenced by a `comment on table` in 20260819000011.
create table public.promoter_profiles (
    user_id uuid primary key references auth.users (id)
);

-- Copied verbatim from 20260813000002_user_roles.sql, which cannot be replayed
-- here: it hangs a trigger off handle_new_user() from an earlier migration.
-- These two objects are all 20260827000022 needs from it.
create type public.app_role as enum ('user', 'pro', 'admin');

create table public.user_roles (
    user_id uuid primary key references auth.users (id) on delete cascade,
    role public.app_role not null default 'user',
    granted_by uuid references auth.users (id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

\echo '=== replaying 20260819000011_organizations.sql ==='
-- Organizations: the thing that owns a venue, an artist or an event.
--
-- Until now a pro account owned entities personally: `owner_id` on the graph
-- node, stamped ON CREATE, first writer wins. That cannot express a venue with
-- three staff, a booker who leaves, or a collective. The unit becomes an
-- organization, people are members of it with a role, and the owner invites
-- the rest — the shape Eventbrite settled on, and the one the owner asked for.
--
-- Two design decisions this encodes, both the owner's (docs/roadmap/02-ownership.md):
--
--  * Claims are self-declared for now. Claiming a venue that already exists in
--    the graph succeeds immediately with verified = false. Verification is a
--    later review step, not a gate on onboarding: city-scale supply matters
--    more than gatekeeping at this stage.
--  * Listing at a venue is NOT restricted. Anyone with a pro account can
--    publish an event anywhere; the venue is an address, not a permission.
--    So ownership governs who may EDIT a record, never who may create one.
--
-- Nothing enforces any of this yet, because there is nothing to enforce: the
-- pusher is create-only, with no update or delete endpoint. What lands here is
-- the record — every publish writes who owns the result — so that the edit
-- endpoints and the "your events" screens have an authority to consult when
-- they arrive.
--
-- Supersedes public.ownerships (dropped below: zero rows, read by no code).
-- public.promoter_profiles survives for now because the account page still
-- reads it; it goes when the pro screens are rebuilt.

create type public.org_kind as enum ('venue', 'artist', 'promoter');
create type public.org_role as enum ('owner', 'admin', 'member');
create type public.ownership_basis as enum ('created', 'claimed');

create table public.organizations (
    id uuid primary key default gen_random_uuid(),
    kind public.org_kind not null,
    display_name text not null check (length(trim(display_name)) > 0),
    -- Doubles as verification evidence when a claim is reviewed: a working
    -- site and a listed phone are what a reviewer actually checks.
    website text,
    phone text,
    contact_email text,
    created_by uuid not null references auth.users (id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.organization_members (
    org_id uuid not null references public.organizations (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    role public.org_role not null default 'member',
    created_at timestamptz not null default now(),
    primary key (org_id, user_id)
);

create index organization_members_user_idx on public.organization_members (user_id);

-- Invitations carry a hash, never the token: the token exists only in the link
-- that goes out by email, so a leaked table row cannot be redeemed.
create table public.organization_invitations (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations (id) on delete cascade,
    email text not null check (position('@' in email) > 1),
    role public.org_role not null default 'member',
    token_hash text not null,
    invited_by uuid not null references auth.users (id),
    expires_at timestamptz not null default now() + interval '14 days',
    accepted_at timestamptz,
    accepted_by uuid references auth.users (id),
    created_at timestamptz not null default now()
);

-- One live invitation per address per org; accepted ones are kept as history.
create unique index organization_invitations_pending_idx
on public.organization_invitations (org_id, lower(email))
where accepted_at is null;

create index organization_invitations_token_idx on public.organization_invitations (token_hash);

-- The graph is the source of truth for entities themselves; this says which
-- organization stands behind one. Deliberately NOT unique per entity: a venue
-- and its resident promoter can both hold a claim on the same room, which is
-- how the real world works.
create table public.entity_ownership (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references public.organizations (id) on delete cascade,
    entity_type text not null check (entity_type in ('venue', 'artist', 'event')),
    entity_uid text not null,
    -- 'created' needs no verification — you made the thing. 'claimed' is a
    -- statement about an entity that already existed, and starts unverified.
    basis public.ownership_basis not null,
    verified boolean not null default false,
    claimed_by uuid references auth.users (id),
    evidence jsonb not null default '{}'::jsonb,
    reviewed_by uuid references auth.users (id),
    reviewed_at timestamptz,
    created_at timestamptz not null default now(),
    unique (org_id, entity_type, entity_uid),
    constraint created_is_verified check (basis <> 'created' or verified)
);

create index entity_ownership_entity_idx on public.entity_ownership (entity_type, entity_uid);
create index entity_ownership_org_idx on public.entity_ownership (org_id);

-- ---------------------------------------------------------------------------
-- Membership helpers.
--
-- SECURITY DEFINER because the policies below query organization_members from
-- inside organization_members' own policy, which recurses. A definer function
-- reads the table without re-entering RLS and breaks the cycle. `authenticated`
-- keeps EXECUTE — see the grants at the end for why it has to.
-- ---------------------------------------------------------------------------

create function public.is_org_member(org uuid, uid uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.organization_members m
    where m.org_id = org and m.user_id = uid
  );
$$;

create function public.is_org_admin(org uuid, uid uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.organization_members m
    where m.org_id = org and m.user_id = uid and m.role in ('owner', 'admin')
  );
$$;

-- Also a definer, and for a sharper reason than convenience. The founder policy
-- below has to know whether ANY member row exists. Asking that inline would ask
-- it through RLS, which only shows rows the caller is already a member of — so
-- a stranger would see zero rows in a fully staffed organization and conclude it
-- was empty. That is not a subtle failure: it would let anyone insert themselves
-- as owner of someone else's venue.
create function public.org_has_no_members(org uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select not exists (
    select 1 from public.organization_members m where m.org_id = org
  );
$$;

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.organization_invitations enable row level security;
alter table public.entity_ownership enable row level security;

create policy "members read their organizations"
on public.organizations for select
using (public.is_org_member(id, auth.uid()));

-- Anyone with an account may found an organization; being its creator is not
-- yet membership, so the insert is paired with a member row by the caller.
create policy "users create organizations"
on public.organizations for insert
with check (auth.uid() = created_by);

create policy "admins update their organization"
on public.organizations for update
using (public.is_org_admin(id, auth.uid()))
with check (public.is_org_admin(id, auth.uid()));

create policy "members read the roster"
on public.organization_members for select
using (public.is_org_member(org_id, auth.uid()));

-- The founder's own owner row, and nothing else: everything after that is an
-- invitation, which the service role redeems. Without this the creator could
-- never become a member of the organization they just made.
create policy "founder takes the owner seat"
on public.organization_members for insert
with check (
    auth.uid() = user_id
    and role = 'owner'
    and public.org_has_no_members(org_id)
);

create policy "admins remove members"
on public.organization_members for delete
using (public.is_org_admin(org_id, auth.uid()));

create policy "admins read invitations"
on public.organization_invitations for select
using (public.is_org_admin(org_id, auth.uid()));

create policy "members read their ownerships"
on public.entity_ownership for select
using (public.is_org_member(org_id, auth.uid()));

-- Sending an invitation, redeeming one, recording a publish and reviewing a
-- claim all go through the service role. None of them is a thing an end user
-- should be able to do by talking to PostgREST directly.

-- These three are called from inside the policies above, and a policy expression
-- runs with the privileges of whoever is running the query — so `authenticated`
-- must keep EXECUTE or every policy that calls them fails with "permission denied
-- for function". What comes off is the blanket PUBLIC grant Postgres adds to every
-- new function, which is what reaches `anon` (database linter 0028/0029).
revoke execute on function public.is_org_member(uuid, uuid) from public, anon;
revoke execute on function public.is_org_admin(uuid, uuid) from public, anon;
revoke execute on function public.org_has_no_members(uuid) from public, anon;

grant execute on function public.is_org_member(uuid, uuid) to authenticated;
grant execute on function public.is_org_admin(uuid, uuid) to authenticated;
grant execute on function public.org_has_no_members(uuid) to authenticated;

-- Zero rows, referenced by no code: superseded by entity_ownership before it
-- was ever used.
drop table public.ownerships;

comment on table public.promoter_profiles is
'Superseded by public.organizations. Read by the account page until the pro screens are rebuilt.';

\echo '=== applying 20260827000022_ownership_claims.sql ==='
-- Phase D: claiming becomes a lifecycle, and founding an organization becomes
-- one transaction.
--
-- 20260819000011 landed the record -- organizations, members, invitations,
-- entity_ownership -- with nothing enforcing it, because the pusher was
-- create-only and there was no edit to authorize. Phase E adds the edits. This
-- migration is what they will consult.
--
-- Numbering note: the approved plan slotted this at 20260825000016, which now
-- sorts before applied history, so `db push` would skip it silently. 21 is the
-- feedback rating, so ownership takes 22 and phase G's review signals take 23.
--
-- Four things change:
--
--  1. A claim gains a status. Until now the only way to undo one was DELETE,
--     which loses the fact that it was ever made and who reviewed it.
--     Revocation is a reviewer's verdict and belongs in the trail, so 'revoked'
--     is a state rather than an absence. A rejected claim and a withdrawn one
--     are the same state deliberately: both mean "this org does not speak for
--     this entity", and splitting them buys a distinction no screen would draw.
--
--  2. Founding an organization stops being two round trips. The old shape was
--     an insert under one policy followed by a member insert under another, so
--     an interrupted client left an org with no members -- which the founder
--     policy then treats as claimable by the next person to ask.
--
--  3. Edits get an audit table, before any edit route exists to fill it.
--
--  4. The gateway gets one question to ask: user_may_edit.


-- ---------------------------------------------------------------------------
-- 1 - entity_ownership gains a lifecycle
-- ---------------------------------------------------------------------------

alter table public.entity_ownership
add column status text not null default 'active'
check (status in ('active', 'revoked'));

alter table public.entity_ownership
add column revoked_by uuid references auth.users (id);

alter table public.entity_ownership
add column revoked_at timestamptz;

alter table public.entity_ownership
add column revoke_note text;

-- Denormalized so the "your claims" and /admin queues render a list without
-- asking the graph about every row. The graph stays the source of truth for
-- the entity itself; this is a label, and a stale one is a cosmetic bug.
alter table public.entity_ownership
add column entity_name text;

-- The table constraint forbade re-claiming an entity this org once held, even
-- after a revoke, because the revoked row keeps occupying the tuple. A partial
-- unique index says what was meant: one LIVE claim per org per entity.
alter table public.entity_ownership
drop constraint entity_ownership_org_id_entity_type_entity_uid_key;

create unique index entity_ownership_active_claim_idx
on public.entity_ownership (org_id, entity_type, entity_uid)
where status = 'active';


-- ---------------------------------------------------------------------------
-- 2 - founding an organization, atomically
-- ---------------------------------------------------------------------------

-- Both insert policies go. Between them they let a client create an org and
-- then seat itself, which is two statements and therefore two failure points.
drop policy "users create organizations" on public.organizations;
drop policy "founder takes the owner seat" on public.organization_members;

-- Parameters carry p_ prefixes because plpgsql resolves a bare `display_name`
-- inside INSERT ... VALUES to the parameter rather than the column, and the
-- two reading the same is the kind of thing that looks correct in review.
-- PostgREST derives the RPC's JSON argument names from these, so the gateway
-- posts {"p_kind": ..., "p_display_name": ...}.
create function public.create_organization(
    p_kind public.org_kind,
    p_display_name text,
    p_website text default null,
    p_phone text default null,
    p_contact_email text default null
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    caller uuid := auth.uid();
    caller_role public.app_role;
    new_org uuid;
begin
    if caller is null then
        raise exception 'not authenticated' using errcode = '28000';
    end if;

    -- The pro floor lives here rather than in the gateway because this is now
    -- the only way an organization can be created: a check the client cannot
    -- route around is worth more than one it can.
    select r.role into caller_role
    from public.user_roles r
    where r.user_id = caller;

    if coalesce(caller_role, 'user') not in ('pro', 'admin') then
        raise exception 'a promoter account is required to create an organization'
        using errcode = '42501';
    end if;

    insert into public.organizations (
        kind, display_name, website, phone, contact_email, created_by
    )
    values (
        p_kind, p_display_name, p_website, p_phone, p_contact_email, caller
    )
    returning id into new_org;

    insert into public.organization_members (org_id, user_id, role)
    values (new_org, caller, 'owner');

    return new_org;
end;
$$;


-- ---------------------------------------------------------------------------
-- 3 - the edit audit
-- ---------------------------------------------------------------------------

-- Written by the gateway with the service role after a successful graph write,
-- carrying the writer's own old/new delta per field. RLS on with no user
-- policies: nobody reads this through PostgREST, and /admin reads it through
-- the gateway.
create table public.entity_edits (
    id bigint generated always as identity primary key,
    entity_type text not null check (entity_type in ('venue', 'artist', 'event')),
    entity_uid text not null,
    -- Not `on delete cascade`: an audit trail that disappears together with
    -- the organization it indicts is not an audit trail.
    org_id uuid references public.organizations (id) on delete set null,
    user_id uuid references auth.users (id),
    changes jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index entity_edits_entity_idx on public.entity_edits (entity_type, entity_uid);
create index entity_edits_org_idx on public.entity_edits (org_id, created_at desc);

alter table public.entity_edits enable row level security;


-- ---------------------------------------------------------------------------
-- 4 - the one authorization question
-- ---------------------------------------------------------------------------

-- May this user edit this entity? True when any organization they belong to
-- holds a LIVE claim on it. Verified is deliberately not required: a pending
-- claim may edit, because review latency is ours, and a promoter waiting on us
-- to correct their own door time is a worse failure than an unreviewed edit
-- that the audit table records and an admin can revert.
--
-- Definer for the same reason as is_org_member: it reads organization_members,
-- whose policies would otherwise show the caller only their own rows.
create function public.user_may_edit(
    p_entity_type text,
    p_entity_uid text,
    p_uid uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.entity_ownership o
    inner join public.organization_members m on o.org_id = m.org_id
    where
      o.entity_type = p_entity_type
      and o.entity_uid = p_entity_uid
      and o.status = 'active'
      and m.user_id = p_uid
  );
$$;


-- ---------------------------------------------------------------------------
-- 5 - grants
-- ---------------------------------------------------------------------------

-- Strip the blanket PUBLIC execute Postgres adds to every new function, which
-- is what reaches anon (database linter 0028/0029), then hand it back
-- deliberately. user_may_edit also goes to service_role: the gateway is its
-- caller, and a revoked PUBLIC grant takes service_role with it.
revoke execute on function
public.create_organization(public.org_kind, text, text, text, text)
from public, anon;

revoke execute on function public.user_may_edit(text, text, uuid) from public, anon;

grant execute on function
public.create_organization(public.org_kind, text, text, text, text)
to authenticated;

grant execute on function public.user_may_edit(text, text, uuid) to authenticated;
grant execute on function public.user_may_edit(text, text, uuid) to service_role;

-- Column-level grants on organizations, per the 20260814000008 pattern. The
-- "admins update their organization" policy constrains WHICH row an admin may
-- update and says nothing about which columns; without this an admin can
-- rewrite `kind` or `created_by` on their own org. Editable is what the
-- /pro/org form shows.
revoke update on public.organizations from authenticated;

grant update (display_name, website, phone, contact_email, updated_at)
on public.organizations
to authenticated;

\echo '=== behaviour ==='
-- Behaviour of 20260827000022, not just its syntax.
-- auth.uid() becomes GUC-driven so a caller can be simulated.
create or replace function auth.uid() returns uuid
language sql stable as $$ select nullif(current_setting('test.uid', true), '')::uuid $$;

insert into auth.users (id) values
('00000000-0000-0000-0000-00000000000a'),   -- pro, founder
('00000000-0000-0000-0000-00000000000b'),   -- plain user
('00000000-0000-0000-0000-00000000000c');   -- pro, stranger

insert into public.user_roles (user_id, role) values
('00000000-0000-0000-0000-00000000000a', 'pro'),
('00000000-0000-0000-0000-00000000000b', 'user'),
('00000000-0000-0000-0000-00000000000c', 'pro');

\echo '--- 1. a plain user cannot found an organization ---'
set test.uid = '00000000-0000-0000-0000-00000000000b';
do $$
begin
  perform public.create_organization('venue', 'Should Not Exist');
  raise exception 'FAIL: a user-role caller founded an organization';
exception when insufficient_privilege then
  raise notice 'PASS: refused with %', sqlerrm;
end $$;

\echo '--- 2. an anonymous caller cannot found one ---'
set test.uid = '';
do $$
begin
  perform public.create_organization('venue', 'Should Not Exist');
  raise exception 'FAIL: anonymous founded an organization';
exception when invalid_authorization_specification then
  raise notice 'PASS: refused with %', sqlerrm;
end $$;

\echo '--- 3. a pro founds an org and is seated as owner atomically ---'
set test.uid = '00000000-0000-0000-0000-00000000000a';
select public.create_organization('venue', 'Sala Apolo', 'https://apolo.example') as org_id \gset
select
  (select count(*) from public.organizations where id = :'org_id') = 1 as org_created,
  (select role::text from public.organization_members
   where org_id = :'org_id' and user_id = '00000000-0000-0000-0000-00000000000a') as founder_role;

\echo '--- 4. one active claim per org+entity; a second is rejected ---'
insert into public.entity_ownership (org_id, entity_type, entity_uid, basis, entity_name)
values (:'org_id', 'venue', 'venue-1', 'claimed', 'Sala Apolo');
do $$
begin
  insert into public.entity_ownership (org_id, entity_type, entity_uid, basis)
  values ((select id from public.organizations limit 1), 'venue', 'venue-1', 'claimed');
  raise exception 'FAIL: duplicate active claim was allowed';
exception when unique_violation then
  raise notice 'PASS: duplicate active claim rejected';
end $$;

\echo '--- 5. user_may_edit: member of the claiming org ---'
select public.user_may_edit('venue', 'venue-1', '00000000-0000-0000-0000-00000000000a') as member_may_edit,
       public.user_may_edit('venue', 'venue-1', '00000000-0000-0000-0000-00000000000c') as stranger_may_edit,
       public.user_may_edit('venue', 'venue-2', '00000000-0000-0000-0000-00000000000a') as unclaimed_may_edit;

\echo '--- 6. revoking kills edit rights and frees the slot for a re-claim ---'
update public.entity_ownership
set status = 'revoked', revoked_at = now(), revoke_note = 'evidence withdrawn'
where entity_uid = 'venue-1';

select public.user_may_edit('venue', 'venue-1', '00000000-0000-0000-0000-00000000000a')
  as revoked_may_edit;

insert into public.entity_ownership (org_id, entity_type, entity_uid, basis, entity_name)
values (:'org_id', 'venue', 'venue-1', 'claimed', 'Sala Apolo');

select count(*) filter (where status = 'active')  as active_claims,
       count(*) filter (where status = 'revoked') as revoked_claims
from public.entity_ownership where entity_uid = 'venue-1';

\echo '--- 7. re-claim restored edit rights ---'
select public.user_may_edit('venue', 'venue-1', '00000000-0000-0000-0000-00000000000a')
  as reclaimed_may_edit;

\echo '--- 8. the audit survives its organization being deleted ---'
insert into public.entity_edits (entity_type, entity_uid, org_id, user_id, changes)
values ('venue', 'venue-1', :'org_id', '00000000-0000-0000-0000-00000000000a',
        '{"address": {"old": "x", "new": "y"}}'::jsonb);
delete from public.organizations where id = :'org_id';
select count(*) as audit_rows_kept, count(org_id) as org_id_still_set
from public.entity_edits;

\echo '--- 9. column grants: kind and created_by are not updatable by authenticated ---'
select string_agg(column_name, ', ' order by column_name) as authenticated_may_update
from information_schema.column_privileges
where grantee = 'authenticated'
  and table_name = 'organizations'
  and privilege_type = 'UPDATE';
