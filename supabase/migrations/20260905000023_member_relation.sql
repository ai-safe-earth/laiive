-- Pro identity: who the person is to the organization they stand behind.
--
-- The pro form asked one thing, "organisation", and stored it as a name. A
-- venue owner, a venue employee, a band member and a freelance organiser were
-- the same row, and docs/roadmap/02-ownership.md specified "your role in it"
-- on 2026-08-19 without it ever landing. Two changes:
--
--  1. org_kind gains 'agency'. A manager of several artists is neither the
--     artist nor a promoter, and the three-way enum forced them to pick one.
--
--  2. organization_members gains `relation`: owner / employee / freelance /
--     member. It is a description, not a permission -- `role` stays the
--     permission -- and it exists so a reviewer has context when claims start
--     being reviewed. An enum rather than free text because the form is a
--     fixed list, and a check the database enforces beats one the client does.
--
-- Numbering: 23 was earmarked for phase G's review signals; they take 24.


-- ---------------------------------------------------------------------------
-- 1 - a fourth kind
-- ---------------------------------------------------------------------------

alter type public.org_kind add value 'agency';


-- ---------------------------------------------------------------------------
-- 2 - the person's relation to the organization
-- ---------------------------------------------------------------------------

create type public.member_relation as enum ('owner', 'employee', 'freelance', 'member');

alter table public.organization_members
add column relation public.member_relation;

-- The definer RPC stays the only writer of a new seat (22 dropped the insert
-- policies for that reason), so it carries the relation in. Signature change
-- means drop-and-recreate: Postgres overloads rather than replaces, and two
-- create_organization functions is a PostgREST ambiguity error. The body is
-- 22's verbatim plus the one column.
drop function public.create_organization(public.org_kind, text, text, text, text);

create function public.create_organization(
    p_kind public.org_kind,
    p_display_name text,
    p_website text default null,
    p_phone text default null,
    p_contact_email text default null,
    p_relation public.member_relation default null
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

    insert into public.organization_members (org_id, user_id, role, relation)
    values (new_org, caller, 'owner', p_relation);

    return new_org;
end;
$$;

revoke execute on function
public.create_organization(public.org_kind, text, text, text, text, public.member_relation)
from public, anon;

grant execute on function
public.create_organization(public.org_kind, text, text, text, text, public.member_relation)
to authenticated;

-- A member may describe their own seat later, and only that: the row is
-- theirs by policy, the column is the only one granted (22:217 pattern), so
-- `role` and `org_id` stay out of reach even from a client that tries.
revoke update on public.organization_members from authenticated;

grant update (relation) on public.organization_members to authenticated;

create policy "members describe their own seat"
on public.organization_members for update
using (user_id = auth.uid())
with check (user_id = auth.uid());
