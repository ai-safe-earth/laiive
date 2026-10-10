---
status: todo
step: retrieval
next: owner approves the design, then step 1
---
# Date ranges resolved in code

Owner, 2026-10-10: "this weekend" must be exact when the user's clock is right; a
time-interval function, called as a tool, does the work.

## Today
- The classifier writes `date_from`/`date_to` itself from today's date, so it does
  the calendar maths. Once, "this weekend" asked on a Saturday came out as
  Wednesday to Friday.

## Design (proposed)
- The classifier names the interval instead of computing it:
  `"when": "tonight" | "today" | "tomorrow" | "this_weekend" | "next_weekend" |
  "this_week" | "next_week" | "this_month" | "next_month" | "<weekday>" |
  "YYYY-MM-DD" | "YYYY-MM-DD..YYYY-MM-DD"`.
- `resolve_when(when, now)` in code turns it into dates on the user's clock
  (`now_in(timezone)`). Rules written once: "this weekend" on a Sunday is today
  only; "tonight" ends 06:00 the next day.
- "Called as a tool": the same function, but as a structured field and not an
  LLM tool call. A tool call adds a second model round trip per turn for the same
  result. Owner's call if a real tool call is wanted.

## Steps
- [ ] 1. `resolve_when()` plus a table test: each interval asked on each weekday.
- [ ] 2. Classifier prompt: emit `when`; `enforce()` fills the dates from it.
- [ ] 3. Dataset: cases pinned to a fixed clock (the harness gets a `now`), so
      "this weekend on a Saturday" is testable.
