---
status: todo
step: evals
next: owner approves the design, then step 1 (a named place is never "near me")
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
- [ ] 1. A named place is never "near me". Prompt: `near_me` only for the user's own
      position; "near X / around X / vicino a X" is the place X plus `radius_km`.
      `enforce()`: a sub-query that names a place drops `near_me`, so it never asks.
      Classifier cases from the 10 replayed turns. Prompt v4.
- [ ] 2. Widen around a named place. Geocode the place (`parent` and `country_code` make
      the Nominatim query, so "Montmartre, Paris" never lands in Quebec), then run the
      same radius steps as near-me around that point. When: always for "near X", and when
      "in X" finds fewer than 5 events. The composer is told the distance ("these are
      within 15 km of Bergamo"). Cases: Ponteranica for "near Bergamo".
- [ ] 3. Ask for the location when it is needed. When a turn needs a location and has
      none, the stream sends `status` with state `needs_location` (the field is already
      a string: no protocol change). The chat shows a "Share my location" button under
      the reply; a tap asks the browser and, if granted, re-sends the same question with
      the location. Denied: the reply already asks for a city. Translations in en/es/it/ca.
- [ ] 4. Re-run the replay; the 31 turns should either answer or ask once, clearly.

## Decisions to take
- `radius_km` cap: 30 km today (`location_max_radius_km`), so "near Bergamo (50 km)"
  is cut to 30. Raise to 50?
- Widen "in X" when it finds fewer than 5 events, or only on "near X" asks?
