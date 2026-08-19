-- Profiles: one row per auth user, created automatically on signup.
-- UI chrome languages per D6: en/es/it/ca.

create table public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    display_name text,
    ui_language text not null default 'en'
    check (ui_language in ('en', 'es', 'it', 'ca')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "users read own profile"
on public.profiles for select
using (auth.uid() = id);

create policy "users update own profile"
on public.profiles for update
using (auth.uid() = id)
with check (auth.uid() = id);

create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'display_name');
  insert into public.user_roles (user_id, role) values (new.id, 'user');
  return new;
end;
$$;

-- trigger is created in the user_roles migration, after both tables exist
