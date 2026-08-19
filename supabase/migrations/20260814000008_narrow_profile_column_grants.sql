-- Column-level grants on public.profiles.
--
-- The frontend edits profiles directly (RLS is the enforcement point — see
-- frontend/src/api/profile.ts for why that beats a gateway route). The existing
-- policy allows a user to UPDATE their own row, and "their own row" is the only
-- thing it constrains: every column of it is fair game.
--
-- That is fine for today's three columns and wrong the moment this table gains
-- one the user must not set for themselves — a plan, a quota override, a
-- verified flag. Grants are the right place to say which columns are theirs,
-- because it keeps the rule next to the data instead of in a client we ship.

revoke update on public.profiles from authenticated;

grant update (display_name, ui_language, updated_at)
on public.profiles
to authenticated;
