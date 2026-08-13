# HANDOFF — refactor status (updated 2026-08-13, night)

Continuation point for the laiive refactor. Read this first, then
`04-plan.md` (phases) and `05-decisions.md` (all decisions, D1–D16 + budget).
Branch: **`refactor/foundation`** (from `connect-to-ui`). Nothing pushed yet;
canonical remote for future PRs = `origin` (ai-safe-earth/laiive) — the remote
*named* `laiive` is the personal fork, do not push there.

## Done

### Phase 0 — hygiene ✅ (commits `dbff176`…`235ff87`)
- Untracked production code committed; docker builds fixed; pre-commit green
  (ruff/ruff-format/mypy scoped to `services/(retriever|pusher|shared)`);
  dead code removed (pre-ReAct router, broken evals/Makefile targets,
  `FRONTEND_INTEGRATION.md`, bun lockfiles); ports unified 8002/8003;
  root `.env` aligned; LICENSE proprietary; keys rotated (D4);
  `requests.jsonl` moved to `../laiive-data/`.

### Phase 1 — graph schema + seed ✅ (commit `bb677c3`)
- Aura `2099d44c` carries the full 03-ontology DDL (constraints incl. City
  NODE KEY, range/POINT/vector indexes, all ONLINE). `setup_schema.py` is the
  DDL source of truth; `seed.py` seeds 3 cities / 5 genres / 6 venues /
  8 artists / 12 future-dated events with 1536-d embeddings. Multi-hop, geo,
  and vector queries verified live.

### Phase 2 — backend contracts + redesign ✅ (commits `f566d2b`, `6e5c6e1`, `9897d30`)
- **`services/shared`** (D10): `laiive-shared` package installed editable in
  both services — typed SSE protocol (`message.delta`, `events.result`,
  `form.extracted`, `batch.progress`, `status`, `error`, `done`) with
  `sse_frame()`; `EventCard`/`EventDraft`; `norm()`/`genre_slug()`;
  embedding-text recipes; Nominatim geocoder (cache + 1 req/s, D12);
  MERGE-by-identity `neo4j_writer` (dedup probe, `source`, `owner_id`,
  geocoded venue `location`, embedding backfill). TS mirror in
  `services/shared/ts/protocol.ts` + drift-checking contract test.
  Docker build context is now `services/` (Dockerfiles COPY shared + svc).
- **Retriever**: orchestrator/ReAct deleted. Per turn:
  `classifier.py` (gpt-4o-mini, JSON mode, re-emits full resolved constraint
  state + moment) → `router.py` (deterministic plans) → `executor.py`
  (parameterized Cypher templates, vector kNN, progressive-radius nearby
  with `start_at >= datetime()`, LLM Cypher long tail read-only-validated) →
  `composer.py` (ALWAYS runs, streams real tokens, jazzy tone, user's
  language). `pipeline.py` ties it together; built lazily (importing
  `agent.api` no longer needs Neo4j). `/chat/stream` body field
  `protocol: "legacy"|"v2"` — legacy (default) = OpenAI-shaped frames +
  markdown for the current frontend; v2 = shared named-event protocol
  (events.result before prose). Bugs fixed: LlamaGuard layer replaced with
  OpenAI moderation + regex guard (R3), `/health` openai check real,
  request_id in metadata frame, nearby cypher reported.
- **Pusher**: stateless chat (client-carried history) — extraction over the
  whole conversation, **one** clarification round, then the form always,
  missing fields marked. `**CONFIRMED**`/"type yes" path, in-memory session
  store, and hashed session ids deleted. Writes only via
  `/validate-event` + `/batch/validate-event` through `agent/graph.py` →
  shared writer (dedup → 409, `source='pro_submission'`, `owner_id` from
  `X-User-Id`). `/batch/parse` handles CSV/XLSX → drafts + per-row missing
  (openpyxl added; slowapi dropped — gateway owns rate limits in Phase 3).
- **Configs**: both fail loudly listing missing env keys; per-role models
  (CLASSIFIER_MODEL=gpt-4o-mini, QUERY_BUILDER_MODEL/COMPOSER_MODEL=gpt-4o);
  `.example.env` regenerated (OpenRouter/LlamaGuard + internet-search vars
  gone).
- **Tests**: shared 24, retriever 102 (`-m "not integration"`; the 4 old
  /health failures fixed), pusher 44 — all green. Live smokes done:
  retriever (first/refinement/nearby/empty/ambiguous/Spanish smalltalk
  against seeded Aura), pusher (create with provenance + embedding +
  geocode, MERGE into seed nodes, duplicate refused; smoke event deleted).

## Phase 2 judgment calls — taken where the plan left room, owner may revisit

1. **Pusher state is client-carried, no TTL store** (02-arch allowed either):
   extraction reruns over the full conversation each turn; clarification
   rounds = assistant messages in history. Revisit only if conversations get
   too long to re-extract.
2. **Protocol switch is a request-body field** `protocol: "legacy"|"v2"`
   (legacy default) on both `/chat/stream`s, not an env flag. In legacy mode
   the pusher one-round rule is OFF (old frontend can't render partial
   forms). Delete all legacy paths (OpenAI frames, sentinel,
   `cards_to_markdown`) when Phase 4 lands.
3. **`tools/internet_search.py` deleted** — retriever is graph-only;
   internet discovery is Phase 5's SEARCH service (Brave key still unset).
4. **Writer resilience over strictness**: geocode failure still writes the
   event (city-centroid fallback, then no location) with a warning, instead
   of rejecting the submission.
5. **`form.extracted` payload key is `draft`**, not `event` as sketched in
   02-arch §2 (avoids clashing with the frame's event name); the TS mirror
   and contract test pin it.

### Phase 3 — Node gateway + auth + ownership ✅ done (verified live 2026-08-13)

- **`services/gateway/`** (Fastify 5 + TS strict, npm, vitest 16/16 green):
  - `src/auth.ts`: Supabase JWT via remote JWKS (jose, ES256/RS256). No token
    = anonymous (D7); present-but-invalid = 401 everywhere. Role read from the
    `user_role` claim (custom access token hook), NOT Supabase's `role` claim.
    Unknown claim value degrades to `user`.
  - `src/proxy.ts`: `/api/chat/*`→retriever `/chat/*` (anon OK);
    `/api/push/*`→pusher `/*` (pro+); `/api/admin/search/*` (admin, 503 until
    Phase 5, flip with `SEARCH_ENABLED=true`). Client-sent
    `X-User-Id`/`X-User-Role`/`X-Request-Id`/`Authorization` stripped, verified
    ones injected. Chat routes parse JSON (`proxyPayloads:false`) so logging
    sees payloads; upload routes (`/batch/parse`, `/transcribe-audio`) stream
    unbuffered — keep that split if routes are added.
  - Rate limits: in-memory `@fastify/rate-limit`, anon per-IP 10/min, authed
    per-sub 60/min (env-tunable); 429 body carries the login upsell; anon
    responses get `x-login-upsell` header. CORS allow-list via
    `CORS_ALLOW_ORIGINS`.
  - `src/logging.ts`: fire-and-forget insert to Supabase `conversation_logs`
    (service role, plain fetch). Request-side only — responses stream through
    unbuffered; response capture is Phase 6's eval-record work (Langfuse has
    LLM outputs meanwhile).
  - Tests fake Supabase with a local JWKS + REST stub (`test/helpers.ts`) —
    no live project needed. SSE unbufferedness is asserted (multi-chunk).
- **`supabase/migrations/`** (fresh project, D15): profiles (+signup trigger),
  user_roles + `custom_access_token_hook`, promoter_profiles, ownerships
  (+RLS), role_quotas/user_quotas (defined but gateway still enforces from
  env), conversation_logs (service-role only). `supabase/README.md` = owner
  setup steps.
- **Services hardened**: CORS `*` gone — browser access now only via gateway
  unless `SERVICE_CORS_ALLOW_ORIGINS` set; pusher `validate-event` takes
  owner only from `X-User-Id` (body `user_id` removed); `make start-*` binds
  127.0.0.1; compose publishes only gateway :8000 (retriever/pusher `expose`
  internal), gateway targets them via service DNS. `make start-gateway` runs
  the dev server.

**Live go-live done**: Supabase project `pjlcfdyheyubsemwlzzv` created, the 7
migrations pushed, access-token hook registered, service-role key in root
`.env`. Google OAuth is still **not** enabled (needs Google Cloud credentials —
the only Phase 3 item left, and Phase 4's auth page will want it).

- `services/gateway/scripts/e2e-live.mjs` (`npm run e2e:live`) is the live
  verify step, **23/23 green**: real ES256 JWTs carry `user_role` for
  user/pro/admin (proves the hook), anon chat 200 + `x-login-upsell`,
  multi-chunk SSE through the proxy, garbage/malformed bearer → 401,
  `/api/push` 401/403/200 by role, `/api/admin/search` 403/503, client-sent
  `X-User-Role` cannot escalate, `conversation_logs` rows with the verified
  user id, anon burst → 429 with upsell. It provisions three throwaway users
  via the admin API and deletes them at the end; the anon rate-limit budget is
  waited out at the start so consecutive runs pass.
- Getting there fixed two real bugs (see below): retriever SSE was not actually
  streaming, and the root `.env` had drifted back to its pre-Phase-2 shape.
- Postgres note: `db.<ref>.supabase.co` is IPv6-only, so `supabase db push`
  from this machine must use
  `postgresql://postgres.<ref>:<pw>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`.
  The push itself is blocked by the permission classifier — the owner runs it.
- Migration `20260813000007` revokes public EXECUTE on `handle_new_user`
  (linter 0028/0029). Remaining advisor output is one INFO: `conversation_logs`
  has RLS on with no policies, which is the intended service-role-only shape.

### Phase 3 judgment calls — owner may revisit

1. **Role travels in the JWT** via custom access token hook (owner approved):
   stateless gateway, but role changes only land on token refresh (~1h).
2. **Conversation logging is request-side** into Supabase (owner approved
   destination): payload captured on chat routes only; response-side capture
   deferred to Phase 6 (would require buffering the SSE stream).
3. **Quota tables exist but aren't read** — gateway enforces env-configured
   per-minute limits in memory (resets on deploy, single-instance only);
   per-day quotas + per-user overrides wire up when they matter.
4. **Legacy frontend transition**: with service CORS now opt-in, the current
   frontend's direct 8002/8003 calls fail CORS. Options until Phase 4: set
   `SERVICE_CORS_ALLOW_ORIGINS=http://localhost:8081` on the services, or
   point it at the gateway (`/api/chat/*` works anonymously; `/api/push/*`
   would 401 — old Supabase project's tokens don't verify against the new
   JWKS).
5. **No eslint in the gateway yet** — typecheck + vitest only; Phase 6's CI
   matrix adds it.
6. Gateway Docker image builds are **unverified** — Docker Desktop wasn't
   running on this machine; `docker compose build gateway` is the first thing
   to try when it is.
7. `verify-retriever` skill's stale per-file test list replaced with
   `-m "not integration"`.
8. **SSE was fake-streaming again** (found by the live E2E, fixed):
   `agent/api.py`'s `_generate_v2`/`_generate_legacy` were `async` generators
   iterating the *blocking* `pipeline.run_turn`, so the event loop never got to
   flush and every frame landed in one burst at the end (3.1 s of silence, then
   the whole answer). They are now sync generators — Starlette iterates those in
   a threadpool. Frames now arrive progressively (status at 2.3 s, tokens from
   4.5 s). `TestStreamingIsIncremental` in `tests/test_api_endpoints.py` guards
   it. Anything new that yields SSE frames must not `async def` around blocking
   work; the pusher's pattern (`await asyncio.to_thread(...)`) is the other
   valid shape.

### Phase 4a — new frontend, consumer chat ✅ (commit `330bb5a`)

`frontend/` is a fresh Vite + React 18 + strict-TS app (the Lovable snapshot is
in git history). Verified in Chrome against the live stack: anonymous "jazz in
Madrid" streams status → cards → prose, the Leaflet map opens inside the card
with a correct pin and a Google Maps deep link, read-more expands, no console
errors.

- **One backend**: `src/api/client.ts` → gateway only, token read per request
  (never captured in a closure — supabase-js refreshes in the background).
  `ApiError` carries status + whether the gateway sent `x-login-upsell`.
- **`src/api/sse.ts`** parses the *named-event* v2 protocol; types come from
  `services/shared/ts/protocol.ts` via the `@shared` alias (tsconfig path +
  Vite alias + `server.fs.allow`), so `test_ts_contract.py` now guards the
  frontend too. Never redeclare `EventCard` locally.
- **Ported verbatim**: `index.css` tokens, `translations/` (en/es/it/ca),
  `audioRecorder`. Dropped: 30 unused Radix packages, the second toast system
  (sonner only), shadcn CLI wiring, the dead edge functions.
- `npm run typecheck` runs **both** tsconfig projects — plain `tsc --noEmit` at
  the root is a silent no-op with project references (it was, at first).
- Windows trap: renaming `ui/button.tsx` → `ui/Button.tsx` needed
  `git mv --force`; git kept the old casing and the Pages build (Linux) would
  have failed on the import. Check `git ls-files` casing after any rename.

## Next: Phase 4b/4c and the gaps 4a left

- **4b — pro flows**: PusherChat against `/api/push/chat/stream`, form from
  `form.extracted` with missing-field highlights, one-clarification-round UX,
  batch mode with `batch.progress`, CSV/XLSX upload.
- **4c — account + cleanup**: profile (ui_language), promoter entities via
  react-query; then delete the legacy SSE frames, the `__EVENT_EXTRACTED__`
  sentinel and `cards_to_markdown`, and drop `SERVICE_CORS_ALLOW_ORIGINS`.
- **Voice input is not in 4a**: the only transcription endpoint is the pusher's
  `/transcribe-audio`, which sits behind `/api/push/*` (pro+). Consumer voice
  needs either a retriever-side transcribe route or a gateway exception —
  owner decision, not a code detail. `audioRecorder.ts` is already ported.
- **Google sign-in**: the Auth page has a placeholder comment where the button
  goes; enable the provider in Supabase first (needs Google Cloud credentials).

Backend follow-ups the browser walkthrough surfaced (not frontend bugs):

1. **Composer answered in Spanish to an English question** ("jazz in Madrid" →
   "Tres noches de jazz te esperan en Madrid"). D6 says it adapts to the
   *user's* language; the city name appears to be pulling it over.
2. **Genre recall is loose**: that jazz query returned Flamenco Eléctrico and
   two Costa Norte events. Worth checking whether the genre constraint reaches
   the Cypher or only the vector kNN.

## Phase 4 plan of record (04-plan.md)

Fresh Vite+React app (D1): v2 protocol, cards from `events.result`, Leaflet
maps (D9), auth against the new Supabase project, `VITE_API_URL` → gateway
:8000. After it lands, delete the legacy SSE frames + sentinel +
`cards_to_markdown`, and drop `SERVICE_CORS_ALLOW_ORIGINS` entirely.

Supabase values it needs: `SUPABASE_URL=https://pjlcfdyheyubsemwlzzv.supabase.co`
and the publishable key `sb_publishable_YMEqW94-1qlPPBmV6YYSvQ_v9fH4Htt`
(both already in root `.env`; the old project `ccdlygjdizpesdblymaq` in
`frontend/.env` is dead). Google sign-in needs the provider enabled first.
Then Phase 5 SEARCH service (set `SEARCH_ENABLED=true` on the gateway),
Phase 6 CI/CD + deploy ($30–50/mo budget).

New decisions for those phases (D17/D18 in `05-decisions.md`, work items in
`04-plan.md`):

- **Phase 5 gains Prefect Cloud scheduling.** Flows run on a *managed* work pool,
  which has no private networking — so they are thin HTTP clients of
  `/api/admin/search/*` on the public gateway, signing in as a Supabase admin
  service account (password in a Prefect Secret block, JWT minted per run).
  First cut: weekly per-city sweep (one Prefect task per city, markdown artifact
  for review) + nightly embedding/geocode backfill. Sweeps stay **dry-run** —
  the batch write still waits for a human approve. Scheduling adds no new write
  path; the shared `neo4j_writer` remains the only one.
- **Phase 6 frontend host = Cloudflare Pages** (D18). Fly.io was considered and
  declined for a static SPA; services still go to Railway/Fly per R2.

## Environment gotchas (this machine)

- Windows; `bun` NOT installed — use npm/node. Port 8080 taken by
  EnterpriseDB → run Vite with `--port 8081`.
- Always `cd services/<svc>` before `uv run …` (config loads `../../.env`
  relative to CWD). Missing keys now exit with a clear message.
- Pre-commit runs on commit and modifies files (ruff format) — a failed
  commit usually just needs re-`git add` + retry. Watch the ruff --fix hook:
  it deletes imports that are unused *at the moment of the edit* (add import
  + usage in the same write).
- Pusher tests' `conftest.py` patches `agent.converters._client`,
  `agent.conversation._client`, `agent.graph._openai/_driver/_geocoder`;
  new modules with module-level clients must be added there.
- `cd` in one Bash call does not persist reliably — use absolute paths.
- Long-lived dev servers from an earlier session go stale: a retriever started
  before the `.env` repair reported `openai: error` on `/health` while the key
  worked fine via curl. Check `Get-NetTCPConnection -LocalPort 8002` /
  `StartTime` before debugging a service you did not start.
- Writes to Supabase (`db push`, MCP `apply_migration`/`execute_sql` DDL) are
  refused by the permission classifier — hand the owner the command to run.
- MCP `aura-neo4j` points at `2099d44c` (write access; ask owner before
  writing data). Playwright + claude-in-chrome MCPs available.

## Standing rules from the owner

- Terse replies, no end-of-turn summaries. Propose a plan before
  implementing; explain real trade-offs. Every decision needs owner approval.
- Conventional Commits (commit-msg hook enforces), lowercase subject.
- Never read `.history/` or `legacy/`.
