# HANDOFF — laiive (updated 2026-08-18, fourth session)

The single handoff for this repository (moved here from `docs/refactor/HANDOFF.md`;
never start a second one). Continuation point for the laiive refactor. Read this
first, then `docs/refactor/04-plan.md` (phases) and `docs/refactor/05-decisions.md`
(all decisions, D1–D19 + budget).
Branch: **`refactor/foundation`** (from `connect-to-ui`), pushed to `origin`
(ai-safe-earth/laiive) 2026-08-15, updated 2026-08-17 (`e100195`); `main` on
`origin` not updated yet. The k3s detour lives on **`experiment/k3s`**
(`99c92d4`, `12d85d7`), also pushed — see *Phase 6* below before reviving it.
Canonical remote for PRs = `origin` — the remote *named* `laiive` is the
personal fork, do not push there.

**Where things stand**: phases 0–3 done and verified live; phase 4a (consumer
chat), 4b (multimodal submission), 4c (legacy deletion + account page) and
**4d (the multi-event walk)** are done — 4d is live-smoked against the real
LLM but its UI has not had a browser walkthrough yet (see *Phase 4d*).
Nothing is deployed yet. To run the stack locally: gateway :8000, retriever
:8002, pusher :8003, frontend :8081 (see *Environment gotchas* — stale
servers from earlier sessions are a recurring time sink).

**Next up**: **the live deploy, owner-driven, per root `DEPLOY.md`** — all the
deploy-prep code landed 2026-08-18 (second session, see *Phase 6 — deploy-prep*):
202+poll sweep/backfill, Fly configs (`deploy/fly/`, owner chose **Fly.io** over
Railway), Pages `_redirects`, `.example.env` completed, gateway eslint in CI.
The one repo-side gate is migration `20260818000010` (owner pushes it before the
new search service runs against Supabase). Older context below.
Phase 5b scheduling is done. The **third session of 2026-08-18 was geocoding
quality**, six commits on `refactor/foundation` (`e48f102`..`3eb5935`), all
suites green - see *Geocoding and location quality* below. The **fourth
session** closed three of that session's four open items and found a fifth
problem while smoking them live - five commits (`ef9c3ff`..`9cce367`), see
*Named-place search and pin quality* below. The one geocoding item still open
is the repair-sweep drain, which is an Aura write and needs the owner.
The k3s detour (D19) was **withdrawn the same day it was decided** — the owner
chose simple: compose stays the shape, gateway the only published surface,
Railway/Fly at deploy time per the reinstated R1/R2. The full k3s work is
parked on branch **`experiment/k3s`** (`99c92d4`, `12d85d7`); everything
substrate-independent from that session **survived and is committed on
`refactor/foundation`** — read *Phase 6 — the k3s detour and what survived*
below before touching the gateway, the geocoder, the writer, or any Dockerfile,
because all of them changed. **Scheduling is implemented and verified live**:
`services/search/flows/serve.py` registers both cron deployments in Prefect
Cloud and executes them locally against the gateway — see *Phase 5b — the
scheduling rethink*. Only remaining scheduling work is optional packaging (a
compose `flows` service). The only Phase-4 leftover is the Google click-through
by the owner.

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
  `form.extracted`, `status`, `error`, `done`) with
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

### Phase 4b — multimodal ingestion + pro submission ✅ (commits `bb44217`…`277ab02`)

The owner's shape, now implemented: **every input modality becomes text, the
text joins the conversation, and one extraction path over the whole
conversation produces the draft.** A flyer that supplies the venue and a
sentence that supplies the price merge into one draft with no merge rules in
the browser.

- **Public STT** (`laiive_shared/speech.py` + retriever `/transcribe`,
  gateway `/api/transcribe`): anonymous users get voice (D7). The pusher's
  transcription is pro-only and could never serve the consumer composer. Size
  and format policy live in shared and are checked **before** the Whisper call —
  with anonymous access that cap is a cost control, not a nicety.
- **Pusher `/ingest`** (multipart: audio | image | document | url) returns
  `{kind, source, text}` and deliberately **does not extract** — extraction
  belongs to `/chat/stream`, which sees the whole conversation.
- `document_to_text` was dead code with a broken branch (raw PDF bytes to the
  vision *image* API). Now pypdf for the text layer, python-docx for .docx;
  a scanned PDF is refused with a pointer to the image path rather than pulling
  in a page renderer (pymupdf, ~40 MB) — revisit if promoters send scans often.
- **`/validate-event` accepts a full draft**, so the form no longer flattens
  genre, venue_type, address and price ranges away on the last hop into the
  graph. The legacy flat payload still works until 4c deletes it.
- Gateway caps upload size on the declared content-length: those routes stream
  through unparsed, so Fastify's body limit never sees them.
- Frontend: mic in consumer chat (transcript lands in the composer for review,
  not auto-sent) and `/pro` — attach flyer/document/recording or type, form from
  `form.extracted` with the five required fields marked, publish sends the draft.

Verified in the browser against the live stack: flyer.txt upload → form
pre-filled (name, artists, 2026-09-25T21:30, Sala Clamores, Madrid, 18 EUR,
genre, ticket link) → follow-up sentence **merged** address + price_max while
keeping everything else. Publishing was not clicked (writes to Aura need owner
approval). Suites: shared 36, retriever 107, pusher 58, gateway 19.

**A React trap worth remembering** (cost an hour): flipping a flag *inside* a
`setMessages` updater breaks under StrictMode — React double-invokes updaters,
so the second pass took the "replace last message" branch and silently dropped
the user's flyer from the conversation sent back up. Decide append-vs-replace
outside the updater; keep updaters pure. The gateway's `conversation_logs`
payloads are what pinned it down — query them when the UI and the API disagree.

### Phase 4b (cont.) — many events in one conversation ✅ backend only

The owner's call: a spreadsheet is **not** a batch mode, it is a longer
conversation. Extraction now returns a *list*, so a CSV, a festival line-up and
"I have four gigs next week" all take the ordinary path; the assistant says how
many it recognized, one clarification round covers the whole set, and the forms
then go out one per event.

- `converters.extract_drafts_from_text()` (prompt v3) asks for
  `{"events": [...]}` and tolerates a bare object or bare list — a lone event
  still comes back unwrapped often. `extract_draft_from_text` survives as a
  `[0]` wrapper for the `/extract-event-*` endpoints 4c deletes.
- `PusherTurn` carries `drafts` + a parallel `missing`; `.draft` /
  `.draft_missing` are the first-event view the legacy frames use. The
  clarification prompt for a set is written from `_gaps()` ("2 of them are
  missing the ticket price") so the assistant asks once, not event by event.
- `MAX_EVENTS_PER_TURN = 25` (conversation.py). Past it the turn keeps the
  first 25, sets `truncated`, and the reply asks for the rest separately —
  every turn re-emits all drafts, so a 200-row sheet would spend the turn
  rewriting itself. Big sheets keep the deterministic `/batch/parse` fast lane.
- **Protocol**: `form.extracted` gained `index`/`total` and `/chat/stream` v2
  emits one frame per event in source order. `batch.progress` is **deleted** —
  a lone event is index 0 of 1, so a second frame shape had nothing to carry.
- Extraction no longer guesses `venue_type: "other"` when nothing says so.

Live-smoked against a 4-row CSV pasted as conversation text (scratch pusher on
:8013, no writes): "He reconocido cuatro eventos" + one round asking only for
the row with gaps; then "The third one is at Café Berlin, 14 euros. And all of
them are jazz." landed on the right draft and the genre on all four, order
preserved, 4 frames indexed 0–3 of 4. Suites: shared 36, pusher 70,
retriever 107, frontend typecheck + lint clean.

**Why no UI**: owner deferred it at the time. Superseded — see *Phase 4d* below:
the answer is not a queue in the browser but a walk driven by the agent, one
event per turn. Nothing else regressed (single-event submission is unchanged,
index 0 of 1).

### Phase 4c — legacy deletion + account ✅ (commits `de46fda`…`d2b45a6`)

**The three walkthrough follow-ups are fixed and verified live**, and two of the
three diagnoses in the old handoff were wrong — worth reading before trusting a
symptom report:

- **Language** (`fix(agent)`, `fix(shared)`): both services *already* had a
  "reply in the user's language" rule and both ignored it, because it sat at the
  top of a long prompt with a wall of Spanish proper nouns after it. The
  language is now decided once per turn from the user's own words and handed to
  the reply prompt as a fact, **placed last** — `laiive_shared/language.py`.
  The retriever gets it free (one more field on the classifier's existing
  structured call); the pusher has no classifier, so `detect_language` makes one
  cheap gpt-4o-mini call on the promoter's *latest message only* (not the whole
  conversation — that carries pasted flyers).
  A listing like "Marta Sanchez Trio plays Sala Clamores, Madrid, tickets 18
  euros" is the hard case: mostly names, and two ordinary words carry the whole
  signal. The first prompt failed it on mini; four worked examples took mini
  from 8/10 to 10/10, matching gpt-4o, so detection stays cheap. Verified
  end-to-end in en/es/it/ca.
- **Genre recall was not a ranking problem** (`fix(retriever)`): the executor
  applies the genre clause on every path. The *classifier* was dropping the
  constraint on terse English — "jazz in Madrid" came out as city='Madrid',
  genre=None, i.e. "everything in Madrid". Longer phrasings were always fine.
  Also: **the seed has no jazz in Madrid at all** (only Barcelona and Berlin),
  so the correct answer there is the empty-result moment, not a consolation
  list. A prompt rule now pins genre; verified across terse phrasings while a
  real vibe ask ("something intimate and candle-lit") still routes to free_text.
- **Same smoke found a third bug**: "concerti jazz a Barcellona" resolved to
  city='Barcellona' and, since city matching is exact on `name_norm`, returned
  nothing. Cities now come back in their local name (Barcellona/Londres/Múnich →
  Barcelona/London/München).

**Legacy paths deleted** (`refactor:`): retriever `_generate_legacy`, all of
`utils/formatters.py` (`cards_to_markdown` + OpenAI-shaped frame helpers), the
markdown block `/chat` appended to its prose; pusher `_generate_legacy` with the
`__EVENT_EXTRACTED__` sentinel, the flat `EventDetailsModel` branch of
`/validate-event`, `/transcribe-audio` and the three `/extract-event-*`
endpoints (superseded by `/ingest`), and `process_turn`'s `one_round_rule` flag.
The `protocol` request field is **dropped entirely**, not pinned to "v2" — a
stale caller gets the only protocol there is rather than a 422 about a choice
that no longer exists. `SERVICE_CORS_ALLOW_ORIGINS` and
`frontend/src/audio/audioRecorder.ts` are gone too.

**`/account`** (`feat(frontend)`): display name + UI language for everyone,
organisation/website/phone/managed venues/artists for pros. Language now follows
the account (`profiles.ui_language` beats localStorage once signed in, picking
one writes through) via `src/i18n/useLanguagePreference.ts`.

- **Owner decision — profile data goes direct to Supabase, not through the
  gateway.** The ownership rule is already an RLS policy enforced by Postgres;
  a gateway route would restate it in TypeScript *and* run with the service-role
  key, so a bug there leaks the whole table instead of one row. It is all behind
  `src/api/profile.ts`, so moving it server-side later is an implementation
  change. `frontend/src/auth/supabase.ts`'s old "auth only, never reads
  application tables" comment was updated to match.
- RLS does not narrow *which columns* of the owned row are writable, so
  **migration `20260814000008` grants UPDATE on display_name/ui_language only** —
  it keeps a future `plan` or `quota_override` column from being self-settable.
  Pushed by the owner 2026-08-14.
- Copy is English, like Auth and ProSubmit. Only `t.chat.*` is actually wired to
  `translations/` — the ported `about`/`promoter`/`promoterCreate` sections have
  no callers. A translation sweep across all pages is its own task.

**Verified signed in** against the live project, with a throwaway pro user
created and deleted through the admin API (same pattern as `e2e-live.mjs` —
the script is worth rewriting when the next page needs it): display name,
language, organisation, website, phone and both chip lists round-trip through
Supabase and reload; `ui_language` sets `document.documentElement.lang` on load;
the promoter section appears for `pro` and is absent for `user`; signed-out
`/account` redirects to `/auth`. No console errors.

**That walkthrough caught a bug typecheck could not** (`fix(frontend)`,
`11ccffa`): picking a language writes through and invalidates the profile query,
react-query hands back a *new* object, and the `[profile]` seeding effect re-ran
and wiped a display name typed but not yet saved — it reached the database as
null. Both seeding effects are now guarded by a ref and run once per account id.
Worth remembering as a shape: **any form seeded from a react-query result
re-seeds on every refetch**, and a sibling mutation is enough to trigger one.

Suites after 4c: shared 48, retriever 103, pusher 65, gateway 19, frontend
typecheck + lint clean.

### Phase 4d — the multi-event walk ✅ (commits `148f239`…`2a08c67`)

The owner's design implemented: a spreadsheet or a line-up is not a batch
screen, the chat walks the promoter through the events one at a time — "event
1 of 5, here is what I have, I need the price and the date" → form, gaps
marked → publish → "let's go with event 2". The cursor lives client-side
(owner chose A): the browser echoes the draft list + cursor with each message,
the pusher refines only `drafts[cursor]`, and it advances on publish.

- **Shared**: new `walk.state` SSE frame (`drafts`, `missing`, `cursor`,
  `total`) in `protocol.py` + TS mirror; `form.extracted` unchanged, now
  carrying only the event under the cursor (`index=cursor`).
- **Pusher**: `process_turn(messages, walk)` — with no `walk`, N>1 extracted
  events enter the walk immediately (the per-event intro *is* the ask, so the
  set-wide clarification round and `CLARIFY_MANY`/`HANDOFF_MANY`/`_gaps` are
  deleted; a single event keeps the old one-round shape). Mid-walk there is
  **no re-extraction**: `converters.refine_draft()` merges the promoter's
  latest message into the cursor's draft only, falling back to the unchanged
  draft on any unparseable reply, so a turn costs one draft's worth of tokens.
  Cursor is clamped; an empty echoed set falls back to extraction;
  `MAX_EVENTS_PER_TURN = 25` still caps the entry turn (big sheets keep
  `/batch/parse`). Prompt version bumped to v5.
- **Frontend `/pro`**: persists `{messages, walk, draft, missing}` in
  sessionStorage so a reload resumes mid-walk; echoes `{drafts, cursor}` on
  every turn (typing *and* attachments); publish sends the promoter's final
  form edits back in the echoed set, appends a
  `Published "name" (event k of N).` marker message and calls the next turn
  with `cursor+1` — the server words the next intro in the user's language.
  The form gets an "event k of N" heading while walking.
- **Live-smoked** on a scratch pusher :8013 (no writes): a Spanish 3-gig
  listing → `walk.state` with 3 drafts + one form (event 1) + "He reconocido
  3 eventos…"; the publish marker advanced to event 2 without corrupting it
  and asked exactly for its gaps (city, price); "Está en Madrid y son 14
  euros" merged into event 2 only, neighbours byte-identical, gaps closed.
  Suites: shared 50, pusher 71, frontend typecheck + lint clean.
- **Browser walkthrough done (2026-08-14, real publishes, owner-approved)**,
  full stack live + throwaway pro user via the admin API (kept as a reusable
  script pattern: provision, PATCH `user_roles` to pro, delete). A Spanish
  3-gig listing → intro + "EVENT 1 OF 3" + pre-filled form; **reload mid-walk
  resumed** conversation, walk and form from sessionStorage; publish advanced
  to event 2 and asked exactly for its gaps (city, price); "Está en Barcelona
  y las entradas cuestan 14 euros" merged into event 2 only; a manual form
  edit (typing the genre) travelled through publish into the graph; after the
  last publish the page resets to the empty composer (coded:
  `setWalk(null); setMessages([])`). All 3 events verified in Aura with
  `source='pro_submission'`, the pro user's `owner_id`, embeddings, geocoded
  venues and genre; **the mid-walk 409 path verified** by re-submitting event
  1 — pusher returned 409, UI toasted "That event is already on laiive."
  Smoke events, their artists and orphaned venues deleted after; the
  throwaway user too. Two nits, not bugs: the refine model still infers
  `price_max` (14–14) from a single price, and end-of-walk has no completion
  message in the conversation — only the transient success toast before the
  reset.
- A queue (Redis/RabbitMQ) is still **not** needed: the shared writer MERGEs
  by identity, so a double submission collapses or 409s. If Redis ever
  arrives for other reasons, the cursor could move server-side without
  changing the contract.

## Other gaps 4a–4d left

- **Google sign-in**: wired and enabled (`36c1f87`); owner should click
  through once with a real Google account. The one thing not exercised is
  that real click-through — the button calls `signInWithOAuth`, the return
  leg is the stock detectSessionInUrl/onAuthStateChange path.
- ~~End-of-walk UX nit~~ closed (`2398cfa`): the final publish now leaves one
  assistant completion message (`t.pro.walkComplete`, en/es/it/ca) instead of
  wiping to the empty composer; walk/draft state still resets, and the message
  names no event details so the next listing extracts cleanly. Typecheck+lint
  verified only — spot-check in the next browser walkthrough.

### Closed this session (2026-08-14)

- **CSV fast lane deleted** (`722c415`, owner's call — the 4d walk covers
  sheets conversationally): pusher `/batch/parse` + `/batch/validate-event`,
  `agent/batch.py`, `TestBatch`, openpyxl; gateway upload/logging route
  regexes trimmed. Recoverable from git if big-sheet promoters materialize.
  The 25-event walk cap still asks for the rest in a separate message.
- **Translation sweep done** (`c5af2e0`): every page/component now reads
  `translations.ts` (en/es/it/ca) — auth, account, pro submission, event
  form, event cards, user menu, 404, plus Chat's status labels and
  429/401 messages. Dead `about`/`promoter`/`promoterCreate` sections
  dropped (in git history for when those pages return). Parameterized
  strings are *functions* on the `Translations` interface (counts/names
  inflect); the mid-walk publish marker is now in the UI language, which is
  what the pusher's `detect_language` reads on the next turn.
  detect-secrets flags `passwordPlaceholder` lines — they carry
  `pragma: allowlist secret`. Not browser-verified beyond typecheck+lint;
  the next walkthrough should spot-check es/ca on /pro and /account.

### Phase 5a — SEARCH service ✅ (commits `7484781`, `fa6699f` + feat commit; live-verified 2026-08-14)

- **D13 revised (owner call): Tavily, not Brave** — the provisioned key was
  Tavily (`TAVILY_API_KEY` in root `.env`, renamed from `BRAVE_API_KEY`), and
  Tavily returns cleaned page content, so there is no fetch-and-strip step.
- **`services/search/`** (FastAPI :8004, internal, admin-only via the
  gateway's existing `/api/admin/search/*` + `SEARCH_ENABLED=true` — gateway
  needed zero code changes): `POST /sweep` (Tavily per-city queries →
  gpt-4o-mini extraction with gpt-4o fallback *only on unparseable replies*,
  an empty page is final → past-event filter → intra-sweep dedup → graph
  identity probe + vector-similarity advisory (`event_embedding`, threshold
  0.92) → dry-run report, zero writes), `GET /reports(/{id})`,
  `POST /reports/{id}/approve` (replays the *stored* report through the
  shared writer, `source='admin_search'`, `owner_id=None`; default = only
  "new" candidates, explicit `indices` override), `POST /backfill`
  (embeddings + venue geocoding, bounded), `/health`. Endpoints are plain
  `def` (threadpool — the Phase-3 SSE lesson). Migration
  `20260814000009_search_reports.sql` (service-role only, jsonb candidates)
  pushed by the owner. `make start-search`, compose service, pre-commit
  scope all wired. `laiive_shared/drafts.py` now owns the JSON→EventDraft
  coercion helpers (moved out of pusher's converters).
- **Write gate relaxed for discovery (owner call)**: agenda pages state
  name/date/venue but rarely lineup or price, so under promoter rules every
  candidate was unapprovable (`complete: 0`). `missing_required(draft,
  source)`: `admin_search` requires only name + start_at + venue + city.
- **Live-verified end-to-end**: Barcelona sweep (4 pages, ~100 s) → 57
  drafts, 50 past filtered, 7 real candidates (Poble Espanyol agenda);
  node counts unchanged; report persisted + re-readable. Owner-approved 3
  (Cosquin Rock, Rock The Sun, Europe – Barcelona Rock Fest) → landed
  tagged `admin_search`, venue geocoded; **re-approve returned 3×
  `duplicate`, 0 created** (writer probe, idempotent); retriever surfaces
  them mixed with seed events, `source: "admin_search"` on the cards.
- Live smoke found and fixed: non-uuid `X-User-Id` broke the report PATCH
  (uuid column — now coerced to null), and a failed report update after
  committed graph writes 502'd away the write results (now 200 + warning).
- **Nits, not blockers**: (1) approve's inline embedding backfill silently
  did nothing during the live run — `/backfill` covered it (embedded 4) and
  the nightly flow is the real answer; warnings now surface in the approve
  response if it recurs. (2) admin_search events carry no genre, so
  genre-pinned queries ("rock in Barcelona") miss them — vector search and
  city/date queries find them fine. (3) One transient Aura
  `SessionExpired` 500'd an approve; the retry succeeded — the writer's
  dedup probe sits outside its try/except, so connection-level errors
  surface as 500s rather than typed results.

### Phase 5b — Prefect flows: local half ✅ verified live 2026-08-14, Cloud half pending

- **Local flow run green end-to-end**: admin service account provisioned by
  the owner (`create_admin_user.py`); root `.env` gained `SEARCH_ENABLED=true`,
  `GATEWAY_URL=http://127.0.0.1:8000`, `SUPABASE_ADMIN_EMAIL/PASSWORD`
  (env-first resolution worked — no Prefect Cloud involved).
  `python flows/city_sweep.py` from `services/search`: password grant → admin
  JWT (`user_role: admin` from the hook) → gateway `/api/admin/search/sweep` →
  three sequential city tasks, all Completed, dry-run reports persisted +
  readable. Stats: Madrid 49 new / Barcelona 28 new **+ 3 `exists`** (the
  identity probe recognized the morning's approved events — dedup proven
  through the whole loop) / Berlin 10 new. Reports awaiting owner review:
  `c34a282f` (Madrid), `53983964` (Barcelona), `388d35ed` (Berlin).
- Sweep calls took ~2–6 min per city, well inside the client's 900 s timeout
  locally; the managed-pool question stays open until the Cloud run.
- Two gotchas from the run: the ephemeral Prefect server logs a scary but
  harmless `sqlite3.OperationalError: database is locked` traceback from its
  telemetry heartbeat at startup; and an `.env` hand-edit dropped
  `TAVILY_API_KEY` first and restored a stale value second (Tavily 401s made
  sweeps "succeed" with 0 pages — a sweep that finishes in ~2 s instead of
  minutes means the search API errored per-query and the endpoint swallowed
  it into an empty report).

#### Phase 5b — approvals of the 2026-08-14 sweep reports (done)

- Owner approved the recommended cut: **54 of 88** candidates written
  (Madrid 21, Barcelona 25, Berlin 8), all embedded, all venues located
  (city-centroid fallback where Nominatim missed). Graph now holds 57
  `admin_search` events. Skipped: 23 Songkick rows whose `start_at` was the
  *scrape date* (all `2026-08-15T00:00:00`), 7 cross-source duplicates
  (The Weeknd ×5, Shakira, Ca7riel — venue-string variants the name-exact
  probe can't match), 2 non-music (stand-up, dinner-variety), 1 screening.
  Full review with per-report indices: session scratchpad
  `sweep-review-2026-08-14.md` (regenerable from the `search_reports` rows).
- **Writer bug found and fixed** (`7bb7ad0`): `neo4j_writer.write_event`'s
  artist block used `UNWIND $artists` — an empty list consumed the row, the
  final `RETURN` came back empty, and an event that had *already committed*
  was reported `status: "error", "No record returned from Neo4j"`. Berlin's
  Pop Kultur + Atonal hit it (in the graph, recorded as errors in that
  report's `write_results`). Now `FOREACH`, which iterates without touching
  cardinality. Shared suite 51 green; only reachable via `admin_search`
  (pro submissions require artists), so no pusher impact.
- The Madrid/Barcelona batch runs first 500'd with zero writes while Berlin
  passed — consistent with the known nit: the writer's dedup probe sits
  outside its try/except, so a transient Aura `SessionExpired` on the first
  candidate 500s the whole approve. Retry (after resetting the report row to
  `dry_run` via `reports.update_report`; approve marks a report `approved`
  even on partial/errored runs) succeeded end-to-end. Berlin's stored
  `write_results` still carry the two phantom "error" rows — cosmetic.
- Sweep-quality follow-ups the review surfaced (not implemented): listing-
  page date poisoning (N drafts from one page sharing one `start_at` ⇒ page
  date, drop or flag); cross-source dedup is name-exact and the 0.92 vector
  advisory fired 0 times all sweep — check whether `similar_event` runs at
  all; extractor fabricates `price_min: 0.0` from pages that state no price
  (UI will say "free"); non-music leakage (comedy/screenings/dinner shows)
  wants a type gate. Also: Ticketmaster's joke venue "Shakira Stadium" is
  now a Venue node (real venue: Iberdrola Music) — approve has no edit path.

#### Phase 5b — the scheduling rethink, implemented and verified live (2026-08-17)

**The insight**: only a *managed* work pool needs a public gateway URL. It runs
in Prefect's own container, which has no route to this machine. **Every other
Prefect execution mode is outbound-only** — the machine polls Prefect Cloud over
HTTPS, Cloud never connects in. Same direction of travel as a tunnel, but it is
the intended design instead of plumbing.

**Shape (implemented)**: Prefect Cloud is scheduler + UI + run history; the flows
execute on this machine against whatever `GATEWAY_URL` resolves to.

- **`services/search/flows/serve.py`** (~25 lines, committed): Prefect 3's
  `serve()`. Registers `city-sweep-weekly` (`Cron("0 6 * * 1",
  timezone="Europe/Madrid")`) and `backfill-nightly` (`Cron("30 4 * * *",
  timezone="Europe/Madrid")`) — same cron strings as `prefect.yaml` — and blocks,
  executing runs in-process. No work pool, no worker, no git_clone, no PAT, no
  tunnel, no image. One API trap: `Flow.to_deployment()` takes no `timezone=`
  kwarg alongside `cron=` — the timezone has to travel on a
  `prefect.schedules.Cron(...)` object passed as `schedule=`.
- **Verified live, end to end**: with the local gateway (port 8100 this session,
  see *Environment gotchas*) and search running, `uv run --group flows python
  flows/serve.py` registered both deployments in Cloud
  (`oscar-av/default` workspace) and started polling. From a second shell,
  `prefect deployment run 'backfill/backfill-nightly'` created a Cloud flow run;
  the local `serve()` process picked it up, downloaded the flow code, ran
  `run_backfill` against the gateway, and finished `Completed()` — **~7 seconds,
  Cloud-scheduled, locally-executed, exactly the shape the rethink proposed.**
  Full output is in `services/search/README.md`.
- **What it deletes**: the tunnel, `github-laiive-pat`, the "`main` is not pushed"
  problem, and the open question about a managed pool tolerating a 2–6 min
  synchronous call.
- **The one genuine tradeoff, unchanged**: scheduled runs fire only while this
  machine is awake with the stack up. Missed crons show as Late in the Cloud UI
  and get triggered by hand. `prefect.yaml` stays in the repo, dormant and
  unchanged, for when Phase 6 deploys a public gateway and the managed-pool path
  is worth reviving.
- **Not done, deliberately deferred**: containerizing `serve.py` as a compose
  `flows` service (`restart: unless-stopped`, `GATEWAY_URL: http://gateway:8000`
  via compose DNS). Two snags noted for whoever picks this up: `services/search/Dockerfile`
  syncs `--no-group flows` to stay slim, so a flows image needs its own stage or
  Dockerfile — and since the image hardening this session, the runtime stage has
  no `uv`, so it would build from the `build` stage; and it needs
  `PREFECT_API_KEY` + `PREFECT_API_URL` in root `.env` (mint a key in the Cloud
  UI). Running `serve.py` under any process supervisor (systemd, `pm2`, a plain
  `nohup`) is enough for now — proven correctness matters more than packaging
  before there's a schedule to keep.

**Why the managed route stalled — three independent walls:**

1. **No private networking.** A managed pool cannot reach a localhost gateway,
   so it needs a public URL, which does not exist until Phase 6 deploys one —
   hence a tunnel.
2. **A Cloudflare quick tunnel would have failed the test uninformatively.**
   Cloudflare's edge returns 524 after 100 s of origin silence. `/sweep` is a
   plain `def` returning one JSON blob with nothing streamed
   (`services/search/agent/api.py:44`), sweeps take 2–6 min per city, and the
   flow allows 900 s (`SWEEP_TIMEOUT`, task `timeout_seconds=1200`). The run
   would die at 100 s on *Cloudflare*, not on Prefect, and the 524 would look
   like the managed-pool timeout question answering itself in the negative.
   ngrok has no such cap and would have been the correct tunnel. Note for
   Phase 6: Railway and Fly proxies cut long silent requests the same way, so
   the 202+poll redesign that 04-plan sanctions is probably required in
   production regardless of how scheduling lands.
3. **GitHub's fine-grained PAT page was down** — "No server is currently
   available to service your request" — so `github-laiive-pat` was never minted
   and `git_clone` could not authenticate. Retry in a later session.

**Prefect Cloud state created this session — do not redo:**

- Logged in; workspace `oscar-av/default`.
- Work pool `laiive-managed` (`prefect:managed`), id `0f6bf8bf`.
- Secret blocks `supabase-admin-email`, `supabase-admin-password`.
- Variables `laiive_supabase_url`, `laiive_supabase_publishable_key`.
- All four seeded from root `.env` values.
- **Not set**: Secret block `github-laiive-pat`, Variable `laiive_gateway_url`.
  Under the local-`serve()` shape `laiive_gateway_url` can simply be
  `http://127.0.0.1:8000`, or omitted entirely since `flows/auth.py` resolves
  env first and root `.env` already has `GATEWAY_URL`.

#### Phase 5b — original design notes

- **`services/search/flows/`** (D17, thin HTTP clients of the public
  gateway — no new write path): `auth.py` (password grant → admin JWT;
  every setting resolves **env first, then Prefect** — Variables
  `laiive_gateway_url` / `laiive_supabase_url` /
  `laiive_supabase_publishable_key`, Secret blocks `supabase-admin-email` /
  `supabase-admin-password` — so a local run needs no Prefect Cloud),
  `city_sweep.py` (one task per city, retries=2, sequential on purpose —
  the sweep endpoint is a minutes-long synchronous call; markdown artifact
  tables the **new** candidates per city + approve URL; sweeps stay
  dry-run), `backfill.py` (nightly, `max_venues=100`). JWTs are minted
  *inside* tasks so they never appear as Prefect task parameters.
- **Root `prefect.yaml`**: deployments `city-sweep-weekly` (Mon 06:00
  Europe/Madrid) + `backfill-nightly` (04:30); pull = git_clone of
  `ai-safe-earth/laiive` (Secret block `github-laiive-pat`) +
  set_working_directory to `services/search`. Both flow files carry a
  dual-import guard (`flows.auth` / bare `auth`) because Prefect loads
  entrypoints as top-level modules and the sys.path root differs by loader.
- **`scripts/create_admin_user.py`** — owner-run provisioning: auth admin
  API create (or password reset if existing) + `user_roles` upsert to
  admin via PostgREST with the service-role key; the existing access-token
  hook stamps the JWT, zero new machinery.
- **Deps**: `prefect>=3.1` lives in a `flows` dependency group (dev
  includes it); the search Dockerfile now syncs `--no-group flows` so the
  API image stays slim. Setup order is in `services/search/README.md`.
- **Tests** (search 31 total, 9 new): task `.fn` + renderer with httpx
  mocked — the sync-sweep-vs-202+poll question stays open until a managed
  run shows whether the ~minutes-long call survives; 04-plan sanctions the
  poll redesign if not.

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

### Phase 6 — the k3s detour and what survived (2026-08-17)

The owner asked for CORS between the gateway and the services "for security".
CORS cannot do that — it is browser-enforced and the gateway is not a browser;
the gateway's own CORS (for the SPA origin) already exists and is the only CORS
that means anything. The real gap was that the services trust
`X-User-Id`/`X-User-Role` blindly because nothing else can reach them, enforced
only by network placement. That led to **D19: k3s on a Hetzner CX32** — decided,
built for a day, and **withdrawn the same day** when the owner weighed the priced
trade-off (a PaaS absorbs TLS/ingress/registry/secrets/probes/rollouts for
$15–25/mo; k3s converts that into ~10 working days plus a standing ops tax and
buys no capacity) and chose simple. `05-decisions.md` records the full arc; R1/R2
are reinstated (compose now, Railway/Fly at Phase 6 deploy).

**The complete k3s work is parked on branch `experiment/k3s` (`99c92d4`)**:
Kustomize base+overlays, six NetworkPolicies (default-deny + explicit allows,
including the `except:` blocks on egress without which the whole default-deny is
silently undone), SOPS+age secrets with an env-to-secret script, Traefik
timeout/`externalTrafficPolicy: Local` config, cert-manager issuers, a deploy
workflow over Tailscale, and a node bootstrap runbook in `k8s/README.md`. If k8s
ever revives, start from that branch — it is a merge, not a rewrite.

**What survived onto this branch** (committed, all suites green: shared 67,
retriever 103, pusher 67, search 32, gateway 23):

- **The service boundary, minus the cluster**: `laiive_shared/internal_auth.py` —
  the gateway injects `X-Internal-Key` (and strips any client-supplied copy in
  `proxy.ts`'s strip-list), each service verifies it with `hmac.compare_digest`;
  probes and `/health` exempt; **unset key = no-op** so local runs and tests are
  unchanged. `INTERNAL_API_KEY` is in root `.env` (generated this session — note
  the generator initially spliced it onto the `GATEWAY_URL` line because `.env`
  had no trailing newline; fixed, backup at `.env.bak.*`, now gitignored).
  **Verified live**: direct `POST /chat` to the retriever → 403, `/livez` → 200,
  the same call through the gateway → passes.
- **Replica-safety fixes that were latent bugs regardless of substrate**:
  - Gateway rate limit → Redis store when `REDIS_URL` is set (`skipOnError`, so a
    Redis outage costs quota enforcement, not uptime) + **`trustProxy: 1`** —
    without it, behind any proxy every anonymous user shares one bucket.
    **Proven both directions** with two gateway containers on one Redis.
  - Geocoder cache + the 1 req/s Nominatim gate behind a `GeocodeStore`
    (`laiive_shared/geocode_store.py`): `JsonFileGeocodeStore` (old behaviour,
    default) or `RedisGeocodeStore` (`SET NX PX` gate; **misses now expire after
    7 days** — a transient 503 used to be cached as "no such place" forever).
  - `backfill_embeddings(uids=…)` — was a full-graph scan inside every write;
    now scoped to the ≤6 nodes the write created. The unbounded sweep has one
    owner: the nightly flow.
  - `/validate-event` off the event loop (`asyncio.to_thread`) — it was blocking
    the pusher's loop for the whole geocode+write. The guarding test measures
    event-loop stall directly (first version was vacuous; the rewrite fails with
    "stalled for 0.30s" when the fix is reverted).
  - **Probe split** (`laiive_shared/health.py`): `/livez` (no I/O) and `/readyz`
    (Neo4j check, successes cached 20 s) on all three services + the gateway.
    The deep `/health` remains for humans — the retriever's calls
    `openai.models.list()` and must never be a liveness probe.
  - Retriever `requests.jsonl` deleted → one structured `log_turn` line; the
    eval record lives gateway-side in Supabase `conversation_logs`.
  - Neo4j pools budgeted (retriever 100→16 `NEO4J_MAX_POOL_SIZE`, writers 5) —
    Aura Free's real ceiling is undocumented, hence env knobs.
  - Search approve is atomic: `claim_report()` compare-and-sets
    `status=eq.dry_run` in PostgREST **before** writing; a lost race is a 409
    and writes nothing.
  - Gateway handles SIGTERM with `app.close()` — rollouts/restarts drain
    in-flight SSE instead of truncating it.
- **Hardened images** (first verified compose build since Phase 3): multi-stage,
  `python:3.13-slim` runtime without uv, uid 10001, `--no-dev --no-editable`,
  venv uvicorn with graceful-shutdown windows; retriever's `pytest` moved to the
  dev group and unused-yanked `numpy` dropped. All three verified running with a
  **read-only root filesystem** and serving both probes.
- **Compose is the deploy shape**: gateway the only published port (8000), Redis
  service (`volatile-lru` so rate-limit keys evict and geocode hits never do),
  healthchecks on `/livez`, `restart: unless-stopped`, `service_healthy`
  ordering. The dev override builds `target: build` (runtime has no uv for its
  idle shells) with healthchecks disabled.
- **CI**: `.github/workflows/ci.yml` — python matrix (ruff+pytest per service),
  node matrix (gateway/frontend), buildx of all four images with GHA cache.
  YAML-validated, fires when the branch is pushed. The k3s deploy workflow went
  to the experiment branch.
- Traps: two pre-commit fixes were needed the moment one commit spanned services
  — mypy is now **one hook per service** (retriever/pusher/search each have a
  top-level `agent` package and a single run dies on "Duplicate module named
  agent"), and `check-yaml` gained `--allow-multiple-documents`. Excluding
  `**/*.md` from the docker build context **fails the build**: `--no-editable`
  builds the laiive-shared wheel and hatchling requires the `README.md` its
  metadata names.

### Phase 6 — CI green + repo hygiene (2026-08-18, commits `cdfdc23`…`4285fcc`)

**The `ci` workflow is green for the first time since it was added.** It had never
passed; each fix exposed the next latent failure, four in total:

1. **`frontend/src/lib/cn.ts` was never in git** — the root `.gitignore`'s
   unanchored `lib/` (python packaging template) swallowed `frontend/src/lib`,
   so every fresh clone failed typecheck/build on nine `@/lib/cn` imports.
   Anchored to `/lib/`+`/lib64/`, file committed. Watch for this shape: an
   unanchored template pattern can silently untrack frontend dirs (`build/`,
   `dist/` are also unanchored but currently harmless).
2. **ruff had nothing to spawn** — it lived only in pre-commit's isolated hook
   env; `uv run ruff check .` died in all four python jobs. `ruff==0.4.9`
   (pinned to the ruff-pre-commit rev) now sits in each service's dev group.
3. **pytest died at collection with SystemExit** — no `.env` in CI and every
   config exits loudly on missing keys. The pytest step now carries dummy env
   values (the unit suites mock every client). Verified locally by hiding the
   root `.env`: shared 67, retriever 103, pusher 67, search 32, all green.
4. **The runner picked Python 3.14** (`.python-version` is gitignored, so uv
   grabs the newest) and langfuse's pydantic-v1 shim raises ConfigError there.
   Python jobs pinned via job-level `UV_PYTHON: "3.13"` to match the
   `python:3.13-slim` images.

**Repo hygiene, same session**: `product-status.md` committed (the tracker
reads it); `supabase/.temp/` gitignored; the plaintext Aura creds file moved
out of the repo to `..\laiive-data\Neo4j-2099d44c-Created-2026-08-13.txt`
(`.env` carries the live values). **CLAUDE.md rewritten** — it still described
the pre-refactor world (ReAct orchestrator, bun, the three-way port table,
Makefile targets deleted months ago); it now matches the gateway-fronted stack
and points here for the moving picture. **Makefile pruned**: dead
`test-formatting`/`test-unit`/`test-coverage` (pytest-cov was never installed)
replaced with per-service targets mirroring CI; `start-*` switched to the
`uv run --no-sync python -m uvicorn` form that works on this machine. Note:
`uv run pytest` also hits the canonicalize bug here — `uv run --no-sync
python -m pytest` is the reliable form. Left on disk, gitignored, deletable
whenever: `desktop.ini`, `.env.bak.1786991886`, `.history/`.

### Phase 6 — deploy-prep, Fly.io + Cloudflare Pages (2026-08-18 second session, commits `dbb1632`…)

Owner chose **deploy-prep code only** this session (no accounts yet) and **Fly.io**
over Railway (R2's second option). Everything lands inert; the live deploy is a
mechanical owner session following root **`DEPLOY.md`**.

- **202+poll is in** (the centerpiece — Fly's proxy cuts silent responses at
  ~60 s, and sweeps run 2–6 min): `/sweep` and `/backfill` create a `running`
  report row, answer **202** with its id, and finish in a FastAPI
  `BackgroundTasks` plain-`def` worker (threadpool; TestClient runs it
  synchronously so the terminal patch is assertable in the same call). Success
  → `dry_run` (sweep) / `done` (backfill, new `kind` column); any exception →
  `failed` + `error`. The approve CAS still matches only `dry_run`, so
  running/failed reports are unapprovable with zero new checks; a lost CAS now
  re-reads and 409s with the actual status. **Migration `20260818000010`**
  (new statuses, `error`/`kind` columns, nullable city) must be pushed by the
  owner **before** the new search code runs against Supabase — the old check
  constraint rejects `running`.
- **Flows poll**: `flows/polling.py` (`wait_for_report`, 15 s interval, 1500 s
  deadline — 600 s for backfill); tasks post with a 60 s timeout and poll
  through the gateway. `failed` raises with the recorded error. Cities stay
  sequential.
- **Fly configs** in `deploy/fly/*.toml` + `make fly-deploy-*`: gateway is the
  only public app (`http_service`, `/healthz` check, autostop **off** — SSE and
  background sweeps must not race it); retriever/pusher/search/redis are
  6PN-private with `/livez` checks. The three Python images now bind
  `--host ::` (6PN is IPv6-only; dual-stack, compose 127.0.0.1 healthchecks
  unaffected — verify on the next compose run). No `$PORT` plumbing: Fly's
  `internal_port` targets whatever the app binds. Redis stays self-hosted
  (`volatile-lru` is load-bearing for the geocode cache; Upstash can't pin it).
  Search `kill_timeout` is Fly's 300 s cap, under the image's 410 s window —
  accepted, documented in the toml and DEPLOY.md.
- **Pages readiness**: `frontend/public/_redirects` (`/* /index.html 200`,
  verified in `dist/` after build). Pages settings (root dir `frontend`, build
  `npm run build`, output `dist`, the three build-time `VITE_*` vars) are in
  DEPLOY.md — no wrangler.toml needed.
- **`.example.env` finally documents the deploy keys**: `INTERNAL_API_KEY`,
  `REDIS_URL`, `GATEWAY_URL`/`GATEWAY_HOST`, `UPLOAD_MAX_BYTES`, `PREFECT_*`,
  `SUPABASE_ADMIN_*`, `SEARCH_ENABLED`.
- **Gateway eslint** (flat config mirroring the frontend minus React plugins)
  wired as a `lint` step in the CI node matrix; first run found nothing.
- **Deliberately deferred**: CI deploy workflow (untestable without secrets —
  Make targets + runbook instead); approve stays synchronous (small human
  batches; give it 202+poll when it bites).
- Suites after: shared 67, retriever 103, pusher 67, **search 37**, gateway 23
  + lint, frontend build clean. The ruff pre-commit hook ate a
  momentarily-unused import **twice more** (`BackgroundTasks`, `polling`) —
  the same-edit rule stands. detect-secrets flags comment lines shaped
  `Secrets: see X` — reword rather than pragma.

## Geocoding and location quality (2026-08-18, third session)

Started as "find alternatives to Nominatim" and ended somewhere better: the
provider was mostly not the problem. `services/search/scripts/geocode_bakeoff.py`
is kept as a regression harness - it replays the real corpus (both
`.geocode_cache.json` files plus 22 neighbourhoods and landmarks) against
Nominatim, Photon, LocationIQ and Geoapify and **scores** each answer rather
than just counting hits.

**What the measurements said.** The query form the writer built,
`", ".join(venue, address, city)`, resolved **0 of 9** venues. The same venues
as `"venue, city"` resolved 8 of 9. The address already ends with the city, so
appending it produced `"...28009 madrid, spain, madrid"`. Photon scored better
on names (78% vs 62% short-form) but produced twice as many confidently wrong
answers, including a Barcelona venue placed in the Philippines. Raw hit rate is
a misleading metric: neither provider has a confidence score, and a wrong hit is
worse than a miss because a miss warns and falls back to the city centroid while
a wrong hit is written silently.

**Two Nominatim-only alternatives were measured and rejected**: structured
`amenity`/`city` params tied the short form exactly (8/9), ran 1.8x slower and
were worse on neighbourhoods (86% vs 100%); `limit=5` + nearest-plausible added
no recall, only converting wrongs into misses, which the guard already does.

**Google and Mapbox are not available to us**, contrary to D12's "Google if it
underperforms": Google caps lat/lng caching at 30 days and its indefinite
exception requires the cache be isolated per end user, which a shared events
graph cannot satisfy. Mapbox standard needs the pricier Permanent tier.

**What landed** (six commits, `e48f102`..`3eb5935`):

- `geocode_venue()` tries `"venue, city"` then the address then the old join,
  and takes the first *plausible* answer. `VENUE_MAX_KM = 25.0` is measured, not
  guessed: every correct answer in the corpus sat within 12.5 km of its city
  centroid and every answer beyond that was wrong. The city is geocoded first so
  it can serve as the reference.
- `address` is now required for **promoter** submissions only.
  `ADMIN_SEARCH_REQUIRED_FIELDS` deliberately excludes it - only ~26% of swept
  listings state an address, so requiring it there would reject most of
  discovery. A test pins the asymmetry.
- `services/search/agent/address_lookup.py` closes that gap without a second
  geocoder: Tavily finds the street address, Nominatim geocodes it. Injected as
  a callable so the pusher never needs Tavily. Cached in the geocode store, so a
  venue costs at most one search plus one extraction ever.
- `v.geocode_precision` (`venue` | `city_centroid` | `suspect`) and
  `v.geocode_checked_at`. The backfill is now a **repair sweep**: it also selects
  centroid fallbacks, rows predating the flag, and anything beyond
  `VENUE_MAX_KM` from its city, worst first. It previously selected only
  `WHERE v.location IS NULL`, which by construction could never see a wrong
  location. A failed attempt is stamped and not retried for 7 days so one
  unresolvable venue cannot starve the LIMIT.
- Nearby search excludes `suspect` pins and penalises `city_centroid` ones in
  the sort key only - the `distance_km` on the card stays truthful. NULL
  precision is legacy data and stays trusted.

**Verified live against Aura.** `Oasys` in Barcelona was pinned in Almeria,
**627.5 km** away - predicted from the cache before the graph was reachable, then
confirmed. One `run_backfill(max_venues=1)` traced the whole new chain: guard
rejected the cached bad hit, no address on the node, Tavily returned
`Passatge de Sant Antoni Abat 2, 08015 Barcelona`, Nominatim geocoded it.
Result **1.08 km** from centre, `precision='venue'`, and **zero venues remain
beyond the guard**.

**Still open**, in rough priority order:

1. **Named-place search is not built.** "techno in Kreuzberg" still returns
   nothing: a named place goes to `c.name_norm = $city_norm`, exact match, and
   there is no Neighbourhood node. The bake-off already measured what it needs -
   Nominatim hits 100% on neighbourhoods with a bbox every time, median diagonal
   2.8 km. Designed shape: run TEMPLATE first and geocode to a bbox only when it
   returns zero rows, so the happy path pays nothing. Note `GeocodeResult`
   currently discards Nominatim's `boundingbox`; adding it needs
   `_from_cached` to filter unknown keys first, or an old process reading a new
   cache entry raises TypeError.
2. **34 of 35 venues are unstamped.** One `run_backfill(max_venues=100)` drains
   them; expect ~10 to reach the Tavily resolver.
3. **Router gap** (found, not fixed): with a location shared, no place named and
   phrasing that is not "near me", `route()` falls to TEMPLATE with no city
   filter, so the answer contains events from every city in the graph. The fix
   is in `router.py` - default to NEARBY when a location is present and no place
   is named.
4. **Centroid pins render as confident markers** on the Leaflet card. Needs
   `geocode_precision` on the EventCard, so `services/shared/ts/protocol.ts` and
   its drift guard change too.

Also this session: `.claude/settings.json` now carries 30 `permissions.deny`
Read rules. `.claudeignore` is read by nothing (anthropics/claude-code#56997).
The two entries that matter are `.claude/worktrees/handoff-5b-cloud/`, a
complete second checkout that was returning duplicate hits on every symbol
search, and `.history/`, which holds ~20 timestamped `.env` snapshots with live
secrets. `.gitignore` gained `!.claude/settings.json` so it survives a clone;
`settings.local.json` stays ignored. **These rules load at startup, so they were
not active in the session that wrote them and have not been verified enforcing.**

## Named-place search and pin quality (2026-08-18, fourth session)

Continuation of the geocoding session. Items 1, 3 and 4 of its open list are
done; item 2 (drain the repair sweep) is the owner's, and item 5 (the
`.claude/settings.json` deny rules) is still unverified.

**The decision that was re-opened** was the relaxed write gate for discovery
(`missing_required(draft, source)`, owner call 2026-08-14). It stands - under
promoter rules discovery writes nothing, which is not a trade worth making -
but re-reading it surfaced a cost the handoff had filed as a nit. "admin_search
events carry no genre" is not a nit: `executor.py`'s genre predicate is a hard
AND over `HAS_GENRE` from the event or its artists, and a swept event has
neither, so **every genre-pinned query silently excludes every discovered
event**. The classifier turns any named genre into `genre`, so that is the most
common query shape in the product. Recommended fix, **not implemented, owner's
call**: infer genre at approve time in the search service (a human is already
in the loop, one mini call per approved event), or make the genre filter fall
back to unfiltered-plus-rank on zero rows the way the named-place leg now does.
The framing worth keeping: the gate answers "may this be written", and nothing
answers "is this good enough to show" - which is exactly the split
`geocode_precision` already solved for locations.

**What landed** (five commits, `ef9c3ff`..`9cce367`):

- **Router gap closed** (`ef9c3ff`). A shared location with no city named and
  no "near me" phrasing fell to TEMPLATE, which has no city predicate, so the
  answer mixed every city in the graph. Now routes to NEARBY - but only for
  browse-shaped asks: `city`, `country_code`, `artist` and `venue` all win over
  the location, because "when does Klangfeld play?" must not be cut to a 25 km
  circle. Cost: NEARBY only matches located venues, so an un-geocoded venue
  drops out of these answers.
- **Named-place search built** (`ec3e917`, `503cc3a`). `GeocodeResult` keeps
  Nominatim's `boundingbox`, and `_from_cached` now filters unknown keys - the
  old straight splat would have raised TypeError the first time a process read
  an entry written by a build with one more field. The retriever runs TEMPLATE
  first and only geocodes on zero rows, so the happy path pays nothing.
  `named_place_max_diagonal_km = 60` refuses region-sized boxes (Catalonia
  measures 369 km across; Berlin's municipality is ~50, so a missing city still
  resolves). The classifier is told a sub-city place goes in `city` with its
  parent ("Kreuzberg, Berlin").
- **Boxes are padded to a 2 km minimum span** (`9cce367`). Measured across the
  bake-off's 22 places: **7 resolve to a point** - every landmark plus
  Lavapiés, Poblenou and Barceloneta come back as a 10 m box, because OSM
  answers with the square that carries the name. 2 km is the median real
  neighbourhood from the same run. The cost is named and real: a 2 km square
  around Barceloneta's plaza reaches the Palau de la Música, in the next
  barrio.
- **`geocode_precision` on the EventCard** (`630db0b`), TS mirror and drift
  guard included. A `city_centroid` pin opens the map zoomed out with a circle
  instead of a marker, says so in one line, and sends "open in Google Maps" to
  the venue name rather than to coordinates known to be roughly right. A
  `suspect` pin loses its coordinates in `rows_to_cards` - nearby already
  refuses to match one, but template and vector have no location predicate, so
  that is the layer where the guarantee has to hold.

**What the live smoke found** (read-only against Aura, and the reason this
session has a fifth commit): **eight Barcelona venues share one identical
pin** - Razzmatazz, Palau Sant Jordi, Sant Jordi Club, Marula, Queen's, Ocaña,
La Nau, Estadi Olímpic - and that pin is exactly Nominatim's answer for
`"barcelona"`. Every one of those lookups missed and fell back to the city.
Madrid has six more sitting on its centroid. **No existing check sees them**:
the 25 km guard passes (the city centre is near the city), `geocode_precision`
is NULL on all of them (34 of 35 venues predate the flag), and the graph-side
distance test misses the Barcelona eight because `c.location` is **888 m** from
what the geocoder returns for the same name today.

So two guards were added, neither depending on the flag:

- The **repair sweep** compares the venue answer with the city answer it
  already holds and stamps `city_centroid` instead of `venue` when they
  coincide. Without this, draining the backlog would mark all eight *verified*
  and stop the sweep ever revisiting them - worse than leaving them unstamped.
- The **bbox leg** excludes a pin shared with another venue in the same city
  (scoped to the bound `c`, so it reads one city's venues, not the label).
  Two venues cannot share a doorway.

Verified live after the fix: "Kreuzberg, Berlin" returns Columbia Theater and
Uber Arena; "Malasaña, Madrid" returns Sala El Sol only (the Metropolitano
stadium, which sits on Madrid's centroid, is correctly gone); "Poblenou,
Barcelona" returns Razzmatazz once padded; "Catalonia" is refused as too big.

**The drain ran** (owner, same session): `run_backfill(max_venues=100)` →
`venues_geocoded=27, venues_flagged=0, warnings=[]`. Tavily resolved addresses
for nine venues that OSM has no POI for (Sonnenraum, Globe Berlin, Frannz Club,
Vistalegre Arena, Sala Mon Live, Shakira Stadium, Marula, La Nau). **All 35
venues are now stamped `venue`; the collapse is gone** - the Barcelona eight
have eight distinct, plausible pins, and the Madrid six moved off the centroid.
`Queen's` needed the guard: its name form landed 42 km out in Vilanova and was
rejected, and the Tavily address resolved it instead.

**The drain then exposed the next layer.** `Sant Jordi Club` came back **17.7
km** from Barcelona - inside the 25 km guard, so accepted and stamped `venue` -
while the correct Montjuïc address the graph already held resolves **3.1 km**
out, beside the Palau Sant Jordi it shares a wall with. The name form was tried
first, was merely plausible, and nothing asked the address form. Preferring the
address instead is *not* the fix, and the corpus says so: `Sala El Sol` is 0.3
km by name and **25 km** by address, and two venues have no address answer at
all. Fixed in `3f4ffd1`: an answer beyond `VENUE_OUTLIER_KM` (12.5 km, the same
distribution `VENUE_MAX_KM` was cut from) no longer ends the search; the
remaining forms and the resolver are still tried and the nearest plausible
answer wins. **Replayed dry against all 35 venues: exactly one moves** (Sant
Jordi Club, 18.1 → 3.0 km), nothing else shifts by 200 m.

**Still open**, in rough priority order:

1. **Re-run the sweep for `Sant Jordi Club`** so the fix reaches the graph. It
   is stamped `venue` and checked today, so the selector will not pick it up:
   `uv run --no-sync python scripts/recheck_venue.py "Sant Jordi Club"` from
   `services/search`. One Aura write.
2. **Genre: the earlier claim was wrong, and the real gap is smaller.**
   Measured on the live graph: **43 of 57** discovered events are already
   reachable by a genre query and 39 carry their own tag, so extraction has
   been filling `genre` for a while. "admin_search events carry no genre" was
   true of the Phase 5a sweep only. What was actually broken:
   - **Composite slugs did not answer for their parts** (`28ddaf5`). Extraction
     emits what the page says, so `pop-rock` (4 artists, 4 events) answered
     neither "rock" nor "pop". The predicate now matches a slug that is the
     asked genre or contains it as a hyphen-separated part: **"rock" goes 7 →
     18 events and "pop" 16 → 23**; techno, jazz, rap, electronic and
     indie-rock are unchanged. (The commit message says 7 → 10 and "pop
     unchanged" - both were measured through `max_results_limit = 10`, which
     caps every template answer at ten rows. **Any recall measurement has to
     strip `LIMIT $limit` first**, or two different numbers both read as 10.)
   - **13 of 43 artists carry no genre**, hiding 14 events. Fixed by tagging
     the *artist*, which reaches every event they play, now and later
     (`27fd414`): `scripts/tag_artist_genres.py`, dry by default. The model
     named 12 of 13 on the live backlog and declined the one it did not know.
     **Run by the owner**: 12 tagged, and reachability went **43 → 55 of 57**.
     The only two left are the artist the model declined ("The Swingin'
     Hermlins") and "Music Bank Barcelona", which has no artist at all. No
     duplicate Genre node appeared - Two Feet joined the existing `electronic`
     rather than creating a second one, which is what routing the write
     through `laiive_shared` was for.
   - **Two spellings, two nodes** (`bd9643a`). `electronica` sat beside
     `electronic` and `rnb` beside `r-b-pop-new-wave`, so which word a person
     typed decided what they found - structural, not a one-off, since the
     source pages are Spanish and Catalan as often as English. `genre_slug`
     collapses a short alias list on write; `genre_family` gives the query
     side every spelling already stored, because canonicalising on write only
     helps rows written after it. Live: **"rnb" 0 → 4** events, **"electronic"
     4 → 7**, both spellings equal.
   - Matching is on **hyphen boundaries**, not `split()` parts: a variant can
     itself be several parts (`r-b` must reach `r-b-pop-new-wave`). The
     boundary is the honesty condition - "rap" must not answer 'trap', and on
     live data it does not (rap 1, trap 1, reggae 2, reggaeton 1, each to
     itself).
   - **Non-genres slug to empty**: `various`, `live`, `music`, `other`. A tag
     nobody can query for passes the has-a-genre test while telling a reader
     nothing. The executor drops the clause rather than matching nothing, so a
     junk constraint stops filtering instead of emptying the answer ("various"
     returns all 59 upcoming events, not zero). Regional labels (`flamenco`,
     `punjabi`) are deliberately kept - more scene than style, still
     informative.
   Left in the graph: the `various` and `ukrainian` nodes already written, one
   event each. Nothing queries them and cleaning them is an Aura write for no
   retrieval gain.
3. **Duplicate events in the graph**: the smoke showed "The Weeknd" three times
   at the same venue and "Estadi Olímpic" / "Estadi Olímpic Lluis Companys" as
   two Venue nodes. Cross-source dedup was already on the sweep-quality list;
   this is evidence it is real. Related: `Razzmatazz` and `Sala Razzmatazz 1`
   now share a pin *correctly* (a room inside the club), which the bbox leg's
   shared-pin rule reads as a collapse and drops from named-place results. The
   rule earns its keep while pins are unverified; once dedup exists, prefer
   modelling the room as part of the venue.
4. **`Shakira Stadium` is not a venue.** It sits 9.5 km from Madrid's centre
   with no address, and the name is almost certainly a listing-page artefact.
   Extraction quality, not geocoding.
5. **The composer is not told a card matched by box rather than by city**, so
   it will happily phrase a padded-box hit as "in Barceloneta". Only matters
   once padding is common.
6. Confirm the `.claude/settings.json` deny rules enforce after a restart
   (carried over, still unverified).

## Environment gotchas (this machine)

**Re-checking one venue after a geocoder fix.** The repair sweep only selects
venues that are unstamped, non-`venue`, or last checked over 7 days ago, so the
pin a fix would correct is exactly the one the selector no longer offers.
`services/search/scripts/recheck_venue.py` clears the stamp and re-runs the
sweep (an Aura write):

```
cd services/search
uv run --no-sync python scripts/recheck_venue.py "Sant Jordi Club"
```


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
- Long-lived dev servers from an earlier session go stale and cost real time:
  a retriever started before the `.env` repair reported `openai: error` on
  `/health` while the key worked fine via curl, and a Vite from a previous
  session held :8081 serving the *deleted* app. Before debugging anything you
  did not start this session:
  `Get-NetTCPConnection -LocalPort 8000,8002,8003,8081 -State Listen | %{ Get-Process -Id $_.OwningProcess | select Id,ProcessName,StartTime }`
- Browser automation: `computer`'s `type` action does not reach this app's
  inputs — use `form_input` with a ref from `read_page`, and click buttons by
  `ref` rather than coordinates (small targets get missed).
- Writes to Supabase (`db push`, MCP `apply_migration`/`execute_sql` DDL) are
  refused by the permission classifier — hand the owner the command to run.
- MCP `aura-neo4j` points at `2099d44c` (write access; ask owner before
  writing data). Playwright + claude-in-chrome MCPs available.
  **Its host stopped resolving this session** (`2099d44c.mcp-instances.neo4j.io`
  → ENOTFOUND) while the database itself was perfectly reachable on
  `2099d44c.databases.neo4j.io`. If the MCP is down, query through the service:
  `cd services/retriever && PYTHONPATH=. uv run python -c "…Neo4jClient()…"`.
- `PYTHONPATH=.` is needed for ad-hoc `uv run python` scripts in the services
  (`agent` is not an installed package), and piping their output through `grep`
  trips Windows binary detection on accented text — redirect to a file and
  `grep -a` it instead.
- The **ruff `--fix` pre-commit hook deletes an import the moment it is
  momentarily unused**. It bit twice this session: adding an import in one edit
  and its first use in the next leaves the file broken with a `NameError` that
  only surfaces at test time. Add the import and the usage in the same write, or
  re-check the import block afterwards.
- ~~The `.claude` PostToolUse hook path is stale~~ **false alarm, closed
  2026-08-17**: `.claude/settings.local.json` already uses
  `$CLAUDE_PROJECT_DIR/.claude/hooks/ruff_on_edit.py`, not an absolute path. The
  stale absolute path lived only in a leftover git worktree at the old
  `DIALOGOO` location (`git worktree list` marked it `prunable`); removed with
  `git worktree remove --force`. If this resurfaces, check `git worktree list`
  for another orphan before touching the hook config.
- **The `prefect` CLI crashes on Windows while printing.** `work-pool create`
  raised `UnicodeEncodeError: 'charmap' codec` from `rich`'s cp1252 console
  writer *after* creating the pool — the command succeeded, only the output
  died. Prefix Prefect (and any rich-using) commands with `PYTHONIOENCODING=utf-8`.
- `uv run` inside `services/search` warns that
  `VIRTUAL_ENV=…\laiive\.venv` does not match the project env `.venv` — harmless,
  it ignores the outer one.
- **Gateway health is `/healthz`**, not `/health` (which 404s) —
  `services/gateway/src/server.ts:72`. The Python services use `/health`.
- `winget` is not on PATH in this shell, and the permission classifier blocks
  `Invoke-WebRequest` of an `.exe`, so **Claude cannot install cloudflared** —
  the owner installs it if a tunnel is ever needed again.
- The classifier also blocks piping `gh auth token` into a Prefect Secret block.
  Useful fallback while GitHub's PAT page is down: `gh` is logged in as
  `OscarArroyoVega` with `repo` scope and can read `ai-safe-earth/laiive`, so
  `gh auth token` works as a stand-in for the fine-grained PAT — the owner runs
  it. It is much broader scope (every repo he can reach), so swap in the real
  fine-grained PAT once GitHub recovers.
- Background dev servers survive their launcher: stopping the wrapped
  `npm run dev` / `uv run uvicorn` task left `node` and `python` still holding
  :8000 and :8004. Kill by PID from `Get-NetTCPConnection` after stopping a task.
- **`uv run uvicorn …` now fails** with `Failed to canonicalize script path` on this
  machine. Use `uv run --no-sync python -m uvicorn …` with a separate `uv sync`.
  The `make start-*` targets still use the broken form.
- **Other projects squat the stack's ports.** An `A02_VaiVia` uvicorn holds :8000
  and a `laiive-global-workspace` container holds :8002/:8003. Everything is
  env-overridable, so shift rather than kill: `GATEWAY_PORT`, `RETRIEVER_URL`,
  `PUSHER_URL`, `CORS_ALLOW_ORIGINS` on the gateway and inline `VITE_API_URL` for
  Vite (Vite prioritises inline `VITE_*` over `.env` files).
- **`npm run dev -- --port 8081` silently loses the flags** in PowerShell — Vite
  starts on 5173 and treats `8081` as a root directory. Call `npx vite --port 8081
  --strictPort` instead.
- The shared venv had `laiive-shared` installed from the repo's **old DIALOGOO
  path**, which made pytest tracebacks cite files that no longer exist. `uv sync`
  in `services/shared` fixed it; suspect this first if a traceback names a path
  outside this repo.
- Docker Desktop's loopback: `127.0.0.1:<published>` sometimes refuses while
  `localhost:<published>` works. Use `localhost` for published container ports.
- The **ruff `--fix` pre-commit hook bit four more times** this session, always the
  same way: add an import in one edit and its first use in the next, and the hook
  deletes the import in between. It is not hypothetical — grep for the symbol after
  every import-only edit, or write the import and its usage in a single edit.
- `uv run pytest` fails with "Failed to canonicalize script path" exactly like
  `uv run uvicorn` does. **Use `uv run --no-sync python -m pytest -q`.**
- `ruff-format` runs as a pre-commit hook and rewrites staged files, which aborts
  the commit. Re-`git add` the same paths and commit again; it passes the second
  time.
- **DNS on this machine flaps.** `getaddrinfo` failed intermittently for the Aura
  host, `docs.claude.com` and `operations.osmfoundation.org` in one session,
  while a tight probe loop resolved 10/10. It killed three `run_backfill` runs at
  driver-construction time. Pre-warm with `socket.gethostbyname` and retry in
  process - the sweep is idempotent by uid, so retrying is safe.
- The **Aura free instance auto-pauses**. While paused its DNS record disappears
  entirely; while resuming, reads route to a follower but writes fail with
  "No write service currently available". Neither is a code fault.

## Standing rules from the owner

- Terse replies, no end-of-turn summaries. Propose a plan before
  implementing; explain real trade-offs. Every decision needs owner approval.
- Conventional Commits (commit-msg hook enforces), lowercase subject.
- Never read `.history/` or `legacy/`.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-08-18",
  "deadline": null,
  "people": [
    "oscar"
  ],
  "plans": [
    {
      "name": "refactor",
      "path": "docs/refactor/",
      "status": "active"
    }
  ],
  "phases": [
    {
      "name": "Phase 0 - hygiene",
      "status": "done",
      "start": null,
      "end": "2026-08-12",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-12",
          "text": "D4 keys rotated, ports unified on 8002/8003, LICENSE proprietary"
        }
      ]
    },
    {
      "name": "Phase 1 - graph schema + seed",
      "status": "done",
      "start": null,
      "end": "2026-08-12",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-12",
          "text": "setup_schema.py is the DDL source of truth for Aura 2099d44c"
        }
      ]
    },
    {
      "name": "Phase 2 - backend contracts + redesign",
      "status": "done",
      "start": null,
      "end": "2026-08-13",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-13",
          "text": "D10 services/shared as the laiive-shared package, typed SSE protocol with a TS mirror"
        },
        {
          "date": "2026-08-13",
          "text": "ReAct orchestrator deleted for classifier -> router -> executor -> composer"
        },
        {
          "date": "2026-08-13",
          "text": "Pusher state is client-carried, no TTL session store"
        }
      ]
    },
    {
      "name": "Phase 3 - gateway + auth + ownership",
      "status": "done",
      "start": null,
      "end": "2026-08-13",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-13",
          "text": "D7 anonymous chat allowed, role travels in the JWT via a custom access token hook"
        },
        {
          "date": "2026-08-13",
          "text": "D15 fresh Supabase project pjlcfdyheyubsemwlzzv, conversation logging is request-side only"
        }
      ]
    },
    {
      "name": "Phase 4 - frontend, multimodal, walk",
      "status": "done",
      "start": null,
      "end": "2026-08-14",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-14",
          "text": "D1 fresh Vite + React app on the v2 protocol, D9 Leaflet maps"
        },
        {
          "date": "2026-08-14",
          "text": "A spreadsheet is a longer conversation, not a batch screen - CSV fast lane deleted"
        },
        {
          "date": "2026-08-14",
          "text": "Multi-event walk cursor lives client-side (option A)"
        },
        {
          "date": "2026-08-14",
          "text": "Profile data goes direct to Supabase under RLS, not through the gateway"
        }
      ]
    },
    {
      "name": "Phase 5 - SEARCH service + scheduling",
      "status": "done",
      "start": "2026-08-14",
      "end": "2026-08-17",
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-14",
          "text": "D13 revised: Tavily instead of Brave, it returns cleaned page content"
        },
        {
          "date": "2026-08-14",
          "text": "Write gate relaxed for admin_search: name + start_at + venue + city only"
        },
        {
          "date": "2026-08-14",
          "text": "Sweeps stay dry-run, a human approve is required before any graph write"
        },
        {
          "date": "2026-08-14",
          "text": "D17 Prefect Cloud managed pool, flows are thin HTTP clients of the public gateway"
        },
        {
          "date": "2026-08-14",
          "text": "54 of 88 swept candidates approved into the graph"
        },
        {
          "date": "2026-08-17",
          "text": "A managed pool cannot reach a localhost gateway; recommended shape is Prefect Cloud as scheduler and UI only, with flows executing locally via serve() - owner approval pending, nothing implemented"
        },
        {
          "date": "2026-08-17",
          "text": "Cloudflare quick tunnel rejected: its 100 s origin-silence cap would 524 the 2-6 min synchronous sweep and misattribute the failure to Prefect; ngrok has no such cap"
        },
        {
          "date": "2026-08-17",
          "text": "Scheduling implemented as flows/serve.py (Prefect 3 serve()): both cron deployments registered in Prefect Cloud, executed locally against the gateway - verified live end to end, a Cloud-triggered backfill run completed in ~7s"
        }
      ]
    },
    {
      "name": "Phase 6 - CI/CD + deploy",
      "status": "active",
      "start": "2026-08-17",
      "end": null,
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-14",
          "text": "D18 frontend host is Cloudflare Pages; services on Railway/Fly per R2"
        },
        {
          "date": "2026-08-17",
          "text": "CORS between the gateway and the services was rejected as a security control: it is browser-enforced and the gateway is not a browser, so it would change nothing about who can reach 8002/8003"
        },
        {
          "date": "2026-08-17",
          "text": "D19 (k3s on one Hetzner CX32) was decided and withdrawn the same day after pricing the trade-off; R1 and R2 reinstated - compose now, Railway/Fly at deploy time. The full k8s work is parked on branch experiment/k3s (99c92d4)"
        },
        {
          "date": "2026-08-17",
          "text": "The gateway-services boundary is a shared INTERNAL_API_KEY the gateway injects and each service verifies, working identically under compose; an unset key is a no-op for local runs"
        },
        {
          "date": "2026-08-17",
          "text": "Distributed state (gateway rate limit, geocoder cache and 1 req/s gate) goes to one Redis in compose when REDIS_URL is set; unset keeps the old per-process behaviour"
        },
        {
          "date": "2026-08-17",
          "text": "Images hardened: multi-stage, non-root uid 10001, no dev deps, venv uvicorn, verified read-only rootfs; compose gained Redis, healthchecks and restart policies - first verified compose build since Phase 3"
        },
        {
          "date": "2026-08-18",
          "text": "CI green for the first time: gitignore lib/ anchored so frontend/src/lib/cn.ts is tracked, ruff==0.4.9 pinned in every dev group, dummy env keys on the pytest step, python jobs pinned to 3.13 via UV_PYTHON"
        },
        {
          "date": "2026-08-18",
          "text": "Repo hygiene: product-status.md tracked, supabase/.temp ignored, Aura creds file moved to ../laiive-data, CLAUDE.md rewritten to the post-refactor stack, Makefile pruned to CI-mirroring targets"
        },
        {
          "date": "2026-08-18",
          "text": "Owner chose Fly.io over Railway (R2 second option) for the service deploy; deploy-prep landed code-only with no accounts: deploy/fly tomls, make fly-deploy targets, DEPLOY.md runbook"
        },
        {
          "date": "2026-08-18",
          "text": "202+poll implemented: sweep and backfill answer 202 with a running report row and finish in a BackgroundTasks worker; flows poll GET /reports/{id}; approve CAS unchanged so running/failed reports stay unapprovable. Migration 20260818000010 must be pushed before the new search code runs"
        },
        {
          "date": "2026-08-18",
          "text": "Python images bind :: for Fly 6PN (IPv6-only); no $PORT plumbing since internal_port targets the bound port; redis stays self-hosted because volatile-lru is load-bearing for the geocode cache"
        },
        {
          "date": "2026-08-18",
          "text": "Gateway eslint added and the CI node matrix lints both dirs; CI deploy workflow deferred as untestable without secrets"
        }
      ]
    },
    {
      "name": "Phase 7 - geocoding and location quality",
      "status": "active",
      "start": "2026-08-18",
      "end": null,
      "plan": "refactor",
      "decisions": [
        {
          "date": "2026-08-18",
          "text": "Nominatim kept, Photon rejected. Measured on the real corpus: the writer's joined query form resolved 0 of 9 venues and 'venue, city' resolved 8 of 9, so the query string was the bug, not the provider"
        },
        {
          "date": "2026-08-18",
          "text": "A wrong hit is worse than a miss: a miss warns and falls back to the city centroid, a wrong hit is written silently. VENUE_MAX_KM = 25 km rejects answers outside the stated city, measured from the distribution (every correct answer within 12.5 km, everything beyond wrong)"
        },
        {
          "date": "2026-08-18",
          "text": "Two Nominatim-only alternatives measured and rejected: structured amenity/city params tie the short form at 8/9 but run 1.8x slower and are worse on neighbourhoods; limit=5 nearest-plausible adds no recall over the guard"
        },
        {
          "date": "2026-08-18",
          "text": "D12 revised: Google is not actually available as the fallback. It caps lat/lng caching at 30 days and its indefinite exception requires per-end-user isolation, which a shared events graph cannot satisfy; Mapbox standard has the same problem"
        },
        {
          "date": "2026-08-18",
          "text": "address is required for promoter submissions but deliberately not for admin_search - only ~26% of swept listings state one, so requiring it there would reject most of discovery"
        },
        {
          "date": "2026-08-18",
          "text": "The coverage gap is missing address data, not missing geocoding, so it is closed with a Tavily address resolver in the search service rather than a second geocoding provider; injected as a callable so the pusher never needs Tavily"
        },
        {
          "date": "2026-08-18",
          "text": "v.geocode_precision and v.geocode_checked_at added; the backfill became a repair sweep that can finally see wrong locations (the old WHERE v.location IS NULL could not, since a wrong pin is not null). Failed attempts are stamped and skipped for 7 days so one unresolvable venue cannot starve the LIMIT"
        },
        {
          "date": "2026-08-18",
          "text": "Verified live: Oasys was pinned 627.5 km from Barcelona in Almeria; one repair run moved it to 1.08 km via the Tavily resolver, and zero venues now sit beyond the guard"
        },
        {
          "date": "2026-08-18",
          "text": ".claudeignore is read by nothing (anthropics/claude-code#56997); .claude/settings.json permissions.deny is the working mechanism, negated in .gitignore so it survives a clone. Not yet verified enforcing - settings load at startup"
        },
        {
          "date": "2026-08-18",
          "text": "The relaxed admin_search write gate was re-opened and stands, but the missing genre on swept events is not a nit: the genre predicate is a hard AND over HAS_GENRE, so every genre-pinned query silently excludes every discovered event. Fix recommended (infer genre at approve, or fall back on zero rows), not implemented, owner's call"
        },
        {
          "date": "2026-08-18",
          "text": "Router: a shared location becomes a filter only for browse-shaped asks. city, country_code, artist and venue win over it, since an artist question must not be cut to a 25 km circle"
        },
        {
          "date": "2026-08-18",
          "text": "Named-place search runs TEMPLATE first and geocodes to a bbox only on zero rows, so the happy path pays nothing. 60 km diagonal ceiling refuses region-sized boxes (Catalonia is 369 km, Berlin ~50)"
        },
        {
          "date": "2026-08-18",
          "text": "Place boxes are padded to a 2 km minimum span: 7 of the 22 measured places resolve to a point, since OSM answers with the square that carries the name. Cost accepted: a padded box reaches into the next barrio"
        },
        {
          "date": "2026-08-18",
          "text": "_from_cached filters unknown keys before hydrating GeocodeResult, so adding a cached field can no longer TypeError a process reading an entry a newer build wrote"
        },
        {
          "date": "2026-08-18",
          "text": "geocode_precision travels on the EventCard; a suspect pin loses its coordinates in rows_to_cards, because template and vector have no location predicate and that is the layer where the guarantee has to hold"
        },
        {
          "date": "2026-08-18",
          "text": "Found live: eight Barcelona venues share one pin, which is Nominatim's answer for 'barcelona', and six Madrid venues sit on its centroid. The 25 km guard, the precision flag and the c.location distance test all miss them (c.location is 888 m from the geocoder's current answer). Guards added at both ends: the sweep stamps city_centroid when the venue answer equals the city answer, and the bbox leg excludes a pin shared by two venues in the same city"
        },
        {
          "date": "2026-08-18",
          "text": "Repair sweep drained: run_backfill(max_venues=100) geocoded 27 venues, nine of them via the Tavily address resolver. All 35 venues now stamped 'venue' and the shared-pin collapse is gone - the Barcelona eight have eight distinct pins"
        },
        {
          "date": "2026-08-18",
          "text": "The drain exposed that a merely-plausible answer wins by being tried first: Sant Jordi Club landed 17.7 km out by name while its stored address resolves 3.1 km out. Preferring the address is not the fix (Sala El Sol is 0.3 km by name, 25 km by address). An answer beyond VENUE_OUTLIER_KM=12.5 no longer ends the search; the nearest plausible form wins. Dry replay over all 35 venues moves exactly one"
        },
        {
          "date": "2026-08-18",
          "text": "Correction: 43 of 57 admin_search events are already reachable by a genre query and 39 carry their own tag. 'admin_search events carry no genre' was true of the Phase 5a sweep only, and the earlier reading of it as the largest retrieval gap was wrong"
        },
        {
          "date": "2026-08-18",
          "text": "The genre predicate now matches a slug that is the asked genre or contains it as a hyphen-separated part, because extraction emits what the page says: 'pop-rock' answered neither 'rock' nor 'pop'. Measured: 'rock' 7 -> 10 events, nothing else changes"
        },
        {
          "date": "2026-08-18",
          "text": "The remaining genre gap is 13 untagged artists hiding 14 events, fixed by tagging the artist rather than the event so it reaches their future events too. genre_lookup asks one batched LLM call with abstention as the safe answer; the write goes through laiive_shared.tag_artist_genres so the Genre MERGE matches write_event's. Owner runs scripts/tag_artist_genres.py --write"
        },
        {
          "date": "2026-08-18",
          "text": "Artist tagging run: 12 artists tagged, genre reachability 43 -> 55 of 57 events, no duplicate Genre nodes. Corrected measurement: the token split takes 'rock' 7 -> 18 and 'pop' 16 -> 23, not 7 -> 10 with pop unchanged - the first pass was measured through max_results_limit=10, which caps every template answer at ten rows"
        },
        {
          "date": "2026-08-18",
          "text": "Genre vocabulary: genre_slug collapses a short alias list ('electronica'->'electronic', 'r-b'->'rnb') and rejects non-genres ('various', 'live'); genre_family expands a query to every spelling already stored. Matching is on hyphen boundaries rather than split() parts so a multi-part variant reaches a composite slug while 'rap' still does not answer 'trap'. Live: rnb 0 -> 4 events, electronic 4 -> 7"
        }
      ]
    }
  ],
  "blockers": [
    {
      "text": "GitHub's fine-grained PAT page was down when github-laiive-pat was needed for the prefect.yaml managed-pool path; moot now that scheduling runs via flows/serve.py, relevant again only if the managed pool is revived at Phase 6",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-17"
    },
    {
      "text": "Google sign-in is wired and enabled but the real click-through has never been exercised",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-14"
    },
    {
      "text": "prefect.yaml git-clones main of ai-safe-earth/laiive at run time, but only refactor/foundation is pushed - moot under the local serve() shape, blocking again if the managed pool is revived at Phase 6",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-14"
    },
    {
      "text": "The Aura free instance auto-pauses and its DNS record disappears while paused; on resume reads work but writes fail with 'No write service currently available'. Cost three aborted repair runs before it settled",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-18"
    }
  ],
  "nextSteps": [
    {
      "title": "Re-run the repair sweep for Sant Jordi Club so the outlier fix reaches the graph: services/search/scripts/recheck_venue.py 'Sant Jordi Club' (clears the stamp the selector would otherwise skip). One Aura write",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 7 - geocoding and location quality",
      "plan": "refactor"
    },
    {
      "title": "Genre on admin_search events: swept events have no genre and no artists, so the executor's HAS_GENRE predicate excludes them from every genre-pinned query. Infer genre at approve time, or fall back to unfiltered-plus-rank on zero rows",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 7 - geocoding and location quality",
      "plan": "refactor"
    },
    {
      "title": "Cross-source dedup: the live smoke showed one event three times and 'Estadi Olimpic' / 'Estadi Olimpic Lluis Companys' as two Venue nodes",
      "est": 2,
      "owner": "oscar",
      "phase": "Phase 5 - SEARCH service + scheduling",
      "plan": "refactor"
    },
    {
      "title": "Tell the composer when a card matched by bounding box rather than by city, so a padded-box hit is not phrased as 'in Barceloneta'",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 7 - geocoding and location quality",
      "plan": "refactor"
    },
    {
      "title": "Confirm the new .claude/settings.json deny rules actually enforce after a restart; if .history/ is still readable, fall back to a PreToolUse hook",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 7 - geocoding and location quality",
      "plan": "refactor"
    },
    {
      "title": "Optional: containerize flows/serve.py as a compose flows service (needs its own Dockerfile stage since the hardened search runtime has no uv, plus PREFECT_API_KEY/PREFECT_API_URL in root .env)",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 5 - SEARCH service + scheduling",
      "plan": "refactor"
    },
    {
      "title": "Sweep-quality follow-ups: listing-page date poisoning, cross-source dedup, fabricated price_min, non-music type gate",
      "est": 2,
      "owner": "oscar",
      "phase": "Phase 5 - SEARCH service + scheduling",
      "plan": "refactor"
    },
    {
      "title": "Click through Google sign-in once with a real account",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 4 - frontend, multimodal, walk",
      "plan": "refactor"
    },
    {
      "title": "Push migration 20260818000010 (search_reports lifecycle) - required before the new search code runs against Supabase",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 6 - CI/CD + deploy",
      "plan": "refactor"
    },
    {
      "title": "Owner deploy session per root DEPLOY.md: fly apps + secrets + deploy order, Pages project, CORS/redirect stitching, smoke checklist (202+poll prep is done)",
      "est": 2,
      "owner": "oscar",
      "phase": "Phase 6 - CI/CD + deploy",
      "plan": "refactor"
    },
    {
      "title": "Local 202+poll smoke against the live stack once the migration is pushed (compose up also verifies the --host :: healthchecks)",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 6 - CI/CD + deploy",
      "plan": "refactor"
    },
    {
      "title": "'Shakira Stadium' is a listing-page artefact, not a venue: 9.5 km from Madrid's centre, no address. Extraction quality, not geocoding",
      "est": 1,
      "owner": "oscar",
      "phase": "Phase 5 - SEARCH service + scheduling",
      "plan": "refactor"
    }
  ],
  "sessions": [
    {
      "date": "2026-08-13",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-14",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-17",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-17",
      "model": "fable-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-17",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "fable-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "fable-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    },
    {
      "date": "2026-08-18",
      "model": "opus-5",
      "credits": null,
      "person": "oscar",
      "hours": null
    }
  ]
}
```
