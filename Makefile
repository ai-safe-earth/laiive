# .env is optional for docker targets (compose reads it via env_file);
# python services load it themselves from the repo root. Only GATEWAY_PORT is
# exported to recipes: a blanket `export` of the included .env poisons values
# for the services, because make strips inline comments but keeps the trailing
# whitespace (CLASSIFIER_MODEL became "gpt-4o-mini<14 spaces>" -> OpenAI 400
# invalid model ID) and env vars beat the env_file in pydantic and dotenv.
-include .env

# Every recipe, not just the rich-using ones: rich's cp1252 console writer dies
# on accented output on this machine *after* the command has already succeeded,
# and a per-recipe prefix only works when make's shell is a POSIX one.
export PYTHONIOENCODING := utf-8

# ----------------- docker compose ---------------------------------------------------------------
up-dev:
	docker compose up --build

down:
	docker compose down

# The trace collector alone — the rest of the dev compose is idle shells, so
# `up-dev` is the wrong tool when all you want is somewhere for spans to land.
phoenix:
	docker compose up -d phoenix
	@echo "Phoenix UI: http://localhost:6006"

# --------------- local service starters (gateway :8000 is the only public surface) ---------------
# `uv run uvicorn` fails on some machines ("Failed to canonicalize script path");
# sync first, then run uvicorn as a module without re-syncing.
start-retriever:
	cd services/retriever && uv sync && uv run --no-sync python -m uvicorn agent.api:app --host 127.0.0.1 --port 8002 --reload

start-pusher:
	cd services/pusher && uv sync && uv run --no-sync python -m uvicorn agent.api:app --host 127.0.0.1 --port 8003 --reload

start-gateway:
	cd services/gateway && npm install && npm run dev

start-search:
	cd services/search && uv sync && uv run --no-sync python -m uvicorn agent.api:app --host 127.0.0.1 --port 8004 --reload

start-frontend:
	cd frontend && npm install && $(if $(GATEWAY_PORT),VITE_API_URL=http://localhost:$(GATEWAY_PORT) )npx vite --port 8081 --strictPort

# The whole chat stack in one terminal: retriever :8002, gateway :8020,
# frontend :8081. Pusher is not part of it - `make start-pusher` separately
# for the pro flow. The local gateway defaults to 8010, not 8000: VaiVia's
# uvicorn owns :8000 on this box and stays. The gateway reads GATEWAY_PORT
# from the env, and start-frontend passes the matching inline VITE_API_URL,
# which beats frontend/.env. Deploys are untouched (fly.toml sets its own
# port).
export GATEWAY_PORT ?= 8020
dev:
	$(MAKE) -j3 start-retriever start-gateway start-frontend

# --------------- tests ---------------------------------------------------------------------------
# Mirrors CI: ruff + pytest per service, integration tests deselected
# (they need a live Aura and real keys - see the verify-retriever skill).
test-shared:
	cd services/shared && uv sync && uv run pytest -q

test-retriever:
	cd services/retriever && uv sync && uv run pytest -q -m "not integration"

test-pusher:
	cd services/pusher && uv sync && uv run pytest -q

test-search:
	cd services/search && uv sync && uv run pytest -q

test-gateway:
	cd services/gateway && npm test

# --------------- the frozen graph (retrieval + cypher evals) --------------------------------------
# A throwaway Neo4j on 7689, seeded per test session from
# services/retriever/evals/datasets/retrieval/graph.json. Without it the `graph`
# tier skips, which is why `test-retriever` above stays useful on its own.
test-graph-up:
	docker compose -f docker-compose.test.yml up -d --wait
	@echo "frozen graph: bolt://localhost:7689 (browser http://localhost:7476)"

test-graph-down:
	docker compose -f docker-compose.test.yml down -v

# The tier CI holds: needs the container, needs no OpenAI key.
test-graph:
	cd services/retriever && uv run --no-sync pytest -q -m "graph and not integration"

test-all: test-shared test-retriever test-pusher test-search test-gateway

# --------------- release (see README.md, Releasing) ----------------------------------------------------
# Run on main, after the release PR from develop has merged: cz reads the
# Conventional Commits since the last tag, picks the version, writes the
# CHANGELOG section, commits and tags. PYTHONIOENCODING is exported at the top
# of this file rather than prefixed here: a `VAR=value cmd` prefix is shell
# syntax, and make runs recipes through cmd.exe from PowerShell, which reads it
# as a command name and fails with "'PYTHONIOENCODING' is not recognized".
# Exporting works whatever shell make ends up with.
release:
	uvx --from commitizen==3.13.0 cz bump --changelog --yes

release-dry-run:
	uvx --from commitizen==3.13.0 cz bump --changelog --dry-run --yes

# --------------- deploy (Fly.io, see DEPLOY.md) ---------------------------------------------------
# The build context must be services/ (the Dockerfiles COPY shared/ + the service);
# the redis app deploys from a stock image, so any context works.
# Secrets first: fly-secrets-check reports missing key NAMES without touching Fly.
fly-secrets-check:
	sh deploy/fly/set-secrets.sh --check

fly-secrets:
	sh deploy/fly/set-secrets.sh

# flyctl resolves BOTH --config and --dockerfile relative to the positional
# build-context directory, not to the shell's cwd. Passing repo-root paths made
# it look for services/services/retriever/Dockerfile and, before that, fail with
# "the config for your app is missing an app name" -- so the deploy runs from
# services/ and both paths are relative to it.
# One rule for the four service apps: gateway, retriever, pusher, search.
fly-deploy-%:
	cd services && flyctl deploy . --config ../deploy/fly/$*.toml --dockerfile $*/Dockerfile

fly-deploy-redis:
	flyctl deploy . --config deploy/fly/redis.toml
