# 02 — Target architecture

Decisions already confirmed: fresh Vite+React frontend; Supabase for auth; Supabase
Postgres for user/pro/ownership data; Node gateway owns auth/rate-limit/routing.

## 1. System diagram

```
                        ┌────────────────────────────────────────────┐
                        │  Browser — Vite/React SPA (static hosting) │
                        │  chat UI · pro chat · auth screens         │
                        └───────────────┬────────────────────────────┘
                                        │ HTTPS, Supabase JWT (Authorization: Bearer)
                                        ▼
      ┌──────────────────────────────────────────────────────────────┐
      │  API GATEWAY — Node/Fastify (public)                         │
      │  · verifies Supabase JWT via JWKS   · rate limiting          │
      │  · role check (user | pro | admin)  · CORS (allow-list)      │
      │  · request-id injection             · routing/proxy          │
      └────┬──────────────────────┬──────────────────────┬───────────┘
           │ /api/chat/*          │ /api/push/*          │ /api/admin/search/*
           ▼                      ▼                      ▼ (admin role only)
   ┌───────────────┐      ┌───────────────┐      ┌────────────────┐
   │  RETRIEVER    │      │  PUSHER       │      │  SEARCH (new)  │
   │  FastAPI      │      │  FastAPI      │      │  FastAPI       │
   │  read-only    │      │  writes       │      │  writes,       │
   │  agentic RAG  │      │  HITL form    │      │  source-tagged │
   └──────┬────────┘      └──────┬────────┘      └──────┬─────────┘
          │ READ_ACCESS          │ write                │ write
          └──────────────┬───────┴────────────┬─────────┘
                         ▼                    │
              ┌─────────────────────┐         │
              │  Neo4j Aura 2099d44c│◄────────┘
              │  domain graph +     │
              │  vector indexes     │
              └─────────────────────┘

   Supabase (managed, alongside):
   · Auth: Google OAuth + email/password (users and pros; pros = role + extra profile)
   · Postgres + RLS: profiles, promoter_profiles, ownerships, quotas, conversation log
   · Edge functions: retired; their logic moves to gateway or services
```

Invariants kept from the current system:
- **retriever and pusher never call each other**; the graph is the only shared state.
- Services stay Python/FastAPI/uv; each service keeps its own pyproject.
- Services bind to the internal network only; the gateway is the sole public surface.
  CORS `*` on FastAPI is removed (the gateway terminates browser traffic).

## 2. Shared SSE protocol (replaces markdown-scraping and sentinels)

One protocol module (duplicated verbatim in retriever + pusher + a TS type file in the
frontend; drift-checked by a contract test) using **named SSE events**:

```
event: message.delta      data: {"text": "…"}                         # assistant prose
event: events.result      data: {"events": [EventCard...]}            # structured cards
event: form.extracted     data: {"draft": EventDraft, "missing": [],  # pusher form
                                 "index": 0, "total": 1}              #   "event 1 of 5"
event: status             data: {"state": "searching|composing|…"}    # UX affordance
event: error              data: {"code": "...", "message": "..."}
event: done               data: {"request_id": "..."}
```

A submission turn that recognizes several events emits one `form.extracted` per
event in source order; `index`/`total` are how the client walks them one at a time.
A single event is that same frame with index 0 of 1, so there is no separate batch
frame (the sketched `batch.progress` was dropped for this reason).

`EventCard` (the card contract — one shape, typed on both sides):
```json
{"uid": "...", "name": "...", "artists": ["..."], "venue": "...", "venue_type": "club",
 "city": "...", "start_at": "2026-08-14T21:00:00+02:00", "price_min": 0,
 "price_max": 15, "price_currency": "EUR", "description": "...", "ticket_url": "...",
 "lat": 40.4, "lng": -3.7, "source": "pro_submission|admin_search",
 "distance_km": 1.2}
```
The frontend renders cards from `events.result` — never by parsing prose. "Read more"
expands `description`; the map button expands an **embedded map inside the card**
(Leaflet + OpenStreetMap tiles — free, no API key), with a "open in Google Maps"
deep-link (`https://www.google.com/maps/search/?api=1&query={lat},{lng}`) inside it.

Real streaming: the composer's tokens are streamed as they are generated (not
re-tokenized post-hoc); `events.result` is emitted the moment results exist, before the
prose finishes.

## 3. RETRIEVER redesign

Pipeline per turn (stateless server; client sends history + location + language):

```
turn input ──► CLASSIFIER (one cheap LLM call, structured output)
              · query type: event_search | nearby | refinement | new_topic |
                smalltalk | out_of_scope
              · conversational moment: first_query | refinement | new_independent |
                ambiguous
              · resolved query state: previous constraints ± this turn's changes
                (this is how "later queries are built by adding to or changing
                 earlier ones" works — the classifier re-emits the full constraint
                 set every turn)
         ──► ROUTER: splits complex questions into atomic sub-queries
              (e.g. "jazz tonight and anything by X this month" → 2 graph queries)
         ──► EXECUTION per sub-query, hybrid:
              · structured Cypher (parameterized templates for the common shapes;
                LLM-generated Cypher only for the long tail, still read-only-validated)
              · vector kNN (db.index.vector.queryNodes) for fuzzy/similarity asks
              · point.distance for nearby; user location injected as parameters
         ──► COMPOSER — runs after EVERY query, no exception.
              Input: query type + conversational moment + ground-truth results +
              conversation context + user language.
              Output: a very short text (template-guided) adapted to the moment
              (first / refinement / new / empty result / ambiguous), streamed;
              events go out separately as events.result.
```

Tone (defined once in the composer system prompt, kept consistent):
> A musical assistant: light, a bit jazzy, warm. Never neutral-robotic, never slangy,
> never trying too hard. Short sentences. It asks for the minimum missing detail
> naturally inside the conversation — one question at a time, never as a form.

Location & language first-class: both arrive on every request; the classifier and
composer receive them; "concerts near me tonight?" resolves against the user position.
Language policy (decided): the composer simply **answers in the language of the
conversation** — no fixed language list, no detection regexes (replaces the dead
`language` field and the English-only `needs_more_info` heuristic). The en/es/it/ca
list applies only to UI chrome, chosen at signup and in profile settings.

## 4. PUSHER redesign

- Extract from any modality → if required fields missing, **exactly one** clarification
  round (asks naturally for what's missing) → then always the form, with missing fields
  visibly marked. No long guided completion.
- Form payload travels as `form.extracted` (typed SSE event) — the
  `__EVENT_EXTRACTED__` sentinel dies.
- **Many events are not a separate mode** (revised in 4b): extraction runs over the
  whole conversation and returns a *list* of drafts, so a spreadsheet, a festival
  line-up and a promoter listing four gigs all take the ordinary path. The chat says
  how many it recognized, one clarification round covers the whole set, then one
  `form.extracted` per event carries `index`/`total` and the frontend shows them one
  at a time. Approval of draft i triggers write i. `/batch/parse` +
  `/batch/validate-event` remain as the deterministic fast lane for large sheets.
- Write path fixes: MERGE identity (see 03), venue geocoded on write (`location`
  point), `source: 'pro_submission'`, `owner_id` from the authenticated user, dedup
  check before write (same name_norm + date + venue → warn instead of duplicate).
- The legacy "type yes to publish" path is removed; the form is the only write trigger.
- Session state moves out of process memory (short-TTL store or client-carried state)
  and session ids come from the gateway, not from hashing message text.

## 5. SEARCH service (new, internal)

- FastAPI service, not publicly routed; triggered by an admin gateway route and a CLI.
- Pipeline: search (Brave initially) → fetch/normalize → LLM extraction (shared with
  pusher's converters) → dedup against graph (name_norm + date + venue + vector
  similarity) → **dry-run report** → admin approves → batch write, every node tagged
  `source: 'admin_search'` (never `pro_submission`).
- Runs in batches; writes are idempotent (MERGE on identity keys).
- **Scheduling (D17)**: Prefect Cloud runs the sweep weekly per city and a backfill
  nightly. The flows execute on Prefect's managed pool, which has no private networking,
  so they call `/api/admin/search/*` on the public gateway as an admin service account —
  the same authenticated route a human admin uses. Scheduling therefore adds no new
  write path and no new credential surface on the services: a scheduled sweep produces
  the same dry-run report, and the batch write still waits for an approve.

## 6. Auth & ownership (Supabase — **fresh project**, decided)

- A new Supabase project is created; the old `ccdlygjdizpesdblymaq` is reference
  material only (its migrations inform the new schema; no data migrates).
- Supabase Auth for both user types, **Google OAuth on consumer and pro alike**; `pro`
  is a role (`user_roles`) plus `promoter_profiles` (venues/artists/events they manage
  or own, contact, accountability data — collected at pro signup).
- Anonymous users allowed: gateway rate-limits by IP/device with a small quota and the
  UI suggests login to raise it.
- Ownership: `ownerships(entity_uid, entity_type, user_id, role owner|editor,
  granted_by, granted_at)` with RLS — supports **shared** ownership (multiple rows) and
  **transfer** (insert new owner, demote/remove old, both audited). Graph nodes store
  `owner_id` (and the gateway enforces it for pusher edits).
- The gateway verifies JWTs (JWKS), extracts user id + roles, forwards them as trusted
  headers to services; services trust only the gateway network.
- The 9 `verify_jwt=false` edge functions are retired; `validate-conversation` logging
  moves into the gateway (fire-and-forget insert), `promoter-signup` becomes a gateway
  route using the service-role key server-side.

## 7. Environments & config

- One root `.env` (name-aligned with config, template `.example.env`), read by all
  services; every settings class validates required keys at startup with clear errors.
- Ports: retriever 8002, pusher 8003, search 8004, gateway 8787 — everywhere
  (Dockerfile, compose, Makefile, frontend env). One definition, no drift.
- Frontend env: typed `ImportMetaEnv` + runtime assert; `VITE_API_URL` points at the
  gateway only.
