---
status: done
step: retrieval
next: none; the owner merges #144, #145, then this PR
---

# The agent always knows place, day and hour

Follow-up from `done/location-and-distance.md`. The owner's rule (2026-10-09):
the agent must know three things on every turn: place, day and hour.

- A turn that names a place runs without the user's location.
- A turn that needs the user's location asks for it (type a town, or the
  "Share my location" button). That covers "near me" and also a turn that says
  nothing about where, e.g. "events today".

## Today

- Day: the classifier gets the date and weekday. It does not get the hour, so
  "what's on now" or "later tonight" has no anchor. The composer gets neither.
- Place: "near me" with no location asks (done). A turn with no place and no
  location ("events today") runs over the whole graph and mixes every city.
- The composer is not told whether a location was shared, so "do you have my
  location?" gets a generic answer.

## Steps

- [x] 1. A turn with no place asks for one. In `enforce()`: no location shared,
      and a search sub-query has no city, country, venue or artist → treat it as
      near me (`near_me = True`). The existing rule then makes the turn ask, and
      the pipeline sends `needs_location`, so the button shows. Once a location is
      shared, the same sub-query runs as a nearby search.
- [x] 3b. Once per session, the chat offers to share the location (owner,
      2026-10-10): the first finished reply without a location gets a
      "Share my location for events near you" button. A reply that needs the
      location keeps its own button. Frontend only: `offerAt` in `Chat.tsx`.
- [x] 2. The classifier gets the hour: `Today is {date} ({weekday}), {HH:MM}`.
      Prompt v5, dataset pinned to v5.
- [x] 3. The composer gets one line on what it knows: date and hour, and either
      "location shared" or "no location shared". It goes through the existing
      retrieval notes, so no signature change. This fixes "do you have my
      location?".
- [x] 4. Tests: `enforce()` unit tests, two classifier dataset cases ("events
      today" with and without a location), one composer case for "do you have my
      location?". Replay the location thread again.
      Done 2026-10-10: classifier 26/26 three runs in a row, composer 11/11.
      Replay: 10/10 named places answer, 19/21 near-me ask with the button,
      and the 2 questions about the location now say it is not shared and
      suggest typing a town (before: a generic out-of-scope line).

## Decisions

- An artist or a venue counts as a place. "When does Klangfeld play?" needs no
  location: the router already refuses to cut such asks to a circle
  (`router._implicitly_nearby`).
- A country counts as a place ("concerts in Spain").
- Rule in code (`enforce()`), not prompt wording: the prompt can drift, the rule
  cannot.
- Owner, 2026-10-10: plan approved; artist, venue and country count as a place.
- Owner, 2026-10-10: beyond searches, offer location access once per session,
  without insisting. Chosen shape: the chat decides, not the model. The model
  is told "never insist"; the button shows once, on the first finished reply.
  "Session" is the open chat page: a reload offers again. Rejected: a server
  flag, because the server keeps no session.
- The place-day-hour line rides in the composer's retrieval notes, so it is
  also in the trace for every turn.
