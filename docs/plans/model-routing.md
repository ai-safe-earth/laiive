---
status: todo
step: model-routing
next: design the role table for services/shared/laiive_shared/llm.py
---
# Multi-provider model routing (program phase 4)

New `services/shared/laiive_shared/llm.py`: one call surface over OpenAI, Anthropic and
OpenRouter. It resolves roles (`classifier`, `cypher`, `composer`, `extraction`,
`language_detect`, `judge`, `embeddings`) to provider-prefixed model ids, with retries,
fallback on provider outage, per-call cost and Phoenix tracing. It must keep real token
streaming in `composer.compose_stream` (fake-streaming regressed twice).

## Steps
- [ ] Build `llm.py`.
- [ ] Migrate module-level clients: retriever `llm_utils`, search `extraction`,
      `laiive_shared.language`, the pusher's three (move their patches in
      `services/pusher/tests/conftest.py` too).
- [ ] `python -m evals.run --suite x --models a,b`; pick role models from a cost/quality table.
