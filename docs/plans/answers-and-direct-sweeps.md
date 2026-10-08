---
status: active
step: supply
next: merge the language-rule PR, deploy search, check the next sweep writes no English twins
---
# Answers when the graph is thin or down, and sweeps that write directly

The chat answered nothing on 2026-10-08. Cause: Aura Free had paused (its DNS record was
gone), and the composer turned "graph unreachable" into "a quiet spell in Barcelona".

## Steps
- [x] 1. Census the live graph once Aura was resumed (190 events, 48 upcoming, 19 in the next
  14 days: Torino 15, Barcelona 2, Bergamo 1; only 11 upcoming events carry a genre).
- [x] 2. An unreachable graph is an outage: the executor marks driver ServiceUnavailable /
  SessionExpired as `unavailable`; when every sub-query is unavailable and nothing was found,
  the pipeline sends `error` code `graph_unavailable` and skips the composer. The chat shows
  `chat.graphUnavailable` in the reader's language.
- [x] 3. Welcome questions widened (city or time span, no genre), each tested on production in
  en/es/it/ca: 2 to 10 events each.
- [x] 4. `services/retriever/agent/scripts/census.py`: read-only counts, any time.
- [x] 5. Sweeps write their "new" candidates when they finish (`SEARCH_SWEEP_AUTO_WRITE`,
  default true), through the same claim-then-write path as a human approve.
- [x] Deploy retriever and search; one Bergamo sweep; census before and after.
  2026-10-08, report `3a22bbc9`: 136 candidates, 132 new, 131 written, 1 invalid (no venue).
  Events 190 -> 321; upcoming 48 -> 179; Bergamo upcoming 5 -> 106 (48 in 14 days).
- [x] Duplicates got through: ~20 clear same-night pairs (same name twice, or en/it twins from
  visitbergamo.net `/en/eventi` vs `/eventi`), because the writer's probe keys on name + venue +
  date and the two copies carry different venues ("Bergamo" vs the real hall).
  Owner (2026-10-08): auto-write stays on; the twins stay in the graph, to be studied from logs.
- [x] 6. Sweep dedup widened, search service only: a language-twin page (`/en/…` beside `/…`)
  is never extracted; within a sweep, same name + day + city is one event and the copy with a
  real venue is kept; against the graph, `probe_duplicate` also matches same name + day
  anywhere in the city. Checked read-only on the live graph: Niklas Jahn and Harlem Gospel
  Choir now read "exists" from another venue, the same name in Torino stays "new".
- [x] Deploy search; next sweep should show "exists" for today's events.
  Report `ab5c9325`: 107 candidates, 83 exists, 12 similar, 12 new; 11 written. Events
  321 -> 332, Bergamo upcoming 106 -> 113. But 4 of the 11 were English twins: search found
  only visitbergamo's `/en/eventi`, so no twin page was in the sweep, and the English names
  scored under 0.92 against the Italian copies.
- [x] 7. Language rule: a page with a foreign language segment (`/en/…`) is swapped for the
  site's own (`/…`) through Tavily extract, after the max_pages cut; a failed fetch keeps the
  original. Checked live: `/en/eventi` -> `/eventi`, 12,210 chars, Italian names.
- [ ] Deploy search; next sweep should write no English twins.

## Findings from the first direct sweep
- ARCI portal events are national, but the writer geocoded them to their real cities (Padova,
  Seregno, Milano, Genova). Off-target for a Bergamo sweep, not wrong.
- Non-music got in: stand-up comedy, a musical, karaoke, a swap party.
- `livemusicdieci10.it` dates land at 00:00 (date-only); "Trovesi & Remondini" has two dates
  across two sources.

## Decisions
- Only driver connectivity errors short-circuit the composer. Other sub-query errors (no
  location for "near me") still compose, as `test_failed_subquery_still_composes` pins.
- The LLM-Cypher path reports errors through the query builder, so an outage there still
  composes. Template and vector paths, the common ones, are covered.
- The wider dedup lives in the search service, not the shared writer: a promoter is never
  refused because a listing elsewhere in town shares their event's name. Known ceiling: two
  shows with one generic name ("TRIBUTO") on one day in one city collapse to one.
- Translated twins from two different sites (not language paths of one site) are still only
  caught by the embedding "similar" check.
- Auto-write writes only `dedup_status == "new"`; "similar" and "exists" wait for a human.
  The kill switch is an env var so it can be flipped with a Fly secret, no deploy.
- Risk: extraction has written wrong and invented dates before (inkclub eval). Auto-write
  publishes those without a human look. Watch the first sweeps.
- Old dry-run reports in the queue are not auto-approved; `report-backlog.md` still owns them.
- "what's on in Torino this week?" returned 0 while Torino has 15 events in 14 days; probably
  all after Sunday. Not chased.
- Welcome questions are tied to cities that have events today; revisit as those pass.
