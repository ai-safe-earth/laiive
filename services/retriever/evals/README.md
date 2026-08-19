# evals — labelled data, no harness yet

The harness that used to be documented here never existed: five guides described a
`config.py`, a `runners/` package and a `run_evals.py` that are not in the tree, and the
`utils/` sketches read log formats nothing produces. All of it is deleted — recoverable from
git history if a rewrite wants to look.

What survives is the labelled data that still maps to code that exists:

- `datasets/safety/test_cases.json` — injection and moderation cases for
  `agent/tools/safety_guard.py`.
- `datasets/query_generation/test_cases.json` — Cypher shapes and forbidden clauses for
  `agent/tools/query_builder.py`.

The two other sets went with the ReAct orchestrator whose vocabulary they encoded
(`expected_action: QUERY_DB | NEEDS_INFO`); the current pipeline speaks `query_type` and
`moment` instead, so they had to be re-labelled rather than kept.

The real harness — suites for classifier, routing, Cypher, retrieval recall, answer quality
and safety, with per-model reports and a CI tier — is the next milestone after the deploy and
the restyle. Until then there is nothing here to run.
