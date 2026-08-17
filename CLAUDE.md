# CLAUDE.md

Instructions for this repo.

## Working with me

Solo builder/founder; I wrote most of this code. Skip orientation and background explanation.

- Be terse. No end-of-turn summaries.
- Propose a plan before implementing.
- Explain tradeoffs when there's a real design choice.
- When a task ends and the next steps don't need the conversation's prior context: update the
  root `handoff.md` first (see *Handoff file* below), then ask me to `/clear` (Claude can't clear
  its own context), and continue fresh from the handoff.

## Environment

- No root `pyproject.toml` / `uv.lock`. Every Python command runs from inside a service dir:
  `cd services/retriever` or `cd services/pusher`, then `uv run …`.
- Both services load a single **root `.env`** via `SettingsConfigDict(env_file="../../.env")` —
  resolved against CWD. Launching a service from the repo root silently loses all settings.
  Template: `.example.env`.
- Frontend uses **bun**: `cd frontend && bun install && bun run dev` (Vite on :8080).
  `package-lock.json` also exists but bun is the live one.

## Ports — three inconsistent definitions

| Source | retriever | pusher |
|---|---|---|
| Dockerfile / `make start-*` | 8000 | 8001 |
| `docker-compose.override.yml`, `frontend/.env` | **8002** | **8003** |
| `config.py` defaults (unused by the uvicorn CLI) | 8002 | 8003 |

To drive the real frontend, start services on **8002/8003** — not via `make start-*`.

## Architecture

- **retriever and pusher never call each other.** They share only the Neo4j graph: pusher writes
  (`services/pusher/agent/neo4j_writer.py`), retriever reads with `READ_ACCESS`.
- `services/retriever/agent/orchestrator.py` is the whole brain. Tools are plain classes, *not*
  OpenAI function-calling. The ReAct loop parses raw `Thought:` / `Action:` / `Action Input:` /
  `Final Answer:` text — **rewording the prompt constants silently breaks parsing.** Only
  `search_events` and `search_nearby` are valid action names.
- `agent/api.py` calls `neo4j_client.get_schema()` and builds the `Orchestrator` **at import time**.
  No Neo4j or bad creds ⇒ import error ⇒ uvicorn and pytest collection both die.
- `/chat/stream` is **fake streaming**: the answer is computed synchronously, then re-tokenized and
  emitted word-by-word as OpenAI-shaped SSE frames (`agent/utils/formatters.py`).
- `frontend/src/types/api.ts` mirrors the backend response models — update both together.
- Relationship names: trust `services/pusher/agent/neo4j_writer.py` (`PERFORMS_AT`, `HOSTED_AT`,
  `LOCATED_IN`, `HAS_GENRE`). `services/retriever/FRONTEND_INTEGRATION.md` says otherwise and is stale.

## Testing

- Single test: `cd services/retriever && uv run pytest -v tests/test_query_builder.py::test_name`.
  Use `--timeout=120` for anything touching an LLM.
- `services/pusher` has **no pytest dependency** in its lock — `uv run pytest` there won't resolve it.
- `services/pusher/tests/conftest.py` autouse-patches module-level singletons
  (`agent.converters._client`, `agent.conversation._client`, `agent.neo4j_writer._openai`). A new
  module with its own module-level client must be added there or tests hit the real API.
- **Broken Makefile targets — don't use:** `make test-integration` / `test-all` (reference the
  missing `tests/test_pipeline_metrics.py`) and `make dashboard` (references the missing
  `agent.utils.metrics`). Use `/verify-retriever` instead.

## Repo etiquette

- Conventional Commits, lowercase subject, enforced by a commitizen `commit-msg` hook.
  `CONTRIBUTING.md` wants a body explaining *why* plus a `Refs: #123` trailer.
- Branches: `<type>/<kebab-desc>` (`feature/…`, `fix/…`).
- Two GitHub remotes — `origin` → `ai-safe-earth/laiive`, `laiive` → `OscarArroyoVega/laiive`.
  Confirm which one before pushing.
- Never read or edit anything under `.history/` — VSCode local-history junk holding stale copies
  of deleted modules.

## Handoff file (read by the project tracker)

One handoff per repository: `handoff.md` at the root. Never start a second one. When work happens inside a plan folder (`docs/refactor/`), keep writing to the root handoff and list the folder under "plans" so the paths stay findable.

Update it at the end of every working session: write it however you like for humans, then append this machine block as the last thing in the file, replacing the previous one.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "Solar Forge",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-08-15",
  "deadline": "2026-09-30",
  "people": ["ana", "dro"],
  "plans": [
    { "name": "refactor", "path": "docs/refactor/", "status": "active" },
    { "name": "billing", "path": "docs/billing/", "status": "done" }
  ],
  "phases": [
    { "name": "Build", "status": "active", "start": "2026-06-11", "end": null, "plan": "refactor",
      "decisions": [{ "date": "2026-07-02", "text": "Postgres over Mongo, reporting needs joins" }] }
  ],
  "blockers": [{ "text": "Waiting on the provider API key", "severity": "high", "owner": "dro", "since": "2026-08-01" }],
  "nextSteps": [{ "title": "Wire auth to the new schema", "est": 3, "owner": "ana", "phase": "Build", "plan": "refactor" }],
  "sessions": [{ "date": "2026-08-12", "model": "opus-5", "credits": 40, "person": "dro", "hours": 2.5 }]
}
```

Rules: "plans" only points at folders; the work itself stays in phases, blockers, nextSteps and sessions, each tagged with "plan" when it belongs to one. ISO dates, null when unknown. status green|amber|red. phase status done|active|planned. severity critical|high|medium|low. est in working days. One sessions entry per working session. Append decisions and sessions, never rewrite past ones. Commit the handoff on whatever branch you are working in. No emoji.
