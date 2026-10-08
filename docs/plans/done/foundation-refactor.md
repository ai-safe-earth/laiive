---
status: done
step: foundation
next: none
---
# Foundation refactor (Aug 2026)

Merged `refactor/foundation` into `main` on 2026-08-19, then deployed per `DEPLOY.md`.
The full analysis (repo review, target architecture, ontology, phased plan, decisions
D1-D19, R1-R6) lived in `docs/refactor/`; read it with `git log -- docs/refactor/`.
The pre-refactor tree is branch `legacy/pre-refactor` (tag `pre-refactor-main`).

## What it delivered
- Phase 0 hygiene, Phase 1 graph schema on Aura `2099d44c`, Phase 2 typed SSE protocol and
  retriever/pusher redesign, Phase 3 Fastify gateway + Supabase auth, Phase 4 fresh Vite
  frontend, Phase 5 search service, Phase 6 CI + Fly/Pages deploy + foundation observability.

## Decisions still in force
- Supabase for auth and ownership data, RLS throughout; fresh project (D2, D3, D15).
- Chat-only product, no public crawlable pages yet (D5). Assistant answers in the user's
  language; UI in en/es/it/ca (D6). Anonymous users allowed, rate limited (D7).
- Shared Python package `services/shared` for the protocol and the only graph writer (D10).
- Geocoding: Nominatim, cached, 1 req/s (D12). Search API: Tavily (D13).
- Sweeps are dry-run; a human approves. Scheduling adds no new write path (D17).
- SPA on Cloudflare Pages (D18); services on Fly.io, Docker not Kubernetes (R1, R2).
  k3s work parked on `experiment/k3s` (D19, withdrawn).
- Budget $30-50/month all-in: Aura Free, Supabase free, mini-first models.
- Leaked key handled by rotation, no history rewrite (D4).
- Licence: proprietary (R4).
