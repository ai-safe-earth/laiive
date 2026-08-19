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
-- reads the table without re-entering RLS and breaks the cycle. EXECUTE is
-- revoked from the API roles at the end: the policies call these as the
-- definer, nobody needs to call them directly.
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
