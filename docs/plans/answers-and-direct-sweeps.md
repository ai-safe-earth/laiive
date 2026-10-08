---
status: active
step: supply
next: PR, then deploy retriever and search; run one sweep and check its writes with the census
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
- [ ] Deploy retriever and search; one Bergamo sweep; census before and after.

## Decisions
- Only driver connectivity errors short-circuit the composer. Other sub-query errors (no
  location for "near me") still compose, as `test_failed_subquery_still_composes` pins.
- The LLM-Cypher path reports errors through the query builder, so an outage there still
  composes. Template and vector paths, the common ones, are covered.
- Auto-write writes only `dedup_status == "new"`; "similar" and "exists" wait for a human.
  The kill switch is an env var so it can be flipped with a Fly secret, no deploy.
- Risk: extraction has written wrong and invented dates before (inkclub eval). Auto-write
  publishes those without a human look. Watch the first sweeps.
- Old dry-run reports in the queue are not auto-approved; `report-backlog.md` still owns them.
- "what's on in Torino this week?" returned 0 while Torino has 15 events in 14 days; probably
  all after Sunday. Not chased.
- Welcome questions are tied to cities that have events today; revisit as those pass.
