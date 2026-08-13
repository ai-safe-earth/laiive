# 03 — Ontology: critique and proposal

The "designed and working" ontology was reconstructed from
`services/retriever/agent/scripts/setup_schema.py` + `seed.py` (untracked),
`services/pusher/agent/neo4j_writer.py` (untracked), and the LLM-facing contract in
`agent/tools/query_builder.py`. `FRONTEND_INTEGRATION.md` contradicts all of them and
is discarded. The live Aura instance `2099d44c` is empty; everything below was
validated against it read-only (`SHOW INDEXES`, `SHOW PROCEDURES` confirm vector-index
support). **No writes have been made.**

## 1. The existing model

Labels: `Event`, `Artist`, `Venue`, `City`, `Genre`, `Country`.
Relationships written in practice: `(Artist)-[:PERFORMS_AT]->(Event)`,
`(Event)-[:HOSTED_AT]->(Venue)`, `(Event|Artist)-[:HAS_GENRE]->(Genre)`,
`(Venue)-[:LOCATED_IN]->(City)`. Declared to the LLM but **never written**:
`(Artist)-[:BASED_IN]->(City)`, `(City)-[:PART_OF]->(Country)`.

## 2. Critique (each with why it matters)

1. **Identity is split three ways.** `setup_schema.py` makes `ra_id` unique;
   `neo4j_client.ensure_schema()` (tracked code!) instead makes `name` unique on
   Event/Artist/Venue/City and never mentions `ra_id`; two migration scripts key on an
   `id` property nothing ever writes. Consequence: whichever DDL ran last defines
   reality; the writer MERGEs Venue/Artist by raw `name` (case/diacritic-sensitive →
   "Café Berlin" and "Cafe Berlin" become two venues); events use `CREATE` with a fresh
   uuid → resubmission duplicates.
2. **Venues have no coordinates on the write path.** `neo4j_writer` never sets
   `Venue.location`; the radius search requires it. Every pro-submitted event is
   invisible to "near me". A modelling requirement (geo) was left to a seed script.
3. **Duplicate representations.** `Artist.genres` array vs `HAS_GENRE` edges;
   `city`/`country` string properties on Artist/Venue vs `LOCATED_IN`/`BASED_IN`
   edges. Two sources of truth guarantee drift and make Cypher generation ambiguous.
4. **Dead advertised relationships.** The LLM prompt tells the model `BASED_IN` and
   `PART_OF` exist; generated queries traverse edges with zero instances and silently
   return empty — indistinguishable from "no events".
5. **Type inconsistency on the hottest property.** `seed.py` writes `start_at` as a
   string; the writer as `datetime()`; the prompt asserts native DATETIME. String rows
   never match date filters.
6. **Genre nodes without names.** Writer MERGEs `Genre {slug}` only; anything reading
   `g.name` (embedding text, display) gets null.
7. **Price**: writer always sets `price_min == price_max`; the frontend types expect a
   `price_amount` that doesn't exist. Keep min/max (ranges are real) and fix consumers.
8. **Embeddings written, never queryable** — no vector index, no read path, and the
   schema fed to the LLM strips `embedding`. Cost with zero benefit.
9. **Expensive/awkward query paths**: "venue type" (club vs arena…) is unexpressible —
   no property models it; "events in a country" requires string matching on
   `Venue.city`→? (no path); artist similarity has no support beyond shared genre.
10. **No provenance/ownership model** beyond a single `source` string on Event —
    requirement now: pro vs admin-search provenance on everything, plus `owner_id`.

## 3. Proposed model

### Nodes and properties

| Label | Identity | Properties |
|---|---|---|
| `Event` | `uid` (UUID, unique) | `name`, `name_norm`, `description`, `start_at`/`end_at` (**datetime, always**), `price_min`, `price_max`, `price_currency`, `ticket_url`, `status` (`scheduled|cancelled|past`), `source` (`pro_submission|admin_search|seed`), `owner_id` (Supabase UUID, null for admin_search), `created_at`, `updated_at`, `embedding`, `embedding_text` |
| `Artist` | `uid`; MERGE key `name_norm` | `name`, `name_norm`, `description`, `spotify_id?`, `source`, `owner_id?`, `created_at`, `embedding`, `embedding_text` |
| `Venue` | `uid`; MERGE key `name_norm` + city | `name`, `name_norm`, `venue_type` (`club|bar|concert_hall|arena|festival_site|open_air|other`), `address`, `location` (**point, required on write — geocoded**), `capacity?`, `source`, `owner_id?`, `created_at`, `embedding`, `embedding_text` |
| `City` | MERGE key `name_norm` + `country_code` | `name`, `name_norm`, `country_code` (ISO-3166-1), `country_name`, `location` (point, centroid) |
| `Genre` | `slug` (unique) | `slug`, `name` |

`name_norm` = lowercase, trimmed, diacritics stripped — the MERGE key that stops
"Café Berlin"/"cafe berlin" duplication. `uid` is the stable external identifier
(cards, ownership, cross-store references).

**Country stays a property on City** (`country_code`), not a node: every
country-level question ("events in Spain") is `MATCH …-[:LOCATED_IN]->(c:City {country_code:'ES'})`
— one property filter instead of an extra hop, and there is no country-level metadata
to hang on a node. Revisit only if country entities acquire their own data.

### Relationships

```
(Artist)-[:PERFORMS_AT]->(Event)          # lineup; multiple artists per event
(Event)-[:HOSTED_AT]->(Venue)             # exactly one
(Venue)-[:LOCATED_IN]->(City)
(Artist)-[:BASED_IN]->(City)              # now actually written when known
(Event)-[:HAS_GENRE]->(Genre)
(Artist)-[:HAS_GENRE]->(Genre)
```
Dropped: `Country` node + `PART_OF`; `Artist.genres` array; `city`/`country` string
properties on Artist/Venue. One representation per fact.

### Why this supports the required question set (user's point of view)

| Question | Path |
|---|---|
| an event | `Event` by name_norm / vector kNN on `embedding` |
| events in a place | `(:Event)-[:HOSTED_AT]->(:Venue)-[:LOCATED_IN]->(:City)` or `point.distance(v.location, $p)` |
| events on a date | range index on `Event.start_at` |
| events of an artist | `(:Artist)-[:PERFORMS_AT]->(:Event)` |
| events of similar artists | genre overlap (2 hops) **and/or** `db.index.vector.queryNodes('artist_embedding', k, a.embedding)` |
| events in a type of venue | `Venue.venue_type` (indexed) |
| events of a genre | `(:Event)-[:HAS_GENRE]->(:Genre)` plus artist-genre fallback |

## 4. Schema DDL (to run on 2099d44c — **only after explicit approval**)

```cypher
// ---- Constraints (identity) ----
CREATE CONSTRAINT event_uid    IF NOT EXISTS FOR (e:Event)  REQUIRE e.uid  IS UNIQUE;
CREATE CONSTRAINT artist_uid   IF NOT EXISTS FOR (a:Artist) REQUIRE a.uid  IS UNIQUE;
CREATE CONSTRAINT venue_uid    IF NOT EXISTS FOR (v:Venue)  REQUIRE v.uid  IS UNIQUE;
CREATE CONSTRAINT genre_slug   IF NOT EXISTS FOR (g:Genre)  REQUIRE g.slug IS UNIQUE;
CREATE CONSTRAINT event_name_nn  IF NOT EXISTS FOR (e:Event)  REQUIRE e.name IS NOT NULL;
CREATE CONSTRAINT artist_name_nn IF NOT EXISTS FOR (a:Artist) REQUIRE a.name IS NOT NULL;
CREATE CONSTRAINT venue_name_nn  IF NOT EXISTS FOR (v:Venue)  REQUIRE v.name IS NOT NULL;
CREATE CONSTRAINT city_key     IF NOT EXISTS FOR (c:City)
  REQUIRE (c.name_norm, c.country_code) IS NODE KEY;   // needs Aura Professional+;
                                                       // fallback: UNIQUE + NOT NULLs

// ---- Range / lookup indexes ----
CREATE INDEX event_start_at   IF NOT EXISTS FOR (e:Event)  ON (e.start_at);
CREATE INDEX event_status     IF NOT EXISTS FOR (e:Event)  ON (e.status);
CREATE INDEX event_source     IF NOT EXISTS FOR (e:Event)  ON (e.source);
CREATE INDEX event_name_norm  IF NOT EXISTS FOR (e:Event)  ON (e.name_norm);
CREATE INDEX artist_name_norm IF NOT EXISTS FOR (a:Artist) ON (a.name_norm);
CREATE INDEX venue_name_norm  IF NOT EXISTS FOR (v:Venue)  ON (v.name_norm);
CREATE INDEX venue_type       IF NOT EXISTS FOR (v:Venue)  ON (v.venue_type);
CREATE INDEX city_country     IF NOT EXISTS FOR (c:City)   ON (c.country_code);

// ---- Point indexes (geo) ----
CREATE POINT INDEX venue_location IF NOT EXISTS FOR (v:Venue) ON (v.location);
CREATE POINT INDEX city_location  IF NOT EXISTS FOR (c:City)  ON (c.location);

// ---- Vector indexes (hybrid search) ----
CREATE VECTOR INDEX event_embedding IF NOT EXISTS
FOR (e:Event) ON (e.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX artist_embedding IF NOT EXISTS
FOR (a:Artist) ON (a.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX venue_embedding IF NOT EXISTS
FOR (v:Venue) ON (v.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
```

`db.index.vector.createNodeIndex` / `queryNodes` confirmed present on the instance.

## 5. Embeddings

- Model: **`text-embedding-3-small`**, dimension **1536**, similarity **cosine**.
  Rationale: 5× cheaper than 3-large, quality is ample for event/artist/venue blurbs,
  and it's what every existing code path already assumes — zero migration. Upgrade
  path: 3-large at 1536 via the `dimensions` parameter without re-indexing config.
- One embedding module (shared text builders), storing `embedding_text` alongside so
  re-embedding after model changes is a pure batch job.
- `embedding_text` recipes: Event = name + date + venue + city + genres + description;
  Artist = name + genres + city + description; Venue = name + type + city + address.

## 6. Example multi-hop queries (parameterized)

Events by similar artists (graph leg):
```cypher
MATCH (a:Artist {name_norm: $artist})-[:HAS_GENRE]->(g:Genre)<-[:HAS_GENRE]-(sim:Artist)
WHERE sim <> a
WITH sim, count(g) AS shared ORDER BY shared DESC LIMIT 15
MATCH (sim)-[:PERFORMS_AT]->(e:Event)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)
WHERE e.start_at >= datetime() AND e.status = 'scheduled'
RETURN e, v, c, collect(sim.name) AS similar_artists
ORDER BY e.start_at LIMIT 10
```

Events by similar artists (vector leg, fused with the above by the retriever):
```cypher
MATCH (a:Artist {name_norm: $artist})
CALL db.index.vector.queryNodes('artist_embedding', 10, a.embedding)
YIELD node AS sim, score
WHERE sim <> a
MATCH (sim)-[:PERFORMS_AT]->(e:Event)
WHERE e.start_at >= datetime()
RETURN e, sim.name AS artist, score ORDER BY score DESC, e.start_at LIMIT 10
```

Tonight, near me, by venue type:
```cypher
MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)
WHERE v.venue_type = $venue_type
  AND point.distance(v.location, point({latitude: $lat, longitude: $lng})) <= $radius_m
  AND e.start_at >= datetime($tonight_start) AND e.start_at < datetime($tonight_end)
OPTIONAL MATCH (a:Artist)-[:PERFORMS_AT]->(e)
RETURN e, v, collect(a.name) AS artists,
       point.distance(v.location, point({latitude: $lat, longitude: $lng})) AS d
ORDER BY d LIMIT 10
```

Genre in a country next weekend:
```cypher
MATCH (e:Event)-[:HAS_GENRE]->(:Genre {slug: $genre}),
      (e)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City {country_code: $cc})
WHERE e.start_at >= datetime($from) AND e.start_at < datetime($to)
RETURN e, v, c ORDER BY e.start_at LIMIT 20
```

Semantic free-text ("intimate candle-lit jazz"):
```cypher
CALL db.index.vector.queryNodes('event_embedding', 20, $query_embedding)
YIELD node AS e, score
MATCH (e)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)
WHERE e.start_at >= datetime() AND score >= 0.75
RETURN e, v, c, score ORDER BY score DESC LIMIT 10
```

## 7. Migration note

The old instance (`5ce2d474`) is dead and the new one is empty — there is **no data
migration**. `embedings_migration.py` and `agent/embedings.py` are obsolete leftovers
of the previous instance (they key on a property that no longer exists) and are
deleted, not ported. `seed.py` gets adapted to this model as the dev fixture.
