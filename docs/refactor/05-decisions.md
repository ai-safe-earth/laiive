# 05 — Decisions

## Already decided (user-confirmed 2026-08-13)

| # | Decision | Choice |
|---|---|---|
| D1 | Frontend | Fresh Vite + React + TS + Tailwind + shadcn app; port tokens/translations/SSE/recorder; SSR deferred (React Router 7 framework mode or a separate public-pages site when SEO pages become a requirement) |
| D2 | Auth provider | **Supabase** (already integrated, free at this scale, Postgres+RLS fits ownership; Auth0 revisited only if enterprise SSO/MFA demands appear) |
| D3 | User/pro/ownership data | **Supabase Postgres** with RLS; graph nodes carry `owner_id` references |
| D4 | Leaked key in git history | **Rotate keys only** (OpenAI + Aura + Langfuse); no history rewrite while both remotes stay private |

## Decided 2026-08-13 (from 06-questions answers)

| # | Decision | Choice |
|---|---|---|
| D5 | Product scope | Chat-only; no public crawlable pages yet |
| D6 | Chat language | Assistant adapts to the user's language (no fixed list); UI chrome in en/es/it/ca via profile setting + signup choice |
| D7 | Anonymous users | Allowed with gateway rate limit; prompt to log in for more quota |
| D8 | Pro auth | Google login added; signup collects managed/owned venues-artists-events data |
| D9 | Maps UX | Embedded map in the expanded card on map-button click → **Leaflet + OpenStreetMap tiles** (free, no key; fits budget) |
| D10 | Shared Python code | `services/shared` package (SSE protocol, Neo4j writer, embedding text builders); CI contract job |
| D11 | Package manager | npm, single lockfile |
| D12 | Geocoding | Nominatim (with local cache + 1 req/s politeness); Google only if it underperforms |
| D13 | SEARCH trigger | CLI + admin-authed endpoint; no UI yet. Search API: **Tavily** (revised 2026-08-14, owner call — the provisioned key was Tavily, and its cleaned page content removes the fetch-and-strip step Brave would need) |
| D14 | Evals | Quarantine datasets, delete broken runners |
| D15 | Supabase | **Fresh project**; new migrations from scratch; old project is reference only |
| D16 | Canonical remote | `origin` = github.com/ai-safe-earth/laiive (the remote *named* `laiive` is the personal fork — don't push there) |

## Decided 2026-08-13 (post Phase 3)

| # | Decision | Choice |
|---|---|---|
| D17 | SEARCH scheduling | **Prefect Cloud, managed work pool**; flows are thin HTTP clients of `/api/admin/search/*`; first cut = weekly city sweep + nightly embedding/geocode backfill; sweeps stay **dry-run**, a human approves the batch |
| D18 | Frontend hosting | **Cloudflare Pages** (Fly.io considered, declined — a static bundle gets nothing from a container runtime); services stay on Railway/Fly per R2 |

**D17 trade-off**: managed execution has no private networking, so flows cannot reach
Neo4j, Tavily or `search:8004` directly — every scheduled run authenticates as an admin
service account and goes through the public gateway, the same path a human admin uses.
Bought: zero worker infrastructure to operate or pay for, and the scheduled path is
covered by the auth tests that already exist. Exit if it binds: run a self-hosted worker
next to the services (~$2–5/mo) and point flows at the private address instead — the
flows themselves don't change, only the base URL and the credential.

**D17 boundary**: scheduling adds no new write path. Discovery still writes only through
`services/shared`'s `neo4j_writer`, tagged `source='admin_search'`, after approval.

**D18 note**: Netlify is no longer an alternative under consideration; Pages is the
single answer for the SPA.

Budget constraint (owner): **$30–50/month all-in** (LLM + hosting). Consequences:
Aura stays **Free tier** for now (verified in console: instance 2099d44c is AuraDB
Free — `NODE KEY` unavailable, the UNIQUE+NOT NULL fallback in 03 is the default;
auto-pauses when idle — acceptable pre-launch), Supabase free tier, Cloudflare Pages
free (D18), Prefect Cloud free tier (D17 — re-check its managed-execution quota when
Phase 5 lands; the free allowance changes), services on one cheap runtime (~$5–15),
leaving ~$20–35 for LLM spend — mini-first model policy matters (R3).

## Decided 2026-08-17, withdrawn 2026-08-17 (Phase 6 shape)

| # | Decision | Choice |
|---|---|---|
| D19 | Service hosting + orchestration | ~~k3s on one Hetzner CX32~~ — **withdrawn the same day** after weighing the trade-off; **R1 and R2 are reinstated** (compose now, Railway/Fly at deploy time). The full k3s work (Kustomize base+overlays, six NetworkPolicies, SOPS+age, CI deploy over Tailscale) is parked on branch **`experiment/k3s`** (`99c92d4`) for a future revival. |

**Why it was considered.** "Only the gateway may reach the services" was enforced by
nothing but network placement — CORS cannot do that job (browser-enforced; the gateway
is not a browser), and k3s's default-on NetworkPolicy controller was the cheapest
honest enforcement. **Why it was withdrawn.** The priced trade-off: Railway/Fly absorb
TLS, ingress timeouts, registry, secrets, probes, rollouts and private networking for
~$15–25/mo, while k3s converts that into ~10 working days plus a standing ops tax on
one node with no second AZ — and buys **no capacity** (HPA 2→4 on one 4-vCPU box is a
Railway slider's ceiling). The owner chose simple.

**What survived D19** (substrate-independent, kept on `refactor/foundation`):

- **The boundary, layer 2 without layer 1**: a shared `INTERNAL_API_KEY` the gateway
  injects and every service verifies (`laiive_shared/internal_auth.py`) — the services
  no longer trust `X-User-Id` merely because they are unreachable. Works identically
  under compose; unset key = no-op for local runs.
- **Replica-safety fixes** that were simply latent bugs: Redis-backed gateway rate
  limit + `trustProxy` (in-memory store meant N replicas = N× quota; no trustProxy
  meant one shared anonymous bucket behind any proxy); the geocoder's cache and
  1 req/s Nominatim gate behind a `GeocodeStore` (Redis or the old JSON file);
  `backfill_embeddings` scoped to the written nodes instead of a full-graph scan per
  submission; `/validate-event` off the event loop; liveness/readiness probes split
  (`/livez` `/readyz` — the old `/health` called `openai.models.list()`); the
  retriever's `requests.jsonl` replaced by a structured log line.
- **Hardened images**: multi-stage, non-root uid 10001, `--no-dev --no-editable`,
  venv uvicorn (no `uv run` at runtime), verified running with a read-only root
  filesystem — and the **first verified compose build since Phase 3**.
- **Compose as the deploy shape**: gateway the only published port, Redis service,
  healthchecks on `/livez`, `restart: unless-stopped`, `service_healthy` ordering.

## Recommendations awaiting sign-off

### R1. Docker, not Kubernetes — **reinstated 2026-08-17 after the D19 detour**
Three small stateless services + a gateway, one developer, no traffic yet. Kubernetes
buys autoscaling, self-healing and org-scale ops at the cost of manifests, upgrades,
and a control plane to babysit — all cost, no benefit at this stage. Docker images +
compose (dev) + a PaaS runtime (prod) covers everything needed. Revisit K8s only if you
ever need multi-node scaling or hiring expects it. **Trade-off**: if the product
explodes, migration to K8s later is real but mechanical — and now more than mechanical:
the manifests already exist on `experiment/k3s`.

### R2. Deployment platforms — **reinstated 2026-08-17**
- **Services (gateway + retriever + pusher + search): Railway** (first choice — deploys
  Dockerfiles straight from the repo, private networking between services, per-service
  env, logs; ~$5–20/mo at this scale) or **Fly.io** (second — more control, closer to
  metal, slightly more ops). A single Hetzner VPS + compose is the cheapest option but
  makes you the ops team; not worth it solo.
- **Frontend SPA: Cloudflare Pages** — settled as D18.
- **Data: managed as-is** — Neo4j Aura + Supabase.
**Trade-off**: PaaS costs more per compute unit than a VPS; buys back the only truly
scarce resource here (your time).

### R3. Models per service — "make it work first"
Stay **single-provider (OpenAI)** now: one SDK, one key, one failure mode; embeddings
are OpenAI regardless.

| Role | Model | Why |
|---|---|---|
| Retriever classifier/router | `gpt-4o-mini` | cheap, structured output, latency-critical |
| Retriever Cypher long-tail | `gpt-4o` | correctness-critical |
| Retriever composer | `gpt-4o` | tone quality is the product |
| Pusher extraction + vision | `gpt-4o` | multimodal |
| Voice | `whisper-1` | already works |
| Embeddings | `text-embedding-3-small` (1536, cosine) | cost/quality; all code assumes it |
| SEARCH extraction | `gpt-4o-mini` first, `gpt-4o` fallback on low confidence | batch cost |

Drop the OpenRouter + LlamaGuard layer (it has literally never executed due to the
client bug) and use OpenAI's free moderation endpoint + the existing regex Cypher guard.
**Trade-off / later**: Claude Sonnet 5 is the natural candidate for the composer if the
jazzy tone needs more character — isolate model choice per role in config so swapping is
a one-line change.

### R4. Licence
Proprietary: replace the Apache LICENSE with a short "Copyright © 2026 Oscar Arroyo
Vega. All rights reserved." notice and fix the README link. **Caveat**: versions already
distributed under Apache-2.0 remain Apache-licensed for whoever obtained them; the
change governs the future only. If you later want source-visible-but-protected, BSL/FSL
are the options — overkill for a private repo today.

### R5. Timing: build into the foundation now vs wait for traffic

**Now — retrofitting is expensive because it changes interfaces and habits:**
1. **Structured logging + request-id propagation** (gateway → services → LLM calls).
   Touches every service boundary; adding it later means re-threading every call site.
2. **LLM tracing (Langfuse — already integrated, keep it on)** and **eval-ready data
   capture**: persist every (request, context, results, response) tuple from day one.
   Your future evals and self-improvement loops are only as good as the data you
   started collecting today; this is the single most expensive thing to retrofit
   because the data simply won't exist.
3. **Typed contracts** (SSE protocol, EventCard, config validation) — every later
   feature builds on them.
4. **CI (lint, typecheck, tests, builds)** — cost grows with every untested merge.
5. **Graph constraints/indexes** — retrofitting uniqueness onto dirty data is painful;
   day-one constraints keep the graph clean.
6. **Secrets hygiene** (rotation, no files-in-repo, per-env vars) — breaches don't wait.

**Wait until real traffic — needs data you don't have, or is cheap to bolt on:**
1. **Dashboards/alerting** (Grafana, uptime) — platform logs suffice for one user;
   add when there's an SLO to defend.
2. **Evals as a gate** — the harness skeleton exists (quarantined datasets); wire it
   into CI when prompts stabilize and real queries exist to eval against.
3. **Self-improvement loops** (prompt auto-tuning from feedback) — requires eval
   infrastructure + volume; premature before both.
4. **Caching** (LLM response, query results) — an optimization of costs you don't yet
   incur; the exceptions worth doing early are trivial: embedding cache keyed on text
   hash, and geocoding cache (both one-dict/one-table cheap).

### R6. Additional recommendations (task §9.6)
- **Monorepo layout**: `services/{retriever,pusher,search,gateway}` + `frontend` +
  `docs`; per-service lockfiles (uv / npm); no root Python project. Shared Python code
  (protocol, writer) as a tiny `services/shared/` package installed with `uv add
  --editable` — or duplicated with a contract test if that fights uv (see Q6).
- **Testing pyramid**: unit (no network) → contract (SSE protocol, EventCard, both
  sides) → golden-set prompt tests with recorded fixtures → one live E2E smoke, opt-in.
- **Prompting**: keep every prompt in a dedicated module with a version string;
  goldens pin behavior; never inline prompts in handlers.
- **User types**: `user`, `pro`, `admin` as Supabase roles from day one (admin needed
  for SEARCH anyway); quotas per role at the gateway.
- **Cost control**: per-request token accounting via Langfuse; alert at a monthly
  budget; `gpt-4o-mini` first wherever quality allows.
