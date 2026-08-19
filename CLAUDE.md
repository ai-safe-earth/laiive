# CLAUDE.md

Instructions for this repo, plus the machine gotchas that cost real time here. State of play:
root `handoff.md` (read it first — this file is the stable rules, that one is the moving picture).

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
- Deploy targets: services on **Fly.io** (`deploy/fly/*.toml`, `make fly-deploy-*`), SPA on
  **Cloudflare Pages**, Aura + Supabase managed. Runbook: root `DEPLOY.md`. Anything needing
  `flyctl auth`, Cloudflare or Supabase credentials is yours to run — I prepare and verify.

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
- **`main` is production, `develop` is the trunk** — full model in `CONTRIBUTING.md`. Cut
  `<type>/<kebab-desc>` branches from `develop` and PR into `develop`; `main` only ever receives
  a release PR from `develop`, and is protected (PR required, every check green, no force-push).
  Merge commits, never squash — the commit bodies are the reasoning.
  Shipping: release PR → `make release` (`cz bump` tags and writes `CHANGELOG.md`) → deploy →
  merge `main` back into `develop` so the tag is not stranded.
  Two branches are archives, never build on them: `legacy/pre-refactor` (the pre-refactor tree,
  also tag `pre-refactor-main`) and `experiment/k3s` (the withdrawn D19 detour).
- Two GitHub remotes — `origin` → `ai-safe-earth/laiive` (canonical, PRs here), `laiive` →
  `OscarArroyoVega/laiive` (personal fork — don't push there).
- Never read or edit anything under `.history/` — VSCode local-history junk holding stale copies
  of deleted modules.
- Writes to Supabase (`db push`, MCP DDL) are refused by the permission classifier — hand me
  the command to run. Writes to Aura need my approval.

## Machine gotchas (this box)

Windows. `bun` is NOT installed — npm/node. Port 8080 is EnterpriseDB's.

**Running things**

- `uv run uvicorn …` and `uv run pytest` both fail here with "Failed to canonicalize script
  path". Use `uv sync` then `uv run --no-sync python -m uvicorn …` / `python -m pytest -q`.
  The `make start-*` targets still carry the broken form.
- `npm run dev -- --port 8081` silently loses the flag in PowerShell (Vite starts on 5173 and
  treats `8081` as a directory). Use `npx vite --port 8081 --strictPort`.
- `PYTHONPATH=.` is needed for ad-hoc `uv run python` scripts in the services (`agent` is not
  an installed package). Piping their output through `grep` trips Windows binary detection on
  accented text — redirect to a file and `grep -a` it.
- Prefix Prefect (and any rich-using) commands with `PYTHONIOENCODING=utf-8`: `rich`'s cp1252
  console writer raises `UnicodeEncodeError` *after* the command has already succeeded.
- `cd` in one Bash call does not persist reliably — use absolute paths.
- Docker Desktop's loopback: `127.0.0.1:<published>` sometimes refuses while `localhost` works.

**Ports and stale processes**

- Dev servers from an earlier session go stale and cost real time — one retriever reported
  `openai: error` on `/health` while the key worked fine via curl, and a Vite from a previous
  session served the *deleted* app on :8081. Before debugging anything you did not start:
  `Get-NetTCPConnection -LocalPort 8000,8002,8003,8004,8081 -State Listen | %{ Get-Process -Id $_.OwningProcess | select Id,ProcessName,StartTime }`
- Background dev servers survive their launcher; kill by PID.
- Other projects squat these ports (an `A02_VaiVia` uvicorn on :8000, a
  `laiive-global-workspace` container on :8002/:8003). Everything is env-overridable, so shift
  rather than kill: `GATEWAY_PORT`, `RETRIEVER_URL`, `PUSHER_URL`, `CORS_ALLOW_ORIGINS`, and
  inline `VITE_API_URL` for Vite (inline `VITE_*` beats `.env` files).

**Commits**

- The ruff `--fix` pre-commit hook **deletes an import the moment it is momentarily unused**.
  It has bitten six times. Write the import and its first use in the same edit.
- `ruff-format` rewrites staged files and aborts the commit; re-`git add` and commit again.
- `cz bump` without `--yes` dies under Git Bash with `NoConsoleScreenBufferError` —
  prompt_toolkit wants a real Windows console. The `make release` target passes it.

**Network and data**

- **DNS here flaps.** `getaddrinfo` failed intermittently for the Aura host, `docs.claude.com`
  and `operations.osmfoundation.org` in one session while a tight probe loop resolved 10/10. It
  killed three `run_backfill` runs at driver construction. Pre-warm with
  `socket.gethostbyname` and retry in process — the sweep is idempotent by uid.
- The **Aura free instance auto-pauses**. Paused, its DNS record disappears; resuming, reads
  route to a follower while writes fail with "No write service currently available".
- MCP `aura-neo4j` points at `2099d44c`. Its host `2099d44c.mcp-instances.neo4j.io` stopped
  resolving once while the database itself was fine on `2099d44c.databases.neo4j.io`; if the
  MCP is down, query through the service instead.
- Re-checking one venue after a geocoder fix: the repair sweep only selects venues that are
  unstamped, non-`venue`, or checked over 7 days ago — exactly not the one a fix would correct.
  `cd services/search && uv run --no-sync python scripts/recheck_venue.py "<venue>"` clears the
  stamp and re-runs it (an Aura write).
- Maintenance scripts open a **read-only** session unless `--write` is passed.

**Tooling limits**

- `winget` is not on PATH and the classifier blocks downloading an `.exe`, so `cloudflared`
  cannot be installed from here. Tag deletion and force-push are refused too — hand me those.
- Browser automation: `computer`'s `type` action does not reach this app's inputs — use
  `form_input` with a ref from `read_page`, and click by `ref` rather than coordinates.

## Handoff file (read by the project tracker)

Read `handoff.md` once, at the start of a session, before the first plan or code change. Do not
re-read it later in the same session — the conversation is the fresher source. Re-read only after
a `/clear`, a `/compact`, or if I say the repo moved outside this session. If it conflicts with
the repo, trust the repo and say so.

Keep it to state, 40 lines maximum, no narrative and no history — git log keeps that. Non-code
progress (branding, strategy, artwork) goes to `product-status.md` instead.
