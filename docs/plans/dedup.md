---
status: blocked
step: supply
next: owner reviews services/pusher/evals/dedup_review.csv
---
# Dedup (pro settings phase 4)

## Steps
- [ ] Owner fills `verdict` + `should_instead` for the 52 cases in
      `services/pusher/evals/dedup_review.csv`.
- [ ] Convert to `datasets/dedup/test_cases.json`, the acceptance suite.
- [ ] Fix adoption through chat: nameless drafts get derived names, so the exact
      `name_norm` key misses.
- [ ] Venues too (owner, 2026-10-10): "Chorus Life Arena" and "ChorusLife Arena" are
      two venue nodes, so each spelling finds half the events. The `name_norm` key keeps
      spaces; compare without them, and merge the pair (Aura write, owner's OK).
- [ ] Events seen twice in the 2026-10-10 replay (same show, two uids): a Francesco
      Motta concert, Niklas Jahn, a Fabrizio De André tribute. Add them to the review set.
