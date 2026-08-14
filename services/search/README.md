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

## Prefect flows (Phase 5b, D17)

`flows/` are thin HTTP clients of the public gateway — they sign in as a
Supabase admin service account (password grant per run) and never reach this
service or the graph directly. `city_sweep` (weekly, one task per city,
markdown artifact as the review surface — sweeps stay dry-run) and `backfill`
(nightly). Schedules live in the root `prefect.yaml`; deploy with
`prefect deploy --all` from the repo root.

Setup, in order:

1. Provision the service account (writes to Supabase — owner runs it):
   `uv run --env-file ../../.env python scripts/create_admin_user.py --email <email>`
2. Prefect Cloud: create a managed work pool `laiive-managed`; Secret blocks
   `supabase-admin-email`, `supabase-admin-password`, `github-laiive-pat`
   (read-only PAT for the repo clone); Variables `laiive_gateway_url`,
   `laiive_supabase_url`, `laiive_supabase_publishable_key`.
3. `prefect deploy --all`.

Local dry run without Prefect Cloud (env beats blocks/variables):
`uv run --env-file ../../.env` with `GATEWAY_URL`, `SUPABASE_ADMIN_EMAIL`,
`SUPABASE_ADMIN_PASSWORD` set, then `python flows/city_sweep.py` against the
live local stack (gateway with `SEARCH_ENABLED=true`).
