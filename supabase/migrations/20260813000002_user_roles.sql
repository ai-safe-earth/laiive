-- Roles: user < pro < admin. The gateway reads the role from the JWT's
-- user_role claim, embedded by the custom access token hook below.
-- IMPORTANT owner step after applying: register the hook in the dashboard
-- (Authentication → Hooks → Customize Access Token) pointing at
-- public.custom_access_token_hook, or role changes never reach the JWT.

create type public.app_role as enum ('user', 'pro', 'admin');

create table public.user_roles (
    user_id uuid primary key references auth.users (id) on delete cascade,
    role public.app_role not null default 'user',
    granted_by uuid references auth.users (id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.user_roles enable row level security;

create policy "users read own role"
on public.user_roles for select
using (auth.uid() = user_id);

-- role changes go through the service role (admin tooling), not end users

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

-- Custom access token hook: stamps user_role into every JWT.
-- Role changes take effect on the next token refresh (~1h worst case).
create function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  claims jsonb;
  user_role public.app_role;
begin
  select role into user_role
  from public.user_roles
  where user_id = (event ->> 'user_id')::uuid;

  claims := event -> 'claims';
  claims := jsonb_set(claims, '{user_role}', to_jsonb(coalesce(user_role::text, 'user')));
  return jsonb_set(event, '{claims}', claims);
end;
$$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook from authenticated, anon, public;
grant select on table public.user_roles to supabase_auth_admin;

create policy "auth admin reads roles for token hook"
on public.user_roles for select
to supabase_auth_admin
using (true);
