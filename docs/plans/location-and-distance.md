---
status: active
step: retrieval
next: step 3, a "Share my location" button when a turn needs it
---
# Location and distance (feedback thread 2)

The biggest thread still failing after the 2026-10-09 replay: 31 of 87 turns read.
21 asked "near me" with no location shared. 10 named a place ("near Bergamo", "other
towns near Bergamo", "a bergamo?") and were read as "near me", so the v3 classifier asks
"your city or your location?" again. That last part is new in v3 and not released yet:
it must be fixed before the next release.

## What already exists
- The browser asks for the location once, silently, when the chat opens
  (`frontend/src/pages/Chat.tsx:52`). Denied or timed out: nothing happens.
- No location and "near me": the classifier asks for a place (`classifier.enforce`).
- With a location: `executor._execute_nearby` widens 5, 10, 15, 20, 30 km until 5 events.
- A place that is not a City node: geocoded with Nominatim (cached, 1 request a second),
  searched inside its box (`executor._execute_named_place`). The model never gives
  coordinates; it only names the place. That rule stays.
- Missing: widening around a named place, and a way to grant the location mid-chat.

## Design (owner, 2026-10-09)
The model extracts names only, as structured fields:
`{"city": "Montmartre", "parent": "Paris", "country_code": "FR", "radius_km": 5}`.
Nominatim turns the name into a point. Code does the distance search.

## Steps
- [x] 1. A named place is never "near me". Prompt: `near_me` only for the user's own
      position; "near X / around X / vicino a X" is the place X plus `radius_km`.
      `enforce()`: a sub-query that names a place drops `near_me`, so it never asks.
      Classifier cases from the 10 replayed turns. Prompt v4.
      2026-10-09: done. Four cases from the replay (English, Italian, a place answering
      "which city?", towns around a place); 24 of 24 green three runs in a row. The
      model skipped the default radius until the prompt showed two examples.
- [x] 2. Widen around a named place. Geocode the place (`parent` and `country_code` make
      the Nominatim query, so "Montmartre, Paris" never lands in Quebec), then run the
      same radius steps as near-me around that point. When: always for "near X", and when
      "in X" finds fewer than 5 events. The composer is told the distance ("these are
      within 15 km of Bergamo"). Cases: Ponteranica for "near Bergamo".
      2026-10-09: done in `executor._execute_around_place`. Live check (read-only): "near
      Bergamo" in English and Italian, and "other towns near Bergamo?", now bring events in
      Ranica and the reply names the town; "in Ponteranica" widens to Bergamo. Rock in
      Torino this week stays empty up to 50 km: that one is supply.
      Changes from the design: the centre of a city we hold is the graph's own City
      point, not Nominatim's, because Nominatim answers "Bergamo" with the province (98 km
      across, centred off the city). No `parent` field: the prompt already keeps the
      parent in the place name ("Kreuzberg, Berlin"), which is what Nominatim is asked.
      Near-me widening also goes up to 50 km now (same steps and cap).
- [x] 2b. Show more results (owner, 2026-10-09, after step 2: nearest-first with a limit
      of 10 crowded out the nearby towns). A search fetches up to 50 (`fetch_results_limit`);
      the composer still reads the first 10. `events.result` gains `capped` (optional, both
      sides of the protocol), so the count reads "50+". The chat shows 10 cards and a
      "Show 10 more (of 50+)" button; past 20 it adds "N events found, narrow it down by
      genre, distance or price", and the reply suggests the same. Chosen over server
      paging: one request, no state to keep, and a turn is never re-run to page.
      Live: "concerts in Bergamo this month" 50+ with the hint; "jazz in Bergamo" 12.
- [ ] 3. Ask for the location when it is needed. When a turn needs a location and has
      none, the stream sends `status` with state `needs_location` (the field is already
      a string: no protocol change). The chat shows a "Share my location" button under
      the reply; a tap asks the browser and, if granted, re-sends the same question with
      the location. Denied: the reply already asks for a city. Translations in en/es/it/ca.
- [ ] 4. Re-run the replay; the 31 turns should either answer or ask once, clearly.

## Decisions
- Owner, 2026-10-09: plan approved. Step `retrieval`, not `evals`. Location also touches
  pusher extraction and venue/event places in the graph; for now it is solved in the
  retriever only.
- `radius_km` cap goes from 30 to 50 km (step 2).
- "in X" also widens when it finds fewer than 5 events (step 2).
