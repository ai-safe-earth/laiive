# 06 — Questions

Grouped and numbered — short answers are enough.

## A. Product / UX

1. **Public event pages**: chat-only for now, confirmed? (If crawlable event/venue
   pages are near-term, the D1 frontend decision should be revisited toward Next.js —
   see the trade-off discussion; otherwise React Router 7 keeps the door open.)
2. **Languages**: keep all four (en/es/it/ca)? Should the assistant *reply* in all
   four, or reply in en/es and only accept the others?
3. **Anonymous users**: may anonymous visitors chat with a small quota (current code
   intended 5/week but the gate is commented out), or is login required before the
   first query?
4. **Pro Google login**: promoter auth is email/password only today. Add Google parity?
5. **"How to get there"**: is a Google Maps deep link enough, or do you want an
   embedded map in the card? (Deep link recommended — zero API cost.)

## B. Architecture / code

6. **Shared Python code** (SSE protocol, Neo4j writer used by pusher + search):
   small `services/shared` editable package, or duplicate-with-contract-test?
   (Recommendation: shared package unless uv workspace friction appears.)
7. **bun vs npm**: CLAUDE.local.md says bun, but bun isn't installed on this machine
   and `package-lock.json` is the live lockfile. Standardize on npm? (Recommended:
   whatever is actually installed — npm — one lockfile.)
8. **Geocoding provider** for venue coordinates on write: Nominatim/OpenStreetMap
   (free, rate-limited, fine at this volume — recommended) vs Google Geocoding API
   (better hit-rate, needs billing)?
9. **SEARCH trigger surface**: is a CLI + one admin-authed gateway endpoint enough for
   v1, or do you want a minimal admin UI page (list runs, review dry-run report,
   approve batch)?
10. **Search API**: keep Brave (key already provisioned for the retriever design), or
    evaluate alternatives (SerpAPI, Tavily) before building SEARCH?
11. **Evals**: quarantine the datasets and delete the broken runners (recommended), or
    invest now in repairing the versioned-prompt registry they were built against?
12. **Old Aura instance `5ce2d474`**: confirmed dead/deleted? (Root `.env` still points
    at it; I'll repoint to `2099d44c` in Phase 0.)

## C. Operations

13. **Key rotation** (Phase 0, user action): rotate OpenAI + Aura + Langfuse now, or
    schedule it? The leaked OpenAI key in git history should be revoked regardless of
    whether it is still active.
14. **Remotes**: which remote is canonical for this refactor's PRs — `origin`
    (ai-safe-earth/laiive) or `laiive` (OscarArroyoVega/laiive)?
15. **Supabase project**: keep the existing project `ccdlygjdizpesdblymaq` (has users,
    tables, RLS) and migrate it forward, or start a fresh project alongside the fresh
    Aura? (Recommended: keep — real users/tables live there.)
16. **Budget ceiling** for monthly infra + LLM spend while pre-traffic? Shapes R2/R3
    (e.g. whether gpt-4o composer is acceptable or mini-first everywhere).

## D. Approval gates already agreed

17. Phase 1 schema DDL on Aura `2099d44c` will not run until you say go.
18. Nothing is pushed to any remote until you confirm the target remote (Q14).
