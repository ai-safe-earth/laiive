# 05 — Decisions

## Already decided (user-confirmed 2026-08-13)

| # | Decision | Choice |
|---|---|---|
| D1 | Frontend | Fresh Vite + React + TS + Tailwind + shadcn app; port tokens/translations/SSE/recorder; SSR deferred (React Router 7 framework mode or a separate public-pages site when SEO pages become a requirement) |
| D2 | Auth provider | **Supabase** (already integrated, free at this scale, Postgres+RLS fits ownership; Auth0 revisited only if enterprise SSO/MFA demands appear) |
| D3 | User/pro/ownership data | **Supabase Postgres** with RLS; graph nodes carry `owner_id` references |
| D4 | Leaked key in git history | **Rotate keys only** (OpenAI + Aura + Langfuse); no history rewrite while both remotes stay private |

## Recommendations awaiting sign-off

### R1. Docker, not Kubernetes
Three small stateless services + a gateway, one developer, no traffic yet. Kubernetes
buys autoscaling, self-healing and org-scale ops at the cost of manifests, upgrades,
and a control plane to babysit — all cost, no benefit at this stage. Docker images +
compose (dev) + a PaaS runtime (prod) covers everything needed. Revisit K8s only if you
ever need multi-node scaling or hiring expects it. **Trade-off**: if the product
explodes, migration to K8s later is real but mechanical (images already exist).

### R2. Deployment platforms
- **Services (gateway + retriever + pusher + search): Railway** (first choice — deploys
  Dockerfiles straight from the repo, private networking between services, per-service
  env, logs; ~$5–20/mo at this scale) or **Fly.io** (second — more control, closer to
  metal, slightly more ops). A single Hetzner VPS + compose is the cheapest option but
  makes you the ops team; not worth it solo.
- **Frontend SPA: Cloudflare Pages** (free, fast, SPA rewrites) or Netlify.
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
