-- handle_new_user is a trigger function; nothing should call it directly.
-- Postgres grants EXECUTE to PUBLIC on every new function, which makes any
-- SECURITY DEFINER function in the exposed `public` schema reachable by anon
-- and authenticated (database linter 0028/0029). Revoke it.

revoke execute on function public.handle_new_user() from public, anon, authenticated;
