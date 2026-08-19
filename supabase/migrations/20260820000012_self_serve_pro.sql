-- Self-serve pro: filling in promoter details is what makes an account a
-- promoter account.
--
-- Before this there was no path from 'user' to 'pro' anywhere in the product.
-- /pro refused a plain user and linked to /account, whose promoter section
-- only rendered for accounts that were already pro — a closed loop the product
-- could not exit, and the role was reachable only by hand through the service
-- role.
--
-- The grant lives in a trigger rather than in the client because user_roles
-- deliberately has no policy letting an end user write their own role, and that
-- stays true. What the client may do is create its own promoter_profiles row —
-- RLS already allows exactly that and only that — and this turns that row into
-- the role.

create function public.grant_pro_on_promoter_profile()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- handle_new_user() gives every account a user_roles row at signup, so this
  -- insert is a belt for the case where it did not.
  insert into public.user_roles (user_id, role)
  values (new.user_id, 'pro')
  on conflict (user_id) do nothing;

  -- Promote 'user' only. An admin who fills in promoter details must not be
  -- demoted to pro, and an account demoted by hand must not silently climb back.
  update public.user_roles
  set
      role = 'pro',
      updated_at = now()
  where user_id = new.user_id and role = 'user';

  return new;
end;
$$;

-- After insert only. The first save is the one that grants; later edits are
-- updates, and re-granting on those would re-promote a demoted account.
create trigger grant_pro_on_promoter_profile
after insert on public.promoter_profiles
for each row execute function public.grant_pro_on_promoter_profile();

-- Nothing calls this directly — it is reachable only as a trigger.
revoke execute on function public.grant_pro_on_promoter_profile()
from authenticated, anon, public;
