---
status: todo
step: retrieval
next: after follow-up-context, date ranges and event-data-quality (owner's order)
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

## Design (owner approved the closeness and claim rules, 2026-10-10)
- Similarity: embed each genre slug once (the embeddings model is already in use),
  store `(:Genre)-[:NEAR {score}]->(:Genre)` for the top few neighbours. Same family
  gets a floor. A small hand list overrides obvious misses (dj → electronic).
- Search: an exact genre first; when it finds fewer than 5, add the NEAR genres and
  say so in the notes ("no rock; here is punk and alternative").
- Artists: `(:Artist)-[:PLAYS]->(:Genre)`, filled from their events' genres, so a
  new event by a known artist gets a genre even when the page gave none.
- Owner, 2026-10-10: a claimed artist's genres are set only by the artist's
  manager or whoever is responsible for it; the job never overwrites them.
  Unclaimed artists get genres from their events.
- Owner, 2026-10-10: use a genre tree from the internet if useful. Pick: Wikidata
  music genres (`subclass of`, P279). Public domain (CC0), labels in en/es/it/ca,
  and IDs that link to MusicBrainz and Discogs. Rejected: MusicBrainz genres, whose
  genre data is non-commercial; FMA (161 genres, too coarse). Ceiling: Wikidata
  has several parents per genre and some loops, so we keep only the genres in our
  graph plus their parents, and break loops.
- Closeness = distance in that tree, adjusted by the genre-name embeddings.

## Steps
- [ ] 1. Protocol: `EventCard.genres` (TS mirror); the card shows up to two.
- [ ] 2. Artist genres from their events, unclaimed artists only; claimed artists
      get a genre field their manager edits (one write job; Aura write, owner's OK).
- [ ] 3. Import the Wikidata genre subset; build `NEAR` edges from tree distance
      plus embeddings, a check that dj/electronic and
      rock/punk come out close.
- [ ] 4. Retrieval: widen to close genres when few results, with a note.
- [ ] 5. Census: how many events and artists have no genre at all.
