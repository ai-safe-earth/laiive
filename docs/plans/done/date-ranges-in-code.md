---
status: done
step: retrieval
next: none; event-data-quality is next in the owner's order
---
# Date ranges resolved in code

Owner, 2026-10-10: "this weekend" must be exact when the user's clock is right; a
time-interval function, called as a tool, does the work.

## Before
- The classifier wrote `date_from`/`date_to` itself from today's date, so it did
  the calendar maths. Once, "this weekend" asked on a Saturday came out as
  Wednesday to Friday.

## Design
- The classifier names the interval instead of computing it:
  `"when": "now" | "tonight" | "today" | "tomorrow" | "this_weekend" |
  "next_weekend" | "this_week" | "next_week" | "this_month" | "next_month" |
  "<weekday>" | "YYYY-MM-DD" | "YYYY-MM"`, or two of these joined by `..`.
- `resolve_when(when, now)` in `agent/classifier.py` turns it into dates on the
  user's clock. Ends are exclusive and a night runs to 06:00 the next day.
  "This weekend" asked Friday to Sunday starts today; on a Sunday it is today only.
  "Next weekend" is always the one after this one.
- Prompt v7.

## Steps
- [x] 1. `resolve_when()` plus a table test: each interval asked on each weekday
      (`tests/test_classifier.py::TestResolveWhen`).
- [x] 2. Classifier prompt emits `when`; `resolve_dates()` fills the dates from it
      before the follow-up merge. An unknown name keeps the model's own dates.
- [x] 3. Dataset: six cases on a fixed clock (`"now"` in the case), so "this
      weekend on a Saturday" is testable.

## Decisions
- Owner, 2026-10-10: use a real tool call if it is more reliable; if not, add a
  short step-by-step reasoning to the prompt.
- 2026-10-10: the `when` field, not a tool call. The same function does the
  maths either way, so a tool call cannot be more exact; it only adds a second
  model round trip per turn. What failed was the model still doing maths
  ("from tomorrow until sunday" came back as one day, 3 runs of 3). The
  step-by-step fix: a `time_words` field the model fills first (the user's time
  words, verbatim), then `when`. After it, 3 of 3 right, in English and Italian.
- Prompt optimisation with DSPy is its own plan: `prompt-optimization.md`.
