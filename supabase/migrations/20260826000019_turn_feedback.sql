-- Eval phase 1: a thumbs-down on an assistant turn, written by the gateway
-- with the service role. request_id joins the whole picture: the gateway's
-- conversation_logs row carries the full client-sent history for that turn
-- (chat is stateless, the client resends everything), and eval_records
-- carries the answer — so one id links feedback, conversation, and output.
-- The click posts immediately with a null reason (the down itself is the
-- informative event); an optional reason arrives as a second row for the
-- same request_id.
--
-- Numbering note: this takes 19, so phase G's review-signal columns (which
-- 18 pointed at 19) move to 20.

create table public.turn_feedback (
    id bigint generated always as identity primary key,
    request_id text not null,
    user_id uuid,
    reason text,
    created_at timestamptz not null default now()
);

create index turn_feedback_request_idx on public.turn_feedback (request_id);

alter table public.turn_feedback enable row level security;
