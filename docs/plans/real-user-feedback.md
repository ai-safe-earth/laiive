---
status: active
step: evals
next: location-and-distance plan first, then the still-failing turns become cases (step 4)
---
# Real-user feedback into fixes

Owner, 2026-10-09: evals come first now, so the system improves from what real users
say, not only from cases we wrote ourselves.

## What already exists
- Thumbs up/down on every answer (`Chat.tsx`), with an optional typed reason, posted by
  the gateway (`services/gateway/src/feedback.ts`) into `turn_feedback`.
- One `request_id` joins three tables: `conversation_logs` (the question and history),
  `eval_records` (the answer, cyphers, errors, timings) and `turn_feedback` (the label).
- `services/retriever/evals/queries.sql`: the complaint queue and "failures nobody
  complained about", meant to be pasted into the Supabase SQL editor.
- Retention: logs older than 90 days are pruned unless the turn got a thumbs-down.
- Missing: nobody reads it on a schedule, and a complaint never becomes a test case.

## Steps
- [x] 1. Feedback census (read-only, like `agent/scripts/census.py`): turns, downs, ups,
      reasons, error turns and empty-answer turns since launch and in the last 7 days.
      Tells us if there is enough volume to read, or if getting feedback is the problem.
      2026-10-09, scratch script (becomes part of step 2): since 2026-08-26, 9 users,
      133 answered turns, 71 thumbs (61 down, 10 up), 24 downs with a typed reason.
      57 of 115 searches (half) found 0 events. Last 7 days: 2 users, 35 turns, 17 of 34
      searches empty, 4 turns with errors (the Aura pause), 7 downs.
      Enough to read. Volume is not the problem yet; empty answers are.
      Note: 421 `conversation_logs` rows against 133 `eval_records`; the gap is not
      explained yet (other gateway routes, or turns before capture). Step 2 checks it.
- [x] 2. `agent/scripts/feedback.py`: the weekly read, grouped into threads (owner,
      2026-10-09: "threads, so I see the main lines, not single logs"). Design:
      - Turns read: every thumb, plus unflagged failures (no events, error, HTTP >= 400).
        Base is `conversation_logs` (328 chat turns), answers from `eval_records` and,
        before 2026-08-26 capture, from the next turn's resent history.
      - Facts labelled in code (graph-down, error, http-NNN, no-events). One model call
        (composer model, ~2 cents) labels each turn with a thread; any failure thread
        over a quarter of the turns gets a second call that splits it by cause into
        `parent/child` threads.
      - Thread names, descriptions and counts are saved to `evals/failure_modes.json`
        and reused next run, so each line can be followed week to week. No user text.
      - First run: 87 turns read (36 down, 10 up, 41 unflagged). Biggest lines:
        no events found (about 55%, split by place, near me, date, genre), events the
        user knows exist but were not found (17), lost follow-up context (5), wrong
        event details (3), duplicates (2). 21 requests carried no question (401/422/429).
      - Known ceiling: names drift between runs (one run split "no events" by city,
        another by date/genre/area). Reusing saved names should settle it; step 3
        prunes the list by hand.
- [x] 3. Read the first batch together and name the failure modes (wrong city, empty when
      events exist, wrong language, invented details...). The list drives what gets fixed.
      2026-10-09: the owner named seven threads, saved in `evals/failure_modes.json`:
      database-access, location-and-distance, name-spelling, conversation-issues,
      query-interpretation, wrong-event-data, unwanted-reply-text (plus one success line).
      Replay: all 87 turns re-asked against today's graph and the develop code (read-only,
      dates move to today, so "finds events now" is a hint, not proof). Counts after a
      hand check of the model's labels:
      | thread | turns | still failing |
      |---|---|---|
      | location-and-distance | 31 | 31 |
      | database-access | 23 | 6 (rock in Torino this week, DJ sets) |
      | wrong-event-data | 9 | 4 |
      | conversation-issues | 7 | 1 |
      | query-interpretation | 3 | 0 |
      | name-spelling | 3 | 1 (a venue written as one word) |
      | unwanted-reply-text | 1 | 1 |
      | success | 10 | - |
      Location is the main line: 21 "near me" turns with no location, 10 named places read
      as "near me" (a v3 regression, unreleased). Plan: `location-and-distance.md`.
- [ ] 4. Each confirmed failure becomes a case in the matching dataset (classifier,
      answer quality, retrieval) with `source: user` and the `request_id`, so a fix is
      proven against the real complaint and stays fixed.
- [ ] 5. If volume is too low: make giving feedback easier (owner's call), and add the
      logs the owner plans, then re-run step 1.

## Decisions
- Phoenix stays local (owner, 2026-10-09): no Phoenix Cloud. The feedback read needs only
  Supabase. The owner removes the unused `LANGFUSE_*` Fly secrets.
- Reads only. Supabase writes are still handed to the owner as commands.
- No judge model and no nightly job yet: that is the self-improvement step, and it needs
  the failure-mode list from step 3 first.
- User text in the printouts stays local (terminal), never in commits or plan files;
  only counts and anonymised patterns get written down here.
