-- Eval phase 1 addendum: a direction on turn_feedback, so a thumbs-up can be
-- stored next to the down. The down stays the informative event — error
-- analysis reads only downs; ups are inert positive labels until judge
-- calibration wants graded examples. Default 'down' keeps the rows already
-- written in production truthful: every pre-column row was a down.
--
-- Numbering note: this takes 21, so phase D's ownership migration moves to 22
-- and phase G's review-signal columns to 23.
--
-- Deploy order: apply this before deploying the gateway that sends rating —
-- PostgREST rejects unknown insert columns, so a new gateway against the old
-- schema would 502 every feedback post, downs included.

alter table public.turn_feedback
add column rating text not null default 'down'
check (rating in ('up', 'down'));
