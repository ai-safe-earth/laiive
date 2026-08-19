# 04 — Phased refactor plan

All work on branch `refactor/foundation` (created from `connect-to-ui`), one PR-able
phase at a time. Phases 0–2 are sequential; 3–5 can interleave once 2's contracts are
frozen. Nothing writes to Aura without explicit approval (Phase 1 gate).

---

## Phase 0 — Hygiene & truth (no behavior change)

**Goal**: the repo matches reality; secrets are safe; tooling actually runs.

Work:
- Commit untracked production code: `services/pusher/agent/*`, `services/pusher/tests/`,
  `services/retriever/agent/scripts/`, `frontend/` (as-is snapshot before replacement).
- `.gitignore`: add `logs/`, `*.jsonl`, `desktop.ini`; move
  `services/retriever/logs/requests.jsonl` out of the tree (it's eval raw data).
- **User action**: rotate OpenAI key, Aura password, Langfuse keys (leaked key in
  history; decision = rotate only, no history rewrite). Move
  `Neo4j-2099d44c-Created-2026-08-13.txt` outside the repo.
- Root `.env`: point at Aura `2099d44c`; rename keys to match config
  (`CONVERSATIONAL_MODEL`, `SAFETY_MODEL`, `EMBEDDING_MODEL`; drop `ROUTER_MODEL`);
  regenerate `.example.env`; make both `config.py` fail loudly listing missing keys.
- Fix pre-commit: scope ruff/ruff-format/mypy to `^services/(retriever|pusher)/.*\.py$`;
  add a detect-secrets baseline; add commitizen config; fix the fallout the first real
  ruff run finds.
- Delete dead code: `pusher/embedings_migration.py`, `pusher/agent/embedings.py`, the
  router architecture in `orchestrator.py` (+ `test_orchestrator_unit.py`'s dead-path
  tests), `evals/` (quarantine the datasets, delete the broken runners), 11 broken
  Makefile targets, `FRONTEND_INTEGRATION.md`, frontend `bun.lockb`/`bun.lock` (npm is
  what runs here — decision item Q7 if bun is wanted back).
- Unify ports **8002/8003** in Dockerfile, Makefile, compose; remove `include .env`
  hard dependency from Makefile.
- LICENSE → proprietary "All rights reserved" notice; fix README license link; note
  past Apache-2.0 distributions remain licensed.
- Add pytest dependency group to pusher pyproject.

Risks: deleting the router breaks imports in remaining tests — run the full retriever
suite after each deletion. Committing `frontend/` snapshots ~1.9k lines of dead Deno
functions — acceptable, it documents the pre-refactor state.

Verify: `/verify-retriever` targets pass; `cd services/pusher && uv run pytest` passes;
`docker build` succeeds for both services; `pre-commit run --all-files` actually lints;
retriever `/health` shows `neo4j: ok` against 2099d44c.

---

## Phase 1 — Graph schema on the new Aura (GATED: ask before writing)

**Goal**: the ontology from `03-ontology.md` exists on `2099d44c`; dev data seeded.

Work: run the DDL (constraints, range/point/vector indexes) via `write-cypher` after
explicit user approval; rewrite `agent/scripts/setup_schema.py` to emit exactly that
DDL; adapt `seed.py` to the new model (uid, name_norm, venue_type, geocoded points,
datetime start_at, source='seed'); single shared embedding module.

Risks: `NODE KEY` constraint may be unsupported on the Aura tier — fallback in the doc.
Verify: `SHOW CONSTRAINTS` / `SHOW INDEXES` match 03; every example multi-hop query in
03 returns seeded rows; vector query returns neighbors.

---

## Phase 2 — Backend contracts + retriever/pusher redesign

**Goal**: typed SSE protocol; retriever = classifier→router→hybrid execution→composer;
pusher = one-clarification-round + form + batch; all §01 bugs fixed.

Work (files):
- New **`services/shared`** package (decided): typed SSE protocol (`message.delta`,
  `events.result`, `form.extracted`, `batch.progress`, `status`, `error`, `done`),
  `EventCard` shape, Neo4j writer, embedding text builders. Installed editable in
  retriever/pusher/search; TS mirror of the protocol for the frontend with a CI
  contract test.
- `services/retriever/agent/`: split `orchestrator.py` into `classifier.py` (query
  type + conversational moment + resolved constraint state), `router.py` (atomic
  sub-queries), `executor.py` (parameterized Cypher templates for the common shapes;
  LLM Cypher for the long tail; vector kNN; nearby), `composer.py` (always runs; tone
  prompt; language-aware; empty-result and ambiguous branches). Real streaming from the
  composer. Fix: safety client key bug, request_id frame, `/health` OpenAI check,
  nearby cypher reporting, `start_at >= datetime()` filter in nearby, single-line
  Action-Input parsing (moot after redesign).
- `services/pusher/agent/`: merge the duplicated extraction prompts/functions into
  `converters.py`; one-clarification-round rule in `conversation.py`; kill the
  "type yes"/`**CONFIRMED**` write path; `neo4j_writer.py` → MERGE-by-identity write
  with geocoding (provider per 05), `owner_id`, `source`, dedup probe; new
  `batch.py` (CSV/XLSX → drafts) + endpoints `/batch/parse`, `/batch/validate-event`;
  session TTL store; extend `tests/conftest.py` for any new module-level clients.
- Both `config.py`: aligned names, startup validation, shared embedding settings
  (`text-embedding-3-small`, 1536).

Risks: prompt regressions (classifier/composer) — build a small golden-set test
(`tests/test_composer_moments.py`) with recorded fixtures; LLM tests behind
`--timeout=120`. Scope creep — the frontend still speaks the old protocol until
Phase 4; keep a `/chat/stream` compatibility flag emitting the old frames until the new
frontend lands, then delete.

Verify: both suites green; live smoke against seeded Aura: first query / refinement /
new-topic / empty-result / ambiguous each produce correct `events.result` +
moment-appropriate prose; pusher single-event and 5-row CSV batch produce correct
frames and graph writes (checked via read-cypher).

---

## Phase 3 — Node gateway + auth + ownership

**Goal**: one public surface; JWT-verified, role-routed, rate-limited.

Work: new `services/gateway/` (Fastify + TypeScript): JWKS verification of Supabase
JWTs, role extraction, `/api/chat/*` → 8002, `/api/push/*` → 8003 (pro only),
`/api/admin/search/*` → 8004 (admin only), SSE pass-through (flush-friendly proxy),
rate limits (per-user + anonymous per-IP/device with login-upsell quota), CORS
allow-list, request-id injection, conversation logging (replaces
`validate-conversation` edge fn). Supabase: **fresh project** (decided) — new
migrations from scratch (profiles, user_roles incl. Google OAuth for pros,
promoter_profiles with managed/owned venue-artist-event data, `ownerships`
shared/transferable + RLS, quotas); the old project's migrations are reference only;
no edge functions in the new project. FastAPI services: remove CORS
`*`, trust only gateway-forwarded identity headers, bind internal.

Risks: SSE buffering through the proxy — test streaming end-to-end early;
`slowapi` remnants conflict — remove service-level limiter.
Verify: Playwright E2E: anonymous chat allowed with quota headers; unauthenticated
`/api/push/*` rejected 401; non-pro rejected 403; pro flow works; streams uninterrupted
through the gateway.

---

## Phase 4 — New frontend (fresh Vite + React app)

**Goal**: an owned frontend with the same visual language, correct contracts, and the
required UX (cards with "read more" + maps, batch progress, natural clarification).

Work: scaffold new app (Vite, React 18, TS strict + `tsc --noEmit` in CI, Tailwind,
shadcn — only components actually used, react-router, react-query, one toast system);
port `index.css` tokens, `translations/`, `audioRecorder`; new `api/` layer typed
against the protocol (SSE parser handling named events; AbortController wiring); pages:
Chat (cards from `events.result` — "read more" expander, map button expanding an
embedded Leaflet+OSM map in the card with a Google-Maps deep link,
verified/internet source badge), PusherChat (form from
`form.extracted`, missing-field highlights, batch mode with "event i of N"), Auth
(consumer + pro parity incl. Google), Account/entities (react-query). Env typed +
runtime-validated; `VITE_API_URL` → gateway. Auth gate + quota **enabled**. Replace
`frontend/` wholesale once at parity (old snapshot stays in git history).

Risks: visual regression — compare against the Playwright screenshots taken during
analysis (home/auth/promoters); scope — AccountSettings/PrintableFlyer can lag behind
the core chat flows.
Verify: Playwright walkthrough of every §5/§6 requirement in the task: natural
clarification (no form), refinement keeps state, empty-result moment, cards render
from structured data, maps link correct, batch counter advances, one-clarification
round in pro chat.

---

## Phase 5 — SEARCH service

**Goal**: admin-triggered internet event discovery with clean provenance.

Work: new `services/search/` (FastAPI, port 8004, internal): Brave search → fetch →
shared extraction → dedup (name_norm+date+venue, then vector similarity) → dry-run
report endpoint → approved batch write with `source: 'admin_search'`; CLI entry point;
reuse pusher's writer module (extracted into a small shared package or duplicated with
contract test — decision Q6).

Endpoints, all behind the gateway's existing admin route (flip `SEARCH_ENABLED=true`):
`POST /sweep` (dry-run, persists a report, writes nothing), `GET /reports/{id}`,
`POST /reports/{id}/approve` (batch write through the shared writer),
`POST /backfill` (missing embeddings / venue `location`, bounded and idempotent).
Reports persist in a Supabase `search_reports` table (service-role only, shaped like
`conversation_logs`) so they outlive a restart and the frontend can show them later.

**Scheduling (D17)** — `services/search/flows/`: `city_sweep.py` (one Prefect task per
city, so retries and history are per city; publishes a markdown artifact as the review
surface), `backfill.py`, and `auth.py` (Supabase password grant for the admin service
account → short-lived JWT per run; credentials in Prefect Secret blocks, never in the
repo). Schedules live on the Prefect deployment — weekly sweep, nightly backfill — so
cadence changes without a redeploy. Needs one Supabase admin service account
(`user_roles.role='admin'`, created via SQL with the service role); the existing
`custom_access_token_hook` stamps its JWT with no new machinery.

Risks: writes from a third service — same writer code path only, never bespoke Cypher.
A city sweep is a minutes-long HTTP call; the gateway sets `requestTimeout: 0` so
synchronous per-city calls are fine to start, and if one exceeds ~5 min, `/sweep` returns
`report_id` immediately and the flow polls `GET /reports/{id}` — no redesign needed.
Verify: dry-run on a known city produces a sane report with zero writes (node counts
before/after via `read-cypher`); approved 3-event batch lands tagged and deduped (re-run
produces 0 new nodes); retriever surfaces them labeled as internet/admin-sourced; one
manual run from Prefect Cloud proves the managed pool reaches the gateway and the admin
JWT verifies.

---

## Phase 6 — CI/CD + deploy + foundation observability

**Goal**: every merge is tested; the stack deploys reproducibly; day-one signals exist.

Work: GitHub Actions matrix — ruff+mypy+pytest per Python service, tsc+eslint+build for
gateway/frontend, docker build all images; compose file that runs the full stack
(gateway + 3 services) with healthchecks, non-root images; deploy per 05 decisions
(services on Railway/Fly, SPA on **Cloudflare Pages** per D18, Aura + Supabase managed);
Prefect deployments applied from CI so schedules are versioned with the code; structured
JSON logs with request-ids end-to-end; keep Langfuse tracing on all LLM calls; persist
eval-ready request/response records (the `requests.jsonl` idea, done properly:
gateway-side, PII-lean, rotated).

Verify: CI green on the PR; fresh-clone `make up` boots the whole stack; a request-id
from the browser is traceable through gateway → service → Langfuse.
