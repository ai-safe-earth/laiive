# 01 — Repo review

Analysis date: 2026-08-13, branch `connect-to-ui`. Everything below was verified by
reading the code and by running the app (frontend + both services + live Aura MCP).
`legacy/` was not read (hard rule); it is only inventoried as tracked dead weight.

## 1. What was observed by running the app

- Frontend runs (Vite). Note: `bun` is **not installed** on this machine; npm + node
  work. Port 8080 is occupied by a local EnterpriseDB web server, so the dev server was
  run on 8081. The npm-installed `node_modules` was missing the Windows rollup native
  package (`@rollup/rollup-win32-x64-msvc`) — the tree was installed on another
  platform/package manager.
- UX: pure black background, hot-pink accent (`#FF2AA0`), 🫦 logo, chat-first single
  screen. Bottom bar: mic, "Tell me what you're looking for…" input, pink send button.
  Header: logo, `laiive.pro` link, user icon → `/auth`.
- `/auth`: "Welcome back", Continue with Google, email+password, sign-up toggle
  (Supabase). `/promoters`: marketing landing ("Small stages. Big connections.", video
  placeholder, "Push your event now") → `/promoters/auth`: separate promoter login
  (email+password only — no Google parity with consumer auth).
- Every chat send first POSTs to the Supabase edge function `validate-conversation`
  (a hidden guardrail/logging dependency living in Supabase, outside this repo), then
  POSTs `/chat/stream` on the retriever.
- Retriever `/health` = **degraded**: `neo4j: error`, `openai: error`. Root `.env`
  still points at the **old Aura instance `5ce2d474`** (dead). The new instance is
  `2099d44c` (credentials file `Neo4j-2099d44c-Created-2026-08-13.txt` in the repo
  root, gitignored). The `openai` health check is a code bug (§4). Chat therefore shows
  the generic "An unexpected error occurred." bubble.
- Pusher `.venv` was corrupt (no python.exe); rebuilt with `uv sync`; `/health` ok.
- Live Aura `2099d44c` via MCP: completely empty — only the two default LOOKUP indexes,
  no constraints, no data. `db.index.vector.*` procedures available.

## 2. Git state — the tree does not match the repo

Substantial production code is **untracked**:

- `services/pusher/agent/{__init__,conversation,converters,neo4j_writer}.py` — the
  pusher's core. **A `docker build` of the pusher today produces an image that crashes
  at import** (api.py imports all three at module level).
- `services/pusher/tests/` (conftest + 2 suites).
- `services/retriever/agent/scripts/` — `setup_schema.py`, `seed.py`, `embeddings.py`:
  the *authoritative* schema DDL and the only code that writes `Venue.location`.
- `frontend/` — the entire app.
- `services/retriever/logs/requests.jsonl` — 85 lines of real user queries + generated
  Cypher. Untracked but **not gitignored** (`*.log` doesn't match `.jsonl`) — one
  `git add -A` away from being committed.
- `desktop.ini` (Windows junk, unignored).

Plus 10 modified-but-uncommitted tracked files.

## 3. Frontend (Lovable output) — reusable vs rewrite

Stack: Vite 5 + React 18 + TS 5.8 + Tailwind + shadcn/ui + react-router 6 +
@tanstack/react-query + supabase-js. Three lockfiles coexist (`bun.lock`, `bun.lockb`,
`package-lock.json`). No typecheck or test script; `vite build` never runs `tsc`;
eslint disables `no-unused-vars`. No env typing/validation, no `.env.example`.

**Worth porting into the new app** (genuinely custom, load-bearing):

| Asset | Path |
|---|---|
| Design tokens (the whole visual language, incl. `--pro-*` theme) | `frontend/src/index.css`, `tailwind.config.ts` |
| 4-language string table (en/es/it/ca) | `frontend/src/translations/index.ts` |
| SSE parser (rewrite target for typed events) | `frontend/src/utils/parseSSE.ts` |
| Voice recorder (MediaRecorder → base64 webm) | `frontend/src/utils/audioRecorder.ts` |
| Auth hook structure (Supabase session + role) | `frontend/src/hooks/useAuth.tsx` |
| Page flows as specs (not code): Chat, PromoterCreate, PromoterAuth, AccountSettings, EventConfirmationForm, entities/* | `frontend/src/pages`, `frontend/src/components` |
| Supabase migrations + generated types (9 tables, RLS) | `frontend/supabase/migrations/`, `src/integrations/supabase/types.ts` |

**Broken / dead / boilerplate** (do not inherit):

- **EventCard never renders in production**: `parseEventContent()` expects
  `**Artist**\nTagline\nVenue | Time | Price` but the retriever emits
  `### 1. {tagline}\n**Source:** …` (`formatters.format_events_as_markdown`). The
  parser never matches; users see raw `###` markdown. There is **no maps button and no
  "read more" button anywhere** — both are requirements.
- Auth gate and 5-query/week limit in `Chat.tsx:130-153` are **commented out**
  ("TODO: re-enable for production"). Anonymous users get unlimited queries.
- `Chat.tsx` contains an entire unreachable "promoter mode" (state + theme swap +
  `promoter-create` edge-function call): `handleModeChange` is never invoked. It
  duplicates `PromoterCreate.tsx` against a *different backend*.
- `PromoterCreate` checks for a Supabase access token, then calls the pusher **without
  any Authorization header** — the token check is theatre; the pusher has no auth.
- `handleFileUpload`'s `finally` runs before `FileReader.onload` — spinner clears
  early, errors uncatchable.
- No `AbortController` wiring — streams can't be cancelled; setState-after-unmount.
- ~1,900 lines of dead Deno edge functions (`chat`, `extract-event-*`, `validate-event`)
  superseded by the FastAPI pusher; still deployed with `verify_jwt = false` (all 9
  functions) while holding service-role logic.
- Orphans: `Landing.tsx` (unrouted), `<QueryCounter/>` (never rendered),
  `PrintableFlyer` (routed, unlinked, calls third-party `api.qrserver.com`),
  37 of 58 shadcn components unused, two toast systems both mounted, duplicated
  types/constants (`EventDetails`, `EntityType`, `industryRoles`, `typeConfig`,
  `retrieverClient` ≡ `pusherClient`), 12 of 16 exports in `types/api.ts` unused,
  `types/api.ts::EventResult` doesn't match what the backend actually returns.

## 4. Retriever — what exists

Live path: `agent/api.py` → `Orchestrator.run_react()` (`agent/orchestrator.py`, 667
lines). Text-parsed ReAct (`Thought:` / `Action:` / `Action Input:` / `Final Answer:`),
max 5 loops, tools `search_events` (parallel KG + Brave internet search) and
`search_nearby` (progressive radius 5→30 km over `point.distance`). NL→Cypher in
`agent/tools/query_builder.py` (gpt-4o, temp 0, **no parameterization** — literals
inline, guarded by a regex read-only validator). Fake streaming: answer computed
synchronously, re-tokenized, emitted word-by-word as OpenAI-shaped SSE frames.

Findings:

- **A second, complete, dead architecture** coexists in orchestrator.py: the pre-ReAct
  intent router (`decide_action`/`execute_query`/`generate_response` + 4 prompts),
  reachable only from the broken evals. `test_orchestrator_unit.py` (501 lines) tests
  almost exclusively this dead path; `run_react` and `_parallel_search` have **zero
  tests**.
- **Input safety is a silent no-op**: `llm_utils.get_openai_client()` ignores its
  `api_key` argument, so the LlamaGuard call sends the OpenAI key to OpenRouter → 401 →
  `validate_input_safety` catches everything and returns "safe". Fails open.
- No composer, no sub-query router: synthesis happens inside the ReAct loop; the
  markdown event list is bolted on afterwards in api.py, so prose and cards can
  disagree.
- `/chat` ignores location entirely; `/chat/stream` accepts `language` and never uses
  it; `needs_more_info` heuristic matches English phrases only.
- SSE metadata frame always emits `"request_id": "None"` (positional-arg skip,
  api.py:235); `search_nearby` never populates `cypher`; `/health`'s OpenAI check calls
  the bare module with no key (always errors → 503); `location.py:97` unbound-variable
  edge case; `Action Input:` parsing is single-line (silent truncation).
- The nearby-search Cypher never filters `start_at` — returns past events.
- `evals/` does not import (`from agent.prompts import QUERY_BUILDER_PROMPTS…` — a
  versioned-registry API that no longer exists) → all 8 `make eval-*` targets and 5
  eval guides are dead. Makefile also references deleted `tests/test_pipeline_metrics.py`
  and `agent.utils.metrics` (`test-metrics`, `test-integration`, `test-all`,
  `dashboard`).
- 2 stale tests error (patch a deleted symbol; assert removed prompt text);
  `test_safety_unit.py` tests a local *copy* of the validator, not the shipped code;
  `test_api_endpoints.py` patches Neo4j after the import-time call already happened.
- CORS `allow_origins=["*"]` with credentials.

## 5. Pusher — what exists

Flow: one-shot extraction (`converters.extract_fields_from_text`); if the 5 required
fields (artist, date_time, venue, city, price) land → emit form immediately; else
conversational collection (1–2 fields per turn). Form handshake = sentinel string
`__EVENT_EXTRACTED__{json}__EVENT_EXTRACTED__` **inside the SSE content stream**;
frontend regexes it out. Approval → `POST /validate-event` → `neo4j_writer.write_event`
(parameterized Cypher: MERGE City/Venue/Artist by name, CREATE Event, inline
text-embedding-3-small embeddings).

Findings:

- **A second approval path writes without review**: the legacy `/chat` endpoint pushes
  to Neo4j when the user types "yes"/"ok"/"si"/"ja" — or when the LLM merely echoes
  `**CONFIRMED**` (prompt-injectable).
- `CREATE` (not MERGE) on Event + fresh uuid per call → resubmits create duplicates.
- **Never writes `venue.location`** → every pro-submitted event is invisible to
  `search_nearby` (which requires `v.location IS NOT NULL`). Only `seed.py` sets it.
- `_parse_date_to_iso` falls back to `datetime.now()` on unparseable dates — a bad date
  becomes "right now" silently.
- Sessions: process-local dict, no TTL/eviction; session id =
  `uuid5(DNS, first_100_chars_of_first_message)` → identical openings from different
  users share collected fields.
- Multimodal: Whisper voice ✓, gpt-4o vision images ✓ (two LLM calls per image), URL
  extraction fetches raw HTML (8 000 chars incl. markup, SSRF-shaped, no allow-list),
  `document_to_text` is unreachable and its non-text branch sends raw PDF bytes as an
  image (would 4xx). **No batch support** (a requirement).
- No auth on any endpoint; only `/chat` rate-limited; `user_id` accepted and ignored;
  response key naming inconsistent (`eventData` vs `eventDetails`); SSE helpers
  copy-pasted from the retriever.
- `pyproject.toml` has **no pytest dependency** — `uv run pytest` doesn't resolve.
- `conftest.py` autouse-patches module-level singletons (`converters._client`,
  `conversation._client`, `neo4j_writer._openai`); any new module with its own client
  must be added or tests hit the real API.

## 6. Embeddings — written, never read

Four inconsistent implementations (writer inline; retriever script keyed on `ra_id`;
`pusher/agent/embedings.py` [sic] and `pusher/embedings_migration.py` keyed on a
nonexistent `id` property — both dead, the migration would burn full OpenAI spend and
write zero rows). **No vector index exists or is created anywhere; no query ever reads
an embedding.** The retriever even strips `embedding` from the schema it shows the LLM.
All embedding writes today are pure cost. Model everywhere: `text-embedding-3-small`
(1536-d, implicit).

## 7. Secrets

- **Real leak in git history**: `laiive_v1/.env` blob with a live-format
  `OPENAI_API_KEY=sk-…` (commits `e5b4841`, `d009d39`; also `laiive_prototipe1.0/.env`),
  reachable on both remotes. **Decision: rotate OpenAI + Aura + Langfuse keys; no
  history rewrite** (repo stays private).
- Working tree: Aura password in plaintext `Neo4j-2099d44c-Created-2026-08-13.txt`
  (gitignored via `Neo4j-*` but on disk in the repo root); root `.env` (gitignored)
  holds all live keys **and still points at the dead old instance**; `frontend/.env`
  holds only the Supabase anon key (public by design) but is protected *only* by the
  root `.gitignore` — `frontend/.gitignore` has no `.env` rule of its own.
- Env-name drift (silent, because `extra="ignore"`): `.env` has `CONVERSATION_MODEL` /
  `GUARDRAIL_MODEL` / `EMBEDDINGS_MODEL` / `ROUTER_MODEL`; code reads
  `CONVERSATIONAL_MODEL` / `SAFETY_MODEL` / `EMBEDDING_MODEL` / (nothing). Missing
  `BRAVE_SEARCH_API_KEY` silently disables internet search.
- No hardcoded keys in current code; edge functions read secrets via `Deno.env` ✓.

## 8. Tooling & repo hygiene

- **Linting has never run**: pre-commit ruff/ruff-format/mypy are scoped to
  `^(services/frontend|services/backend)/` — directories that don't exist. sqlfluff
  targets a nonexistent `migrations/`. detect-secrets has no baseline (and missed the
  historical leak). CI = pre-commit only; no tests, no builds.
- Ports defined three ways: Dockerfile/Makefile 8000/8001; compose-override +
  `frontend/.env` + config defaults 8002/8003. `make start-*` produces servers the
  frontend cannot reach. `make up-dev` starts containers that `sleep infinity`.
- `Makefile` does `include .env` → every target fails without `.env`. Broken targets:
  `test-metrics`, `test-integration`, `test-all`, `dashboard`, all 8 `eval-*`,
  `run-dev`/`deps` referenced by README but nonexistent.
- Dockerfiles run as root, no HEALTHCHECK. compose sets `NEO4J_USER` (wrong name,
  harmless only via env_file). Frontend absent from compose.
- LICENSE = truncated Apache-2.0 header; README links broken `LICENSES/` path.
  Project will be proprietary → replace (past Apache distributions stay licensed).
- `legacy/` (~40 files incl. old Postgres schema) fully tracked. `retriever/README.md`
  is 0 bytes; `pusher/README.md` describes components that don't exist;
  `FRONTEND_INTEGRATION.md` documents wrong relationship names (`AT_VENUE`,
  `PERFORMED_BY`), wrong key (`id`), wrong port — delete or rewrite.

## 9. Verdict summary

| Bucket | Contents |
|---|---|
| **Reusable as-is** | Graph read/write separation principle; pusher's parameterized write Cypher (fix identity); LocationTool patterns; conftest singleton-patching pattern; Supabase schema/migrations; design tokens; translations; evals *dataset* ideas |
| **Reusable as spec, rewrite the code** | Chat + PromoterCreate flows; ReAct orchestrator (→ router/composer split); SSE streaming (→ typed events); extraction prompts |
| **Dead — delete** | Router architecture + its 501-line test file; `evals/` (or repair its import layer); `embedings_migration.py`; `agent/embedings.py`; 5 Deno edge functions; `Landing.tsx`; promoter-mode branch in Chat; 37 shadcn components; broken Makefile targets; `FRONTEND_INTEGRATION.md` |
| **Broken — must fix before anything else** | Untracked core modules; safety no-op client bug; `.env` → old Aura; EventCard contract; pre-commit scoping |
