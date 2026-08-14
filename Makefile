# .env is optional for docker targets (compose reads it via env_file);
# python services load it themselves from the repo root.
-include .env
export

# ----------------- docker compose ---------------------------------------------------------------
build:
	docker-compose build

up-dev:
	docker-compose up --build

up-prod:
	docker-compose -f docker-compose.yml up --build

down:
	docker-compose down

logs:
	docker-compose logs -f

# --------------- shells into service containers -------------------------------------------------
shell-pusher:
	docker exec -it laiive-pusher sh

shell-retriever:
	docker exec -it laiive-retriever sh

# --------------- local service starters (ports match frontend/.env: 8002/8003) -------------------
start-retriever:
	cd services/retriever && uv sync && uv run uvicorn agent.api:app --host 127.0.0.1 --port 8002 --reload

start-pusher:
	cd services/pusher && uv sync && uv run uvicorn agent.api:app --host 127.0.0.1 --port 8003 --reload

start-gateway:
	cd services/gateway && npm install && npm run dev

start-search:
	cd services/search && uv sync && uv run uvicorn agent.api:app --host 127.0.0.1 --port 8004 --reload

# --------------- tests ---------------------------------------------------------------------------
test-formatting:
	cd services/retriever && uv sync && uv run pytest tests/test_formatting.py

test-safety-guard:
	cd services/retriever && uv sync && uv run pytest tests/test_safety_guard.py

test-safety-manual:
	cd services/retriever && uv sync && uv run pytest tests/test_safety_manual.py

test-safety-unit:
	cd services/retriever && uv sync && uv run pytest tests/test_safety_unit.py

# live LLM connectivity tests - cost money, need real keys
test-api:
	cd services/retriever && uv run pytest -s -vv --timeout=60 tests/test_llm_api.py

test-api-endpoints:
	cd services/retriever && uv sync && uv run pytest -v tests/test_api_endpoints.py

test-query-builder:
	cd services/retriever && uv sync && uv run pytest -v tests/test_query_builder.py

test-error-handling:
	cd services/retriever && uv sync && uv run pytest -v tests/test_error_handling.py

# all unit tests (fast, mocked)
test-unit:
	cd services/retriever && uv sync && uv run pytest -v tests/test_safety_guard.py tests/test_safety_unit.py tests/test_query_builder.py tests/test_api_endpoints.py tests/test_error_handling.py tests/test_formatting.py

test-pusher:
	cd services/pusher && uv sync && uv run pytest -v tests/

test-shared:
	cd services/shared && uv sync && uv run pytest -v tests/

# tests with coverage
test-coverage:
	cd services/retriever && uv sync && uv run pytest tests/ -v --cov=agent --cov-report=html --cov-report=term

test-all:
	make test-unit
	make test-pusher
	make test-shared
