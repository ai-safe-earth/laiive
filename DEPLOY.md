# Deploying laiive — Fly.io (services) + Cloudflare Pages (SPA)

Owner-run runbook for the first deploy (Phase 6, R2 second option: Fly).
Everything repo-side is already in place: `deploy/fly/*.toml`, `make
fly-deploy-*`, `frontend/public/_redirects`, the 202+poll sweep shape.
Data stays managed as-is (Neo4j Aura + Supabase). Budget guardrail:
$30–50/mo all-in — the five shared-cpu-1x machines below land ~$10–15/mo.

## 0. Prerequisites (one-time)

1. **Push the migration** `20260818000010_search_reports_lifecycle.sql`
   (new report statuses; the deployed search service inserts
   `status='running'`, which the old check constraint rejects):

   ```
   supabase db push --db-url "postgresql://postgres.pjlcfdyheyubsemwlzzv:<pw>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
   ```

2. `flyctl auth signup` / `login`; pick one org for all five apps
   (6PN private networking is org-scoped — the `.internal` names in the
   tomls only resolve inside the same org).

## 1. Create the apps + redis volume

```
flyctl apps create laiive-gateway
flyctl apps create laiive-retriever
flyctl apps create laiive-pusher
flyctl apps create laiive-search
flyctl apps create laiive-redis
flyctl volumes create redis_data --app laiive-redis --region mad --size 1
```

Names are load-bearing: the tomls and the gateway's `.internal` URLs use
them. Rename in both places or not at all.

## 2. Secrets per app

Non-secret config lives in each toml's `[env]`. Secrets via
`flyctl secrets set -a <app> KEY=value ...` — values from the root `.env`:

| app | keys |
| --- | --- |
| laiive-gateway | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `INTERNAL_API_KEY`, `CORS_ALLOW_ORIGINS` (the Pages domain, see §5) |
| laiive-retriever | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `OPENAI_API_KEY`, `INTERNAL_API_KEY`, `LANGFUSE_ENABLED` + `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` |
| laiive-pusher | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `OPENAI_API_KEY`, `INTERNAL_API_KEY` |
| laiive-search | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `INTERNAL_API_KEY` |
| laiive-redis | none (6PN-only; set `--requirepass` in `redis.toml`'s process + a `REDIS_URL` password everywhere if the org is ever shared) |

`INTERNAL_API_KEY` must be the **same value** on all four service apps —
it is the gateway↔service trust boundary now that no NetworkPolicy exists.
The containers have no root `.env` (configs read real env first, the file
is a local-dev fallback), so a missing key fails loudly at boot — that is
the signal a secret was forgotten.

## 3. Deploy (order matters once, for a clean first boot)

```
make fly-deploy-redis
make fly-deploy-retriever
make fly-deploy-pusher
make fly-deploy-search
make fly-deploy-gateway
```

The `services/` build context in the Makefile targets is required — the
Dockerfiles COPY `shared/` plus the service. Verify each app with
`flyctl checks list -a <app>` (`/livez`, gateway `/healthz`).

## 4. Cloudflare Pages (SPA)

Pages project → connect the GitHub repo:

- Root directory: `frontend` (the clone is the whole repo, so the
  `@shared` → `../services/shared/ts` alias resolves at build)
- Build command: `npm run build`  ·  Output: `dist`
- Env vars (build-time; the app throws at load if missing):
  `VITE_API_URL=https://laiive-gateway.fly.dev` (or the custom domain),
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`
- `public/_redirects` ships the SPA fallback; no wrangler.toml needed.

## 5. Stitch the origins together

1. Gateway: `flyctl secrets set -a laiive-gateway CORS_ALLOW_ORIGINS=https://<project>.pages.dev` (comma-append any custom domain).
2. Supabase Auth → URL configuration: add the Pages domain to redirect
   URLs (Google sign-in return leg).
3. Prefect: `serve.py` keeps running on the dev machine, now against the
   public gateway — set `GATEWAY_URL=https://laiive-gateway.fly.dev` in
   the root `.env`. (Containerizing serve.py stays optional, see handoff.)

## 6. Smoke checklist

- `curl https://laiive-gateway.fly.dev/healthz` → 200
- Direct service reach must fail: the apps have no public IPs (no
  `[http_service]`) — `flyctl ips list -a laiive-retriever` is empty.
- Browser chat on the Pages URL: anonymous "jazz in Barcelona" streams
  status → cards → prose (SSE through the Fly proxy).
- Admin sweep 202+poll: `POST /api/admin/search/sweep {"city":"Berlin","max_pages":2}`
  with an admin JWT → 202 + `report_id` in seconds; poll
  `GET /api/admin/search/reports/{id}` until `dry_run`.
- Phase 6 acceptance trace: take an `X-Request-Id` from a browser chat,
  find it in Supabase `conversation_logs` and in the Langfuse trace.

## Known limits (accepted for the first deploy)

- **Approve is still synchronous**: a large approve (N × embedding + the
  1 req/s geocode gate) can exceed the Fly proxy's ~60 s idle timeout.
  Approve in small batches; give approve the same 202+poll shape when it
  bites.
- **search kill_timeout is 300 s** (Fly's cap, under the image's 410 s
  window): a redeploy mid-sweep can kill the background sweep. The report
  stays `running`/`failed` and is never approvable; rerun the sweep.
- Scheduled flows still fire only while the dev machine is awake
  (`serve.py`); missed crons show Late in Prefect Cloud.
