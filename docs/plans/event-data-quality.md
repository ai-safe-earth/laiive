---
status: todo
step: supply
next: owner picks the roadmap step, then step 1
---
# Event data quality: unknown times and event names

From the 2026-10-10 feedback replay (wrong-event-data thread).

## Owner decisions (2026-10-10)
- A time the page did not give is shown as "time unknown", never as 00:00.
- An event without its own name is named after the artist only, never
  artist + venue.

## Today
- The writer stores a missing time as 00:00, so the card says 00:00 and the user
  thinks the show starts at midnight.
- Extraction sometimes builds the name from artist + venue.

## Steps
- [ ] 1. Writer (`laiive_shared/neo4j_writer.py`): store whether the time is known
      (`time_known: false` when only a date was found). Extraction says which.
- [ ] 2. Protocol: `EventCard.time_known` (optional, TS mirror). The card shows the
      date and "time unknown" in en/es/it/ca.
- [ ] 3. Name rule at validation (`/validate-event`): no event name → the artist
      name(s). Strip a trailing " at/a/en <venue>" from a name that repeats the venue.
- [ ] 4. Backfill: mark existing 00:00 events with no time on the source page.
      Aura write: the owner's OK first. Real midnight shows (DJ sets) must keep
      their time, so the backfill checks the page or the source, not the clock.
- [ ] 5. Cases from truth: per the memory rule, check drafts against the pages,
      including a stale one, not against draft counts.
