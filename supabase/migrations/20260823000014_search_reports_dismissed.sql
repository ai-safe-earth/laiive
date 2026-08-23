-- A way out of the review queue that is not approval.
--
-- Until now a report could only go dry_run -> approved. A sweep that found
-- nothing worth keeping had no exit and stayed in the queue forever, which is
-- how 12 of the 17 reports came to be sitting there unreviewed. Dismissing is
-- a decision a person made, recorded the same way approving is, so the queue
-- can be emptied honestly rather than by widening a filter.
--
-- reviewed_by / reviewed_at are deliberately separate from approved_by /
-- approved_at: "who cleared this" and "who wrote these events to the graph"
-- are different questions, and conflating them would make the second one
-- unanswerable.

alter table public.search_reports drop constraint search_reports_status_check;

alter table public.search_reports add constraint search_reports_status_check
check (status in ('running', 'dry_run', 'approved', 'dismissed', 'failed', 'done'));

alter table public.search_reports add column reviewed_by uuid;
alter table public.search_reports add column reviewed_at timestamptz;
alter table public.search_reports add column review_note text;

-- The queue read: everything still waiting, newest first.
create index search_reports_status_idx on public.search_reports (status, created_at desc);
