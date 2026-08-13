# laiive-shared

Shared contracts and write path for the laiive services (docs/refactor/02-architecture.md §2, 05-decisions D10).

- `protocol.py` — typed SSE protocol: payload models + `sse_frame()` serializer. The TS mirror lives in `ts/protocol.ts`; `tests/test_ts_contract.py` fails if they drift.
- `cards.py` — `EventCard` (retriever → frontend) and `EventDraft` (pusher form / batch rows).
- `normalize.py` — `norm()` (MERGE identity key) and `genre_slug()`.
- `embedding_text.py` — the composite text recipes for Event/Artist/Venue embeddings (03-ontology §5).
- `geocode.py` — Nominatim geocoder with cache and 1 req/s politeness (D12).
- `neo4j_writer.py` — MERGE-by-identity event write with dedup probe, provenance (`source`, `owner_id`), geocoded venue location, and embedding backfill. The only code path allowed to write domain nodes.

Installed editable in each Python service: `uv add --editable ../shared`.
