-- Eval phase 0: the answer side of a chat turn, written fire-and-forget by the
-- retriever with the service role. Joins conversation_logs (the request side,
-- written by the gateway) on request_id — the retriever now reads the
-- gateway's x-request-id instead of minting its own, so the two halves share
-- a key. Like conversation_logs: RLS on with no user policies = service-role
-- only.
--
-- Numbering note: this takes 18, so phase G's review-signal columns (which 17
-- pointed at 18) move to 19.

create table public.eval_records (
    id bigint generated always as identity primary key,
    request_id text not null,
    final_text text,
    card_uids text[],  -- noqa: LT01
    cyphers text[],  -- noqa: LT01
    query_type text,
    moment text,
    retrieval_notes text[],  -- noqa: LT01
    row_count integer,
    latency_ms integer,
    errors text[],  -- noqa: LT01
    created_at timestamptz not null default now()
);

create index eval_records_request_idx on public.eval_records (request_id);
create index eval_records_created_idx on public.eval_records (created_at desc);

alter table public.eval_records enable row level security;
