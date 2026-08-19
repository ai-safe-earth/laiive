-- Conversation capture, written fire-and-forget by the gateway with the
-- service role (replaces the old validate-conversation edge function).
-- RLS on with no user policies: service-role only.

create table public.conversation_logs (
    id bigint generated always as identity primary key,
    request_id text not null,
    user_id uuid,
    user_role text not null,
    route text not null,
    status integer,
    duration_ms integer,
    payload jsonb,
    created_at timestamptz not null default now()
);

create index conversation_logs_user_idx on public.conversation_logs (user_id, created_at desc);
create index conversation_logs_created_idx on public.conversation_logs (created_at desc);

alter table public.conversation_logs enable row level security;
