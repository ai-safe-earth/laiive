include .env
export

# -----------------BUILD DOCKER COMPOSE FOR DEV AND PROD----------------------------------------------------------------------
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


# ---------------SHELL FOR DEV INSIDE EACH SERVICE CONTAINER ------------------------------------------------------------------

# Update shell commands:
shell-pusher:
	docker exec -it laiive-pusher sh

shell-retriever:
	docker exec -it laiive-retriever sh

# Update service starters:
start-retriever:
	cd services/retriever && uv sync && uv run uvicorn agent.api:app --host 0.0.0.0 --port 8000 --reload

start-pusher:
	cd services/pusher && uv sync && uv run uvicorn agent.api:app --host 0.0.0.0 --port 8001 --reload

# tests

test-metrics:
	cd services/retriever && uv sync && uv run pytest -s -vv --timeout=120 tests/test_pipeline_metrics.py

test-full-pipeline:
	cd services/retriever && uv sync && uv run pytest tests/test_full_pipeline.py

test-formatting:
	cd services/retriever && uv sync && uv run pytest tests/test_formatting.py

test-safety-guard:
	cd services/retriever && uv sync && uv run pytest tests/test_safety_guard.py

test-safety-manual:
	cd services/retriever && uv sync && uv run pytest tests/test_safety_manual.py

test-safety-unit:
	cd services/retriever && uv sync && uv run pytest tests/test_safety_unit.py

test-api:
	cd services/retriever && uv run pytest -s -vv --timeout=60 tests/test_llm_api.py

# New comprehensive tests
test-api-endpoints:
	cd services/retriever && uv sync && uv run pytest -v tests/test_api_endpoints.py

test-orchestrator:
	cd services/retriever && uv sync && uv run pytest -v tests/test_orchestrator_unit.py

test-query-builder:
	cd services/retriever && uv sync && uv run pytest -v tests/test_query_builder.py

test-error-handling:
	cd services/retriever && uv sync && uv run pytest -v tests/test_error_handling.py

# Run all unit tests (fast, mocked)
test-unit:
	cd services/retriever && uv sync && uv run pytest -v tests/test_safety_guard.py tests/test_safety_unit.py tests/test_orchestrator_unit.py tests/test_query_builder.py tests/test_api_endpoints.py tests/test_error_handling.py

# Run all integration tests (slower, may need external services)
test-integration:
	cd services/retriever && uv sync && uv run pytest -v tests/test_full_pipeline.py tests/test_pipeline_metrics.py tests/test_llm_api.py

# Run tests with coverage
test-coverage:
	cd services/retriever && uv sync && uv run pytest tests/ -v --cov=agent --cov-report=html --cov-report=term

dashboard:
	cd services/retriever && uv run python -m agent.utils.metrics print_live_dashboard

test-all:
	make test-safety-guard
	make test-safety-manual
	make test-safety-unit
	make test-orchestrator
	make test-query-builder
	make test-api-endpoints
	make test-error-handling
	make test-formatting
	make test-full-pipeline
	make test-metrics
	make test-api

	# ============== EVALS ==============

# Run all component evals
eval-all:
	cd services/retriever && uv run python evals/run_evals.py --component all

# Run specific component evals
eval-query-builder:
	cd services/retriever && uv run python evals/run_evals.py --component query_builder

eval-intent:
	cd services/retriever && uv run python evals/run_evals.py --component intent_classification

eval-safety:
	cd services/retriever && uv run python evals/run_evals.py --component safety_guard

# Run end-to-end system evals
eval-e2e:
	cd services/retriever && uv run python evals/run_evals.py --system

# Compare prompt versions
eval-compare-prompts:
	cd services/retriever && uv run python evals/run_evals.py --component query_builder --compare-prompts

# Extract from production logs and create datasets
eval-extract-logs:
	cd services/retriever && uv run python -c "\
	from evals.utils.smart_extraction import SmartLogExtractor; \
	extractor = SmartLogExtractor(use_llm_evaluation=False, min_score=0.5); \
	extractor.extract_filter_and_create_datasets('logs/requests.jsonl')"

# Full eval pipeline: extract + run evals
eval-pipeline:
	make eval-extract-logs
	make eval-all
