-- 202+poll lifecycle for search_reports (Phase 6): sweep and backfill now
-- return 202 and run in the background, so a report row exists before its
-- results do. New statuses: 'running' (in flight), 'failed' (worker died,
-- see `error`), 'done' (terminal for backfill, which never gets approved).
-- The approve compare-and-set still matches only 'dry_run', so running and
-- failed reports are unapprovable without any service-side check.
-- Backfill rows have no city, hence the dropped NOT NULL.

alter table public.search_reports
drop constraint search_reports_status_check;

alter table public.search_reports
add constraint search_reports_status_check
check (status in ('running', 'dry_run', 'approved', 'failed', 'done'));

alter table public.search_reports
add column error text;

alter table public.search_reports
add column kind text not null default 'sweep'
check (kind in ('sweep', 'backfill'));

alter table public.search_reports
alter column city drop not null;
