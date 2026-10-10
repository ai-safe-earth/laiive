---
status: todo
step: retrieval
next: owner approves the similarity design, then step 1
---
# Genres on cards, on artists, and close genres

Owner, 2026-10-10: cards must show the genre; artists carry genre labels; a
similarity between genres lets the chat offer genres close to what was asked.

## Today
- Cards show no genre, so a mixed "jazz and rock" list cannot be told apart.
- `laiive_shared.normalize` has `GENRE_ALIASES` (spellings) and `genre_family`
  (a coarse family). Nothing ranks how close two genres are.
- "DJ sets in Bergamo" found nothing: unclear if those events are missing or
  tagged under another genre ("electronic", "house").

## Design (proposed)
- Similarity: embed each genre slug once (the embeddings model is already in use),
  store `(:Genre)-[:NEAR {score}]->(:Genre)` for the top few neighbours. Same family
  gets a floor. A small hand list overrides obvious misses (dj → electronic).
- Search: an exact genre first; when it finds fewer than 5, add the NEAR genres and
  say so in the notes ("no rock; here is punk and alternative").
- Artists: `(:Artist)-[:PLAYS]->(:Genre)`, filled from their events' genres, so a
  new event by a known artist gets a genre even when the page gave none.
- Rejected: a hand-made full genre tree. Too much upkeep at our size.

## Steps
- [ ] 1. Protocol: `EventCard.genres` (TS mirror); the card shows up to two.
- [ ] 2. Artist genres from their events (one write job; Aura write, owner's OK).
- [ ] 3. Genre similarity: build `NEAR` edges, a check that dj/electronic and
      rock/punk come out close.
- [ ] 4. Retrieval: widen to close genres when few results, with a note.
- [ ] 5. Census: how many events and artists have no genre at all.
