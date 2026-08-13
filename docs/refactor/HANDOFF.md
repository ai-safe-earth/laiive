# HANDOFF — refactor status (updated 2026-08-13, evening)

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

## Next: Phase 3 — Node gateway + auth + ownership (04-plan.md)

New `services/gateway/` (Fastify + TS): Supabase JWT via JWKS, roles
user/pro/admin, `/api/chat/*`→8002, `/api/push/*`→8003 (pro),
`/api/admin/search/*`→8004 (admin), SSE pass-through, rate limits (incl.
anonymous per-IP quota, D7), CORS allow-list, request-id injection,
conversation logging. **Fresh Supabase project** (D15) with new migrations
(profiles, user_roles, promoter_profiles, ownerships + RLS, quotas).
Then FastAPI services: remove CORS `*`, trust gateway headers, bind internal.
Owner action needed: create the Supabase project (keys → root `.env`).

Then Phase 4 frontend (Vite+React, v2 protocol, Leaflet cards D9 — after it
lands, delete the legacy SSE frames + sentinel + `cards_to_markdown`),
Phase 5 SEARCH service, Phase 6 CI/CD + deploy ($30–50/mo budget).

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
- MCP `aura-neo4j` points at `2099d44c` (write access; ask owner before
  writing data). Playwright + claude-in-chrome MCPs available.

## Standing rules from the owner

- Terse replies, no end-of-turn summaries. Propose a plan before
  implementing; explain real trade-offs. Every decision needs owner approval.
- Conventional Commits (commit-msg hook enforces), lowercase subject.
- Never read `.history/` or `legacy/`.
