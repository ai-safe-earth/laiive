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
(nightly).

**Scheduling runs via `flows/serve.py`**, not `prefect deploy` — the scheduling
rethink (handoff.md, 2026-08-17): a managed work pool has no private networking
and needed a public gateway URL plus a `github-laiive-pat` Secret block, neither
of which exist pre-deploy. `serve()` registers both deployments' cron schedules
with Prefect Cloud and then blocks in this process, executing runs locally
against whatever `GATEWAY_URL` resolves to. No work pool, no worker, no PAT, no
image. The root `prefect.yaml` (`git_clone` + managed pool) stays in the repo,
dormant, for when Phase 6 deploys a public gateway and that path is worth
reviving.

Setup, in order:

1. Provision the service account (writes to Supabase — owner runs it):
   `uv run --env-file ../../.env python scripts/create_admin_user.py --email <email>`
2. Either set env vars directly (`GATEWAY_URL`, `SUPABASE_ADMIN_EMAIL`,
   `SUPABASE_ADMIN_PASSWORD`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` — root
   `.env` already has all of these), or put the non-secret ones in Prefect
   Variables (`laiive_gateway_url`, `laiive_supabase_url`,
   `laiive_supabase_publishable_key`) and the credentials in Secret blocks
   (`supabase-admin-email`, `supabase-admin-password`) — env wins when both are
   present.
3. `uv run --group flows python flows/serve.py`, with the gateway
   (`SEARCH_ENABLED=true`) and this service running. Long-lived process; run it
   under whatever keeps a process alive on your box (systemd, a compose
   `restart: unless-stopped` service, `pm2`, ...).

**Verified live 2026-08-17**: `serve()` registered `city-sweep-weekly` and
`backfill-nightly` in Prefect Cloud; `prefect deployment run
'backfill/backfill-nightly'` from a second shell created a Cloud flow run that
the local `serve()` process picked up, executed against the local gateway, and
completed in ~7s — the whole point of the rethink, proven end to end.

Ad hoc local run without touching schedules: `uv run --env-file ../../.env`
with the same env vars, then `python flows/city_sweep.py` directly.
