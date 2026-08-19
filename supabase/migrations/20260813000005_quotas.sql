-- Quotas (D7): per-role defaults with optional per-user overrides.
-- The gateway currently enforces limits from env config; these tables are the
-- durable definition it will read once per-user overrides matter.

create table public.role_quotas (
    role public.app_role primary key,
    requests_per_minute integer not null,
    requests_per_day integer not null
);

insert into public.role_quotas (role, requests_per_minute, requests_per_day) values
('user', 60, 500),
('pro', 120, 2000),
('admin', 240, 10000);

create table public.user_quotas (
    user_id uuid primary key references auth.users (id) on delete cascade,
    requests_per_minute integer,
    requests_per_day integer,
    reason text,
    created_at timestamptz not null default now()
);

alter table public.role_quotas enable row level security;
alter table public.user_quotas enable row level security;

create policy "anyone authenticated reads role quotas"
on public.role_quotas for select
to authenticated
using (true);

create policy "users read own quota override"
on public.user_quotas for select
using (auth.uid() = user_id);
