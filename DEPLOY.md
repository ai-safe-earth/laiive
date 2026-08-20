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
flyctl volumes create redis_data --app laiive-redis --region fra --size 1
```

Names are load-bearing: the tomls and the gateway's `.internal` URLs use
them. Rename in both places or not at all.

## 2. Secrets per app

Non-secret config lives in each toml's `[env]`. The whole table below is
scripted — `make fly-secrets-check` reports missing key *names* without
touching Fly, `make fly-secrets` stages every app's secrets from the root
`.env` (`deploy/fly/set-secrets.sh`, no value is ever printed). Do it by
hand with `flyctl secrets set -a <app> KEY=value ...` if you prefer:

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

- **Production branch: `main`** (`develop` and every PR then get preview
  builds automatically — that is the point of the two-branch model, see
  `CONTRIBUTING.md`). The default branch is `develop`, so Pages will offer
  that one first; change it.
- Root directory: `frontend` (the clone is the whole repo, so the
  `@shared` → `../services/shared/ts` alias resolves at build)
- Build command: `npm run build`  ·  Output: `dist`
- Env vars (build-time; the app throws at load if missing):
  `VITE_API_URL=https://laiive-gateway.fly.dev` (or the custom domain),
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`
- `public/_redirects` ships the SPA fallback; no wrangler.toml needed.

## 4b. laiive.com as the custom domain

The domain was registered through **Piensa Solutions** (`ns21`/`ns22.piensasolutions.com`)
and pointed at the pre-refactor Lovable build. Two facts decide the shape of the move.

**`laiive.com` carries live email** — `MX 10 mx.buzondecorreo.com`. A nameserver change
that does not recreate that record kills mail silently: no bounce to you, no error
anywhere, senders just stop arriving. Verify it before the flip, not after.

**A bare apex cannot CNAME.** DNS forbids it, so Pages cannot serve `laiive.com` from
the registrar's zone unless Piensa offers `ALIAS`/`ANAME`. Cloudflare fakes it with
CNAME flattening, which is why the nameservers move rather than one record.

Order matters — each step is only safe once the previous one is true:

1. Add `laiive.com` as a site in Cloudflare. It scans the existing zone and copies
   what it finds.
2. **Check the import before going further.** `MX → mx.buzondecorreo.com` must be
   present, along with any SPF/DKIM `TXT`. Add by hand anything the scan missed.
3. Change the nameservers at Piensa to the pair Cloudflare assigns. Propagation is
   hours; Cloudflare shows the zone as *Active* when it is done. **The Lovable site
   goes dark at this point** — that is the cutover, and it is immediate.
4. Pages project → Custom domains → add `laiive.com` and `www.laiive.com`.
5. Then §5 below, with `https://laiive.com` in the origin list. Until the gateway
   knows the origin, the site loads and every request fails CORS.

The gateway stays on `laiive-gateway.fly.dev`; `VITE_API_URL` does not change. An
`api.laiive.com` would need a Fly certificate, its own DNS record and a Pages
rebuild — another moving part in the same cutover, for a hostname only visible in
the network tab.

`index.html`'s `og:image` and `twitter:image` are absolute (Open Graph requires it)
and point at `laiive.com`. They resolve only once step 4 is done, so that change
ships with the cutover, not before it.

## 5. Stitch the origins together

1. Gateway CORS. **`flyctl secrets set` replaces a key, it never appends** — every
   origin goes in one comma-separated value, or the last command silently
   locks out the ones before it:

   ```
   flyctl secrets set -a laiive-gateway \
     CORS_ALLOW_ORIGINS="https://laiive.pages.dev,https://develop.laiive.pages.dev"
   ```

   The preview origin is worth carrying: Pages builds `develop` at
   `develop.<project>.pages.dev`, and without it a preview cannot call the
   gateway at all. Verify with a preflight rather than by reading the output —
   `curl -X OPTIONS <gateway>/api/chat -H "Origin: …" -H "Access-Control-Request-Method: POST"`
   answers with `access-control-allow-origin` only for an allowed origin.
2. Supabase Auth → URL configuration: add the Pages domain to redirect
   URLs (Google sign-in return leg).
3. Prefect: `serve.py` keeps running on the dev machine, now against the
   public gateway — set `GATEWAY_URL=https://laiive-gateway.fly.dev` in
   the root `.env`. (Containerizing serve.py stays optional, see handoff.)

## 5b. Auth branding (the Google consent screen)

Signing in with Google shows "continue to **pjlcfdyheyubsemwlzzv.supabase.co**",
because Google displays the root domain of the *callback* URL — which belongs to
Supabase, not to laiive. Supabase's own docs call this out: it "does not inspire
trust and can make your application more susceptible to successful phishing
attempts". Two fixes, and they are not equivalent.

**Free, do this first — brand verification.** Google Cloud Console → APIs &
Services → OAuth consent screen → Branding: app name `laiive`, the lips logo,
a support email, and `laiive.com` under authorized domains. Submit for
verification; it is reviewed by a human and takes a few business days. Result:
the name and logo replace the project id.

**Paid, later — a Supabase custom domain.** `auth.laiive.com` as the project's
domain, so the callback itself is laiive-branded. It is an add-on on a paid
plan (Pro $25/mo + $10/mo for the domain), which is most of the $30–50/mo
budget guardrail spent on cosmetics — worth revisiting when there is a paid
plan for other reasons. DNS: a CNAME to the project domain plus a TXT at
`_acme-challenge.auth.laiive.com`.

If that day comes, three things move together or sign-in breaks:

1. Register **both** callback URLs with Google before activating, per Supabase's
   docs — the old `<ref>.supabase.co/auth/v1/callback` and the new one.
2. `VITE_SUPABASE_URL` in Cloudflare Pages, and a rebuild.
3. **The gateway's JWT verification.** `services/gateway/src/config.ts` derives
   both the JWKS URL and the expected issuer from `SUPABASE_URL`
   (`${supabaseUrl}/auth/v1`). Tokens minted by the custom domain carry the new
   issuer, so every request 401s until `SUPABASE_URL` moves too — and tokens
   issued just before the switch carry the old one. `SUPABASE_JWKS_URL` and
   `SUPABASE_JWT_ISSUER` exist as explicit overrides for exactly this window.

Sources and access dates: `docs/references.md`.

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
