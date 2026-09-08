-- Joining an organization is what makes you a promoter.
--
-- 20260819000011 landed organization_invitations complete -- token hash,
-- expiry, accepted_at, a partial unique index on pending invites per address --
-- and nothing has referenced it since. The routes that redeem it arrive with
-- this migration's sibling commits; what is missing on the database side is the
-- one thing the routes must not do themselves.
--
-- An invited person is very often not a promoter yet. The account role lives in
-- public.user_roles, which deliberately has no policy letting an end user write
-- their own role, and the gateway holds the service key -- so "grant pro on
-- accept" written in TypeScript would be the gateway reaching past RLS to set
-- somebody's role directly. 20260820000012 already answered this question for
-- the other door: the client writes the one row it owns, and a trigger decides
-- what that row means. This is that answer for the second door.
--
-- Numbering: 24 stays earmarked for phase G's review signals (see the header of
-- 20260905000023). 25 is org-mate profiles. This is 26, and its date prefix
-- sorts after every applied migration -- db push silently skips anything
-- sorting earlier.


create function public.grant_pro_on_org_membership()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- handle_new_user() gives every account a user_roles row at signup, so this
  -- insert is a belt for the case where it did not. Same belt as
  -- 20260820000012, and for the same reason.
  insert into public.user_roles (user_id, role)
  values (new.user_id, 'pro')
  on conflict (user_id) do nothing;

  -- Promote 'user' only. An admin invited onto a venue's roster must not be
  -- demoted to pro, and an account demoted by hand must not climb back by being
  -- re-invited. Byte for byte the rule 20260820000012 settled on.
  update public.user_roles
  set
      role = 'pro',
      updated_at = now()
  where user_id = new.user_id and role = 'user';

  return new;
end;
$$;

-- After insert only. A seat that changes relation later is an update, and
-- re-granting on those would re-promote a demoted account -- the same trap the
-- promoter_profiles trigger avoids by being insert-only.
--
-- This also fires for the founder seat that create_organization writes, which
-- is harmless and free: that function already has a pro floor (it refuses a
-- plain user outright), so the guarded update matches no row.
create trigger grant_pro_on_org_membership
after insert on public.organization_members
for each row execute function public.grant_pro_on_org_membership();

-- Nothing calls this directly -- it is reachable only as a trigger.
revoke execute on function public.grant_pro_on_org_membership()
from authenticated, anon, public;

comment on function public.grant_pro_on_org_membership() is
'A seat in an organization grants the pro account role, as filling in promoter details does.';


-- ---------------------------------------------------------------------------
-- What is deliberately NOT here
-- ---------------------------------------------------------------------------

-- No INSERT/UPDATE/DELETE policy on organization_invitations. 20260819000011
-- states the position and it still holds: "Sending an invitation, redeeming one,
-- recording a publish and reviewing a claim all go through the service role.
-- None of them is a thing an end user should be able to do by talking to
-- PostgREST directly." The gateway owns all three, and re-checks the caller's
-- seat on every one of them because the service key has already stepped over
-- the row-level rules by the time it is used. The existing "admins read
-- invitations" SELECT policy is enough for the roster to list pending invites
-- under the user's own JWT.
--
-- No status column, and revocation is a DELETE. 20260827000022 argued the
-- opposite for claims -- "Revocation is a reviewer's verdict and belongs in the
-- trail" -- and that reasoning does not carry here: an invitation nobody
-- accepted records only that somebody typed an address. Worse, the partial
-- unique index is `where accepted_at is null`, so a kept-but-revoked row would
-- occupy the one live slot for that address and block re-inviting it. Accepted
-- invitations are still kept as history, which is the half worth keeping.
--
-- No INSERT policy on organization_members either. There is none today
-- (20260827000022:73 dropped the founder policy once create_organization took
-- over), and redeeming an invitation is a service-role write, so adding one
-- would widen the table for nobody.
