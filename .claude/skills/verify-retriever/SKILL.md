---
name: verify-retriever
description: Run the retriever test suite using the targets that actually exist, routing around the broken Makefile targets. Use after changing anything under services/retriever.
---

Run tests for `services/retriever`. Always `cd services/retriever` first — there is no root uv
project, and every service resolves the root `.env` relative to its own directory.

Two invocations are broken here and both fail *before* running anything real:

- `make test-integration`, `make test-all`, `make dashboard` reference
  `tests/test_pipeline_metrics.py` and `agent.utils.metrics`, neither of which exists.
- Bare **`uv run pytest`** dies on this machine with `Failed to canonicalize script path`. Use
  `uv sync` as its own step, then `uv run --no-sync python -m pytest`.

## Default — unit tests, no external services

```
cd services/retriever && uv sync
cd services/retriever && uv run --no-sync python -m pytest -q -m "not integration"
```

(The suite was reorganized in the Phase 2 refactor — don't list test files by
name, the markers are the source of truth.)

## Integration — hits real Neo4j and OpenAI/OpenRouter, costs money

Confirm with the user before running.

```
cd services/retriever && uv run --no-sync python -m pytest -v --timeout=120 \
  tests/test_full_pipeline.py tests/test_llm_api.py
```

(`make test-integration` also lists `tests/test_pipeline_metrics.py`; it doesn't exist, which is
why this omits it.)

## Coverage

```
cd services/retriever && uv run --no-sync python -m pytest tests/ --cov=agent --cov-report=term
```

## Single test

```
cd services/retriever && uv run --no-sync python -m pytest -v tests/test_query_builder.py::test_name
```

Add `--timeout=120` to anything that calls an LLM.

## Reading failures

Report the actual pytest output, and distinguish two failure shapes:

- **Collection error / import error** — `agent/api.py` builds the Neo4j schema and the
  `Orchestrator` at import time. If Neo4j is unreachable or the creds are wrong, every test that
  imports the app dies at collection. That is an environment problem, not a test failure.
- **Assertion failure** — a real regression. Investigate.
