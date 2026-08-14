# search

Admin-triggered internet event discovery (Phase 5). Internal on :8004, reached
only via the gateway's `/api/admin/search/*` (admin JWT, `SEARCH_ENABLED=true`).

Pipeline: Tavily search per city → LLM extraction (`gpt-4o-mini`, `gpt-4o`
fallback) → dedup against the graph (identity probe + vector similarity) →
dry-run report persisted in Supabase `search_reports`. `POST /reports/{id}/approve`
replays the stored report through `laiive_shared.neo4j_writer` with
`source='admin_search'` — the only write path.

Endpoints: `POST /sweep` · `GET /reports` · `GET /reports/{id}` ·
`POST /reports/{id}/approve` · `POST /backfill` (embeddings + venue locations,
bounded) · `GET /health`.

Run: `cd services/search && uv run uvicorn agent.api:app --port 8004` (root
`.env` needs `TAVILY_API_KEY`, Supabase service-role, Neo4j, OpenAI keys).
Tests: `uv run pytest`.

Prefect flows (`flows/`) are thin HTTP clients of the public gateway (D17) —
they sign in as a Supabase admin service account and never reach this service
or the graph directly.
