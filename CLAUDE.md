# CLAUDE.md

Instructions for this repo. State of play + machine-specific gotchas: root `handoff.md`
(read it first — this file is the stable rules, that one is the moving picture).

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
  `cd services/<svc>`, then `uv run …`. All services load the single **root `.env`** via
  `SettingsConfigDict(env_file="../../.env")` — resolved against CWD, so launching from the
  repo root silently loses all settings. Missing keys fail loudly. Template: `.example.env`.
- `uv run uvicorn …` fails on this machine ("Failed to canonicalize script path") — use
  `uv sync` then `uv run --no-sync python -m uvicorn …`, or the `make start-*` targets.
- Frontend uses **npm** (bun is NOT installed): `cd frontend && npm install && npm run dev`.
  Port 8080 is taken by EnterpriseDB on this machine — run Vite on 8081 via
  `npx vite --port 8081 --strictPort` (`npm run dev -- --port` loses the flag in PowerShell).
- Ports: gateway **8000** (the only published surface), retriever **8002**, pusher **8003**,
  search **8004**. The frontend talks to the gateway only (`VITE_API_URL`).

## Architecture

- **Gateway** (`services/gateway`, Fastify + TS) fronts everything: Supabase JWT auth (role in
  the `user_role` claim), rate limits, `/api/chat/*`→retriever, `/api/push/*`→pusher (pro+),
  `/api/admin/search/*`→search (admin). It injects verified `X-User-Id`/`X-User-Role` and
  `X-Internal-Key`; the Python services verify the key (`laiive_shared/internal_auth.py`) —
  direct curls to 8002–8004 get 403 when `INTERNAL_API_KEY` is set. Gateway health is
  `/healthz`; Python services use `/livez` + `/readyz` (probes) and `/health` (deep, humans only).
- **`services/shared`** is the contract: `laiive-shared` package (editable in every service) with
  the typed SSE protocol + TS mirror `services/shared/ts/protocol.ts` (drift-guarded by
  `test_ts_contract.py` — never redeclare protocol types in the frontend), and
  **`neo4j_writer.py`, the only graph write path** (MERGE by identity, dedup → 409).
- **Retriever** reads the graph. Per turn: `classifier.py` → `router.py` → `executor.py` →
  `composer.py`, tied by `pipeline.py` (built lazily — importing `agent.api` needs no Neo4j).
  `/chat/stream` streams real tokens as named-event SSE. Anything yielding SSE frames must not
  `async def` around blocking work (sync generator, or `asyncio.to_thread`) — fake-streaming
  has regressed twice.
- **Pusher** writes via `/validate-event` → shared writer. Chat is stateless (client-carried
  history); multi-event listings enter the "walk" (one event per turn, cursor echoed by the
  client). No batch mode — a spreadsheet is a longer conversation.
- **Search** (`services/search`) sweeps the web (Tavily) into dry-run reports; a human approve
  writes them (`source='admin_search'`). Scheduling: `services/search/flows/serve.py` (Prefect
  Cloud schedules, flows execute locally against the gateway). Root `prefect.yaml` is dormant
  until a public gateway exists.
- Relationship names: trust `services/shared/laiive_shared/neo4j_writer.py`.

## Testing

- Per service: `cd services/<svc> && uv run pytest -q` (retriever adds `-m "not integration"`;
  integration tests need live Aura + real keys). Single test:
  `uv run pytest -v tests/test_x.py::test_name`, `--timeout=120` for anything touching an LLM.
  Or `/verify-retriever` after retriever changes; `make test-all` mirrors CI.
- Gateway: `cd services/gateway && npm test` (vitest, fakes Supabase locally). Frontend:
  `npm run typecheck` (runs both tsconfig projects — bare `tsc --noEmit` is a silent no-op).
- Pusher `tests/conftest.py` autouse-patches module-level clients (`agent.converters._client`,
  `agent.conversation._client`, `agent.graph._openai/_driver/_geocoder`). A new module with its
  own module-level client must be added there or tests hit the real API.
- The ruff `--fix` pre-commit hook deletes an import the moment it is momentarily unused —
  add the import and its first use in the same edit. A failed commit usually just needs
  re-`git add` + retry.

## Repo etiquette

- Conventional Commits, lowercase subject, enforced by a commitizen `commit-msg` hook.
  `CONTRIBUTING.md` wants a body explaining *why* plus a `Refs: #123` trailer.
- Branches: `<type>/<kebab-desc>` (`feature/…`, `fix/…`).
- Two GitHub remotes — `origin` → `ai-safe-earth/laiive` (canonical, PRs here), `laiive` →
  `OscarArroyoVega/laiive` (personal fork — don't push there).
- Never read or edit anything under `.history/` — VSCode local-history junk holding stale copies
  of deleted modules.
- Writes to Supabase (`db push`, MCP DDL) are refused by the permission classifier — hand me
  the command to run. Writes to Aura need my approval.

## Handoff file (read by the project tracker)

One handoff per repository: `handoff.md` at the root. Never start a second one. When work happens
inside a plan folder (`docs/refactor/`), keep writing to the root handoff and list the folder under
"plans" so the paths stay findable. Non-code progress (branding, strategy) goes to
`product-status.md`, not the handoff.

Update it at the end of every working session — invoke the `handoff` skill
(`.claude/skills/handoff/SKILL.md`) for the machine block the tracker parses and its rules.
