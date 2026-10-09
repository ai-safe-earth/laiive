---
status: active
step: evals
next: write agent/scripts/feedback.py, the weekly read of the complaint queue
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
- [ ] 2. A weekly read script, `agent/scripts/feedback.py`: queries 1 and 2 of
      `queries.sql` printed as one readable block per turn (question, what the classifier
      understood, how many events, the answer, the reason). No SQL editor needed.
- [ ] 3. Read the first batch together and name the failure modes (wrong city, empty when
      events exist, wrong language, invented details...). The list drives what gets fixed.
- [ ] 4. Each confirmed failure becomes a case in the matching dataset (classifier,
      answer quality, retrieval) with `source: user` and the `request_id`, so a fix is
      proven against the real complaint and stays fixed.
- [ ] 5. If volume is too low: make giving feedback easier (owner's call), and add the
      logs the owner plans, then re-run step 1.

## Decisions
- Reads only. Supabase writes are still handed to the owner as commands.
- No judge model and no nightly job yet: that is the self-improvement step, and it needs
  the failure-mode list from step 3 first.
- User text in the printouts stays local (terminal), never in commits or plan files;
  only counts and anonymised patterns get written down here.
