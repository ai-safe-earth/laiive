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
