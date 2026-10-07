# Dev box: machine gotchas

Windows box. Read when a command fails in a strange way. Linked from `CLAUDE.md`.

Windows. `bun` is NOT installed — npm/node. Port 8080 is EnterpriseDB's.

**Running things**

- `uv run uvicorn …` and `uv run pytest` both fail here with "Failed to canonicalize script
  path". Use `uv sync` then `uv run --no-sync python -m uvicorn …` / `python -m pytest -q`.
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
- Another project squats :8000 (an `A02_VaiVia` uvicorn). Everything is env-overridable, so
  shift rather than kill: `GATEWAY_PORT`, `RETRIEVER_URL`, `PUSHER_URL`, `CORS_ALLOW_ORIGINS`,
  and inline `VITE_API_URL` for Vite (inline `VITE_*` beats `.env` files).

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
- **The `aura-neo4j` and `tavily` MCP servers are NOT available in this directory** — they are
  registered under the repo's old path (`MAIN/DS_ML_AI/DIALOGOO/laiive`), so query through the
  service, not the MCP. If they are re-added here: `aura-neo4j` points at `2099d44c`, and its
  host `2099d44c.mcp-instances.neo4j.io` stopped resolving once while the database itself was
  fine on `2099d44c.databases.neo4j.io`.
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
- `gh pr edit` dies on the GraphQL Projects-classic deprecation. Edit a PR with
  `gh api -X PATCH repos/ai-safe-earth/laiive/pulls/N --input f.json`.

**Flaky tests**

- `Auth.test.tsx` times out on 1-2 specs under parallel load here; passes alone and on CI.
