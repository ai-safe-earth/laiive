---
status: todo
step: retrieval
next: run sub-queries in parallel and fuse with reciprocal rank fusion
---
# Retrieval accuracy (program phase 5)

No change ships without a recall or precision number from the evals step.

- [ ] `pipeline.run_turn` runs sub-queries serially. Run them in a thread pool (never
      `async def` around blocking work) and fuse with reciprocal rank fusion over time,
      distance, geocode precision, text and vector score.
- [ ] `router.route` picks one leg, and `free_text` beats structured constraints. A plan should
      carry several legs whose results fuse.
- [ ] Full-text index over event name/description and artist names, as its own leg.
- [ ] `QueryBuilderTool`: schema-aware few-shot, `EXPLAIN` before execute, one repair on
      error or zero rows, standard return shape (then delete `flexible_rows_to_cards`),
      cache by question shape.
- [ ] Empty-result ladder: drop the weakest constraint, widen dates, widen radius; report each
      rung through `Outcome.note`.
      Owner, 2026-10-10: when nothing matches, the reply says so plainly and suggests a
      concrete way to widen, from what the ladder found ("no rock in Torino this week;
      3 next week"). The replay's "rock in Torino" and "DJ in Bergamo" turns had no
      entries in the graph; today's reply says "none" but suggests blindly.
