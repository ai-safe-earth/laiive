# HANDOFF — refactor status (updated 2026-08-14, third session)

Continuation point for the laiive refactor. Read this first, then
`04-plan.md` (phases) and `05-decisions.md` (all decisions, D1–D18 + budget).
Branch: **`refactor/foundation`** (from `connect-to-ui`). Nothing pushed yet;
canonical remote for future PRs = `origin` (ai-safe-earth/laiive) — the remote
*named* `laiive` is the personal fork, do not push there.

**Where things stand**: phases 0–3 done and verified live; phase 4a (consumer
chat), 4b (multimodal submission), 4c (legacy deletion + account page) and
**4d (the multi-event walk)** are done — 4d is live-smoked against the real
LLM but its UI has not had a browser walkthrough yet (see *Phase 4d*).
Nothing is deployed yet. To run the stack locally: gateway :8000, retriever
:8002, pusher :8003, frontend :8081 (see *Environment gotchas* — stale
servers from earlier sessions are a recurring time sink).

**Next up**: **Phase 5** (SEARCH service + Prefect sweeps) — see *Phase 4
plan of record* and 04-plan.md. The only Phase-4 leftover is the Google
click-through by the owner. Earlier this session: CSV fast lane **deleted**
(owner's call, `722c415`), translation sweep done (`c5af2e0`), end-of-walk
completion message added (`2398cfa`).

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

## Standing rules from the owner

- Terse replies, no end-of-turn summaries. Propose a plan before
  implementing; explain real trade-offs. Every decision needs owner approval.
- Conventional Commits (commit-msg hook enforces), lowercase subject.
- Never read `.history/` or `legacy/`.
