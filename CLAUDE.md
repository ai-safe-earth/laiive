# CLAUDE.md

## Project
- What it is: laiive, a chat that answers "what can I do tonight?" for live music, over a Neo4j graph.
- Stack: Python services (FastAPI, uv), Fastify + TS gateway, Vite + React SPA, Neo4j Aura, Supabase, Redis. Fly.io + Cloudflare Pages.
- Main folders:
  - `services/gateway` (port 8000, the only public surface: Supabase JWT auth, rate limits, injects `X-User-Id`/`X-User-Role`/`X-Internal-Key`).
  - `services/retriever` (8002, reads the graph: classifier -> router -> executor -> composer, tied by `pipeline.py`).
  - `services/pusher` (8003, writes events via `/validate-event`). `services/search` (8004, Tavily sweeps into dry-run reports).
  - `services/shared`: the contract. SSE protocol + TS mirror `ts/protocol.ts` (never redeclare in the frontend) and `neo4j_writer.py`, the only graph write path.
- Root `.env` only, loaded as `../../.env`, so run Python from inside `services/<svc>`. Deploy runbook: `DEPLOY.md`.

## Commands
- Install: `cd services/<svc> && uv sync` / `cd frontend && npm install`
- Run: `uv run --no-sync python -m uvicorn ...` (bare `uv run uvicorn` fails here). Vite: `npx vite --port 8081 --strictPort`.
- Test: `uv run --no-sync python -m pytest -q` (retriever adds `-m "not integration"`; `--timeout=120` near an LLM). Gateway and frontend: `npm test`. `make test-all` mirrors CI.
- Lint/format: pre-commit (ruff, ruff-format, commitizen). Frontend: `npm run typecheck`.
- Machine gotchas (ports, uv, DNS, commits): `docs/dev-box.md`. Read it when a command fails strangely.

## Rules
- Run tests before saying a task is done.
- Keep changes small and focused on the current plan step.
- Ask before deleting files, adding dependencies, or changing the roadmap order.
- Propose a plan before implementing. Explain tradeoffs when there is a real design choice.
  Micro changes skip this (see "Micro changes").
- Never `async def` around blocking work in anything that yields SSE frames.
- A new module-level API client must be patched in `services/pusher/tests/conftest.py`.
- Never read `.history/` or `docs/pm-log.jsonl`.
- Supabase writes and tag deletion or force-push: hand me the command. Aura writes need my OK.

## Git
- `develop` is the trunk; `main` is production. Branch `<type>/<kebab-desc>` from `develop`, PR to `develop`.
- Conventional Commits, lowercase subject, body says why, `Refs: #123`. Merge commits, never squash.
- Release: release PR -> `make release` -> deploy -> merge `main` back into `develop` locally, never as a PR (PR #66 deleted `main`).
- PRs go to `origin` (`ai-safe-earth/laiive`). Never push to the `laiive` remote. Commit with explicit paths.

## Roadmap and plans
- `docs/ROADMAP.md` is the roadmap. I own the step order. Never change it without asking.
- Plans live in `docs/plans/`. One file per feature or fix, starting with:
  ```yaml
  ---
  status: todo | active | blocked | done
  step: <roadmap step slug>
  next: <one line>
  ---
  ```
- Before working: read the plan for the task. If there is none, create one and ask me which roadmap step it belongs to.
- After each finished step: tick it, update `status` and `next`, write down any decision taken.
- When a plan is finished: set `status: done` and move it to `docs/plans/done/`.
- `/roadmap` refreshes the status section of `docs/ROADMAP.md`.

## Micro changes
- A micro change needs no plan file and no roadmap step: a fast debug, a copy or style tweak,
  a one-spot fix. Do it straight away, then tell me what changed.
- It is micro only if it is about 3 files and 40 lines or less, has no real design choice, and
  touches no schema, protocol, auth, money, or Supabase/Aura writes. Otherwise it needs a plan.
- Commit as usual; the body starts with `micro:` and says why. Tests still run before "done".
- When I say "micro" or "quick", treat it as micro unless it breaks the limits above; then say so.

## Tracking files
- The only tracking files are: this file, `docs/ROADMAP.md`, and `docs/plans/`.
- Do not create handoff, status, summary, audit, or report files. Put that information in the plan or in "Decisions" below.

## Decisions
- Budget $30-50/month all-in: Aura Free (auto-pauses), Supabase free, mini-first models.
- Sweeps write their "new" candidates to the graph as soon as they finish (2026-10-08); the dedup
  marks and the writer's probe guard against duplicates. `SEARCH_SWEEP_AUTO_WRITE=false` puts them
  back to dry-run with human approve. Ownership decides who may edit, never who may create.
- Chat-only, no crawlable pages yet. UI in en/es/it/ca; every string through `translations.ts`.
- Cloudflare Pages: `develop.laiive.pages.dev` is a preview alias; production is not built from `develop` (checked 2026-09-29).
- Tag `legacy-main-2026-08-19` is wrong (six commits short of the old main); owner to delete it.
- The pmctl project tracker is retired (2026-10-04). `docs/pm-log.jsonl` is history only.
- Archive branches, never build on them: `legacy/pre-refactor`, `experiment/k3s`.
- Earlier decisions (D1-D19): `docs/plans/done/foundation-refactor.md`.

## How to write final responses
- Plain English. Short sentences. Bullet points.
- Clear structure: what changed, what is next, what I must decide.
- Put in [brackets] what I should know or need to learn.
- This applies to final responses only, not to code, commits, or plan files.
