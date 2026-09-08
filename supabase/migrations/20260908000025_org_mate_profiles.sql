-- A member can read the name of somebody in the same organization.
--
-- The roster on /pro/org has printed raw uuids for every seat but your own
-- since it shipped, because public.profiles has exactly one SELECT policy --
-- `auth.uid() = id` (20260813000001) -- and there is no org-scoped exception.
-- ProOrg.tsx said so in a comment and the UI shipped the uuid.
--
-- Numbering: 24 stays earmarked for phase G's review signals (see the header
-- of 20260905000023). This is 25, and its date prefix sorts after every
-- applied migration -- db push silently skips anything sorting earlier.


-- ---------------------------------------------------------------------------
-- 1 - reading an org mate's profile
-- ---------------------------------------------------------------------------

-- shares_org_with follows is_org_member next door: SECURITY DEFINER with an
-- empty search_path, reading only organization_members. It never touches
-- profiles, so the policy cannot recurse into itself.
--
-- It is a function rather than a subquery in the policy for the same reason
-- every other policy here calls one. Inline, the rule would read `exists
-- (select 1 from organization_members where user_id = profiles.id)` -- which
-- passes today only because that table's own RLS hides the rows a stranger
-- must not see. Correct by accident of a different table's policy, and one
-- edit to that policy away from exposing every profile in the database. As a
-- definer function the rule is true on its own terms, and testable on its own.

create function public.shares_org_with(other uuid, uid uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.organization_members mine
        inner join public.organization_members theirs
            on mine.org_id = theirs.org_id
        where mine.user_id = uid and theirs.user_id = other
    );
$$;

revoke execute on function public.shares_org_with(uuid, uuid) from public, anon;
grant execute on function public.shares_org_with(uuid, uuid) to authenticated;

-- Policies are PERMISSIVE and OR-ed, so "users read own profile" is untouched:
-- somebody in no organization sees exactly what they saw before.

create policy "members read their org mates' profiles"
on public.profiles for select
using (public.shares_org_with(id, auth.uid()));

-- Note for whoever adds the next column to profiles: the SELECT *grant* on
-- this table is table-wide (Supabase's default; 20260814000008 narrowed only
-- UPDATE), so ui_language and both timestamps are now org-mate-visible too.
-- Harmless for those three. Anything sensitive needs a column-level SELECT
-- grant, the same move 20260814000008 made for UPDATE.

comment on policy "members read their org mates' profiles" on public.profiles is
'A shared organization makes the other seats readable, so the roster can show names.';


-- ---------------------------------------------------------------------------
-- 2 - a postal address on the organization
-- ---------------------------------------------------------------------------

-- Evidence, not a venue address. website and phone are already filed as "what
-- a reviewer checks when a claim is reviewed" (20260819000011), and a street
-- address is the same kind of fact about the organization itself.
--
-- Deliberately NOT the address of any venue it manages: the graph owns those,
-- one org may manage five rooms, and a copy here would be a second source of
-- truth for the deduplication work to reconcile later.

alter table public.organizations add column address text;

-- Column privileges accumulate, so this adds one rather than restating the
-- five granted in 20260827000022.
grant update (address) on public.organizations to authenticated;

comment on column public.organizations.address is
'Postal address of the organization, as evidence. Not the address of a venue it manages.';
