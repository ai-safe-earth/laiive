# .env is optional for docker targets (compose reads it via env_file);
# python services load it themselves from the repo root.
-include .env
export

# ----------------- docker compose ---------------------------------------------------------------
build:
	docker compose build

up-dev:
	docker compose up --build

up-prod:
	docker compose -f docker-compose.yml up --build

down:
	docker compose down

logs:
	docker compose logs -f

# --------------- shells into service containers -------------------------------------------------
shell-pusher:
	docker exec -it laiive-pusher sh

shell-retriever:
	docker exec -it laiive-retriever sh

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

test-all:
	make test-shared
	make test-retriever
	make test-pusher
	make test-search
	make test-gateway

# --------------- deploy (Fly.io, see DEPLOY.md) ---------------------------------------------------
# The build context must be services/ (the Dockerfiles COPY shared/ + the service);
# the redis app deploys from a stock image, so any context works.
# Secrets first: fly-secrets-check reports missing key NAMES without touching Fly.
fly-secrets-check:
	sh deploy/fly/set-secrets.sh --check

fly-secrets:
	sh deploy/fly/set-secrets.sh

fly-deploy-gateway:
	flyctl deploy services --config deploy/fly/gateway.toml --dockerfile services/gateway/Dockerfile

fly-deploy-retriever:
	flyctl deploy services --config deploy/fly/retriever.toml --dockerfile services/retriever/Dockerfile

fly-deploy-pusher:
	flyctl deploy services --config deploy/fly/pusher.toml --dockerfile services/pusher/Dockerfile

fly-deploy-search:
	flyctl deploy services --config deploy/fly/search.toml --dockerfile services/search/Dockerfile

fly-deploy-redis:
	flyctl deploy . --config deploy/fly/redis.toml
