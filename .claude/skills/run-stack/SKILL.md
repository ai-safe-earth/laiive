---
name: run-stack
description: Start the laiive stack (gateway, retriever, pusher, optional search, frontend) on the ports the frontend actually targets. Use when asked to run, start, or serve the app locally.
disable-model-invocation: true
---

Start the local stack. `$ARGUMENTS` selects what to start:

- empty or `all` — gateway + retriever + pusher + frontend
- `gateway` / `retriever` / `pusher` / `search` / `frontend` — just that one
- `backend` — gateway + retriever + pusher, no frontend

## Topology

The browser talks **only to the gateway**. It authenticates the Supabase JWT, injects
`X-User-Id`/`X-User-Role`, rate-limits, and proxies `/api/chat/*` → retriever, `/api/push/*` →
pusher, `/api/admin/search/*` → search. The Python services have no CORS allowance for the
browser, so pointing the frontend straight at 8002/8003 fails.

| service | default port | health |
|---|---|---|
| gateway (Fastify) | 8000 | `/healthz` — **not** `/health`, that 404s |
| retriever | 8002 | `/health` |
| pusher | 8003 | `/health` |
| search (optional) | 8004 | `/health` |
| frontend (Vite) | 8081 | — |

Frontend port is 8081, not 8080: EnterpriseDB holds 8080 on this machine. **bun is not
installed here** — use npm, despite `frontend/package.json` history.

## Steps

1. Check the root `.env` exists. If it doesn't, tell the user to copy `.example.env` to `.env`
   and fill it in, then stop. All Python services read it as `env_file="../../.env"` and the
   gateway as `../../.env` from `services/gateway`, both relative to their own directory.

2. **Check the ports before starting anything.** Other projects on this machine squat on
   8000/8002/8003 (an `A02_VaiVia` uvicorn, a `laiive-global-workspace` docker container), and
   stale laiive servers from an earlier session are worse than absent ones — they serve deleted
   code or a pre-repair `.env`:

   ```powershell
   Get-NetTCPConnection -LocalPort 8000,8002,8003,8004,8081 -State Listen -ErrorAction SilentlyContinue |
     ForEach-Object { $p = Get-Process -Id $_.OwningProcess; "$($_.LocalPort) $($p.Id) $($p.ProcessName) $($p.StartTime)" }
   ```

   If a port belongs to another project, don't kill it — shift this stack onto free ports
   (see *Port conflicts*). If it's a stale laiive server, kill it by PID: background dev servers
   survive their launcher, so stopping the wrapped task leaves `node`/`python` holding the port.

3. Retriever, in the background:
   ```powershell
   Set-Location <repo>/services/retriever; $env:VIRTUAL_ENV=""; uv sync
   Set-Location <repo>/services/retriever; $env:VIRTUAL_ENV=""; uv run --no-sync python -m uvicorn agent.api:app --host 127.0.0.1 --port 8002
   ```

4. Pusher, same shape:
   ```powershell
   Set-Location <repo>/services/pusher; $env:VIRTUAL_ENV=""; uv sync
   Set-Location <repo>/services/pusher; $env:VIRTUAL_ENV=""; uv run --no-sync python -m uvicorn agent.api:app --host 127.0.0.1 --port 8003
   ```

5. Gateway, in the background:
   ```powershell
   Set-Location <repo>/services/gateway; npm install --silent; npm run dev
   ```

6. Frontend, in the background:
   ```powershell
   Set-Location <repo>/frontend; npx vite --port 8081 --strictPort
   ```
   Vite serves with no proxy — the browser calls the gateway origin from
   `VITE_API_URL` (`frontend/.env`, default `http://localhost:8000`), which the gateway allows
   via `CORS_ALLOW_ORIGINS` (default `http://localhost:8081`).

7. Search only when the task needs sweeps — it also needs `SEARCH_ENABLED=true` in the root
   `.env` or the gateway answers `/api/admin/search/*` with 503:
   ```powershell
   Set-Location <repo>/services/search; $env:VIRTUAL_ENV=""; uv run --no-sync python -m uvicorn agent.api:app --host 127.0.0.1 --port 8004
   ```

8. Health-check whatever you started before reporting ready, and report the URLs actually
   listening:
   ```powershell
   Invoke-WebRequest http://127.0.0.1:8000/healthz -UseBasicParsing
   Invoke-WebRequest http://127.0.0.1:8002/health  -UseBasicParsing
   Invoke-WebRequest http://127.0.0.1:8003/health  -UseBasicParsing
   ```

## Windows launch traps

- **`uv run uvicorn …` fails** with `Failed to canonicalize script path`. Use
  `uv run --no-sync python -m uvicorn …` and do the `uv sync` as a separate step. Consequence:
  no `--reload` in that form is fine to add, but backend edits under this recipe need a restart
  unless you pass `--reload` explicitly.
- **`npm run dev -- --port 8081` loses the flags** — PowerShell mangles the `--` separator and
  Vite starts on 5173 treating `8081` as a root dir. Call `npx vite` directly.
- `uv run` warns that `VIRTUAL_ENV=…\laiive\.venv` doesn't match the project env. Harmless, but
  clearing it (`$env:VIRTUAL_ENV=""`) keeps the output readable.
- `make start-retriever` / `start-pusher` / `start-gateway` / `start-search` exist and use the
  same ports, but they `cd` in a shell whose CWD doesn't persist reliably here — prefer the
  explicit `Set-Location` form above.

## Port conflicts

Every port is env-overridable, so a squatted port never needs a kill. Set these on the
*gateway* process (process env wins over the root `.env` — dotenv doesn't override) and inline
on Vite (Vite prioritises inline `VITE_*` over `.env` files):

```powershell
$env:GATEWAY_PORT="8100"; $env:RETRIEVER_URL="http://127.0.0.1:8102"
$env:PUSHER_URL="http://127.0.0.1:8103"; $env:SEARCH_URL="http://127.0.0.1:8104"
$env:CORS_ALLOW_ORIGINS="http://localhost:8081"
# and on the frontend:
$env:VITE_API_URL="http://localhost:8100"
```

Then pass the matching `--port` to each uvicorn. Leave `frontend/.env` alone — it is committed
config, not a scratchpad.

## If a service dies on startup

- **Retriever/pusher import error**: the pipeline is built lazily since Phase 2, so an import
  failure is usually a config one — both configs fail loudly listing the missing env keys.
  A `/health` that reports `neo4j: error` or `openai: error` on a server started *before* an
  `.env` repair is a stale process, not a bug; restart it.
- **Gateway throws `missing required environment keys`**: `SUPABASE_URL` /
  `SUPABASE_SERVICE_ROLE_KEY` are the only hard requirements.
- **Frontend loads but every call 401s**: the browser has a token from the dead Supabase project.
  Sign out, or clear the `sb-*` localStorage keys. The live project is `pjlcfdyheyubsemwlzzv`.
