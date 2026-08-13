# HANDOFF — refactor status (updated 2026-08-13)

Continuation point for the laiive refactor. Read this first, then
`04-plan.md` (phases) and `05-decisions.md` (all decisions, D1–D16 + budget).
Branch: **`refactor/foundation`** (from `connect-to-ui`). Nothing pushed yet;
canonical remote for future PRs = `origin` (ai-safe-earth/laiive) — the remote
*named* `laiive` is the personal fork, do not push there.

## Done

### Phase 0 — hygiene ✅ (commits `dbff176`…`235ff87`)
- All previously-untracked production code committed (pusher agent modules,
  pusher tests, retriever scripts, full frontend snapshot). Both docker images
  build (`docker build services/pusher` was crashing before).
- Pre-commit fixed and fully green: ruff/ruff-format/mypy scoped to
  `services/(retriever|pusher)`, evals excluded from mypy, detect-secrets
  baseline, `.cz.toml`, JSONC tsconfigs excluded from strict JSON check.
- Dead code removed: pre-ReAct router (orchestrator 667→407 lines), broken
  eval runners/config (datasets+guides kept in `evals/`), 501-line dead-path
  test file, stale tests patching deleted symbols, `embedings_migration.py`,
  `agent/embedings.py`, `FRONTEND_INTEGRATION.md`, bun lockfiles (npm only).
- Ports unified **8002 retriever / 8003 pusher** everywhere (Dockerfile CMD,
  compose base+override, Makefile). Makefile broken targets removed,
  `-include .env` now optional, `test-pusher` target added.
- Root `.env` aligned with config names (CONVERSATIONAL_MODEL, SAFETY_MODEL,
  EMBEDDINGS_MODEL, LANGFUSE_HOST; ROUTER_MODEL dropped;
  ENABLE_INTERNET_SEARCH=false until a Brave key exists). `.example.env`
  regenerated. LICENSE → proprietary; README link fixed.
- `requests.jsonl` (raw user queries) moved out of the tree to
  `../laiive-data/`. `.gitignore`: logs/, *.jsonl, desktop.ini.
- Keys rotated by owner (OpenAI, Aura, Langfuse). Old leaked key treated as
  dead; no history rewrite (D4).
- Pusher tests: **47 passed** (pythonpath fix in pyproject). Retriever:
  **72 passed, 4 failed — pre-existing**, all from the `/health` bare-openai
  bug (Phase 2 fix; verified identical on pre-refactor code).

### Phase 1 — graph schema + seed ✅ (commit `bb677c3`)
- Aura `2099d44c` (the only instance; old `5ce2d474` confirmed deleted) now
  has the full 03-ontology DDL, verified via SHOW CONSTRAINTS/INDEXES:
  uid uniqueness on Event/Artist/Venue, genre_slug, name NOT NULLs,
  **City NODE KEY (works on Aura Free — it runs Enterprise)**, range indexes
  (start_at, status, source, name_norms, venue_type, country_code), POINT
  indexes (venue/city location), **vector indexes** event/artist/venue
  `.embedding`, 1536-d cosine — all ONLINE.
- `agent/scripts/setup_schema.py` = the DDL source of truth (idempotent).
  `agent/scripts/seed.py` = new-model dev dataset: 3 cities / 5 genres /
  6 geocoded venues / 8 artists / 12 future-dated events (relative dates,
  never stale), embeddings backfilled (text-embedding-3-small).
- Verified live: similar-artists-by-genre multi-hop, radius+venue_type geo
  query (Sala El Sol 365 m from Madrid center), genre+country query, and
  vector kNN (Klangfeld → DJ Petra .749 / Laia Ferrer .745, jazz ranked
  below). Run commands:
  `cd services/retriever && uv run python -m agent.scripts.setup_schema` / `-m agent.scripts.seed`.

## Next: Phase 2 — backend contracts + redesign (see 04-plan.md for full spec)

1. **`services/shared` package** (D10): typed SSE protocol (`message.delta`,
   `events.result`, `form.extracted`, `batch.progress`, `status`, `error`,
   `done`) + `EventCard` shape (02-architecture.md §2) + Neo4j writer +
   embedding text builders. TS mirror + CI contract test.
2. Retriever: split orchestrator into classifier (query type + conversational
   moment + resolved constraint state) → router (atomic sub-queries) →
   executor (parameterized Cypher templates + vector kNN + geo) → **composer
   that always runs** (jazzy-warm tone prompt, answers in the conversation's
   language). Real streaming.
3. Pusher: one-clarification-round rule; kill the "type yes"/**CONFIRMED**
   direct-write path; MERGE-by-identity writes with Nominatim geocoding (D12,
   cache + 1 req/s); `owner_id`/`source`; batch endpoints (CSV/XLSX → drafts,
   "event i of N"); session TTL store.
4. Bug fixes rolled in: `get_openai_client` ignores api_key (OpenAI key sent
   to OpenRouter → LlamaGuard silently no-ops; likely replace with OpenAI
   moderation per 05/R3), `/health` bare-openai check (the 4 failing tests),
   SSE `request_id: "None"`, nearby search missing cypher + no start_at
   filter, English-only needs_more_info.

Then Phase 3 gateway (+fresh Supabase project, D15), Phase 4 new frontend
(Vite+React, Leaflet embedded maps D9), Phase 5 SEARCH service (CLI + admin
endpoint, Brave), Phase 6 CI/CD + deploy ($30–50/mo budget).

## Environment gotchas (this machine)

- Windows; `bun` NOT installed — use npm/node. Port 8080 taken by
  EnterpriseDB → run Vite with `--port 8081`.
- Always `cd services/<svc>` before `uv run …` (config loads `../../.env`
  relative to CWD).
- Retriever `/health` shows `openai: error` even with a valid key — known
  bug, not an env problem. `neo4j: ok` is the signal that matters.
- Pre-commit runs on commit and modifies files (ruff format) — a failed
  commit usually just needs re-`git add` + retry.
- The pusher tests' `conftest.py` autuse-patches module-level OpenAI clients;
  any new module with its own client must be added there.
- MCP `aura-neo4j` points at `2099d44c` (write access; ask owner before
  writing data). Playwright + claude-in-chrome MCPs available.

## Standing rules from the owner

- Terse replies, no end-of-turn summaries. Propose a plan before
  implementing; explain real trade-offs. Every decision needs owner approval.
- Conventional Commits (commit-msg hook enforces), lowercase subject.
- Never read `.history/` or `legacy/`.
