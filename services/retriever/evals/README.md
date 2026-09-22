# evals — labelled data, wired to the code

The harness that used to be documented here never existed: five guides described a
`config.py`, a `runners/` package and a `run_evals.py` that were not in the tree, and the
`utils/` sketches read log formats nothing produces. All of it is deleted — recoverable
from git history if a rewrite wants to look.

What survives is labelled data, and as of phase 2 it runs. There is still no `evals`
harness to invoke: the twelve cases are loaded by pytest, from
[`../tests/test_eval_cases.py`](../tests/test_eval_cases.py).

## The three datasets

- `datasets/safety/test_cases.json` — seven cases for `agent/tools/safety_guard.py`.
  Each names its `check`: `cypher_guard` (`validate_read_only`), `injection`
  (`detect_injection`) or `moderation` (`moderate`).
- `datasets/query_generation/test_cases.json` — five Cypher shapes for
  `agent/tools/query_builder.py`, with `expected_patterns` (regex, case-insensitive) and
  `should_not_contain` (literal substrings).

- `datasets/classifier/test_cases.json` — twenty messages for `agent/classifier.py`, the
  roadmap's `classifier` suite. Each carries an `expect` block asserting `query_type`,
  `moment`, `language`, how many sub-queries the ask splits into, and constraint fields
  against *any* sub-query. Four values do the work: a string is an equality
  (case-insensitive), `null` is "this field stays empty", `"any"` is "this field is
  filled", and `today`/`tomorrow` are dates on the Europe/Madrid clock every case runs on.

  **The labels are what a reader of the message would expect, not a transcript of what the
  model answers.** Six cases are therefore red, each carrying a `known_gap` sentence and
  xfailed — see below. Two labels were corrected after the first live run instead, and say
  so in a `label_note`: `refinement` rather than `new_topic` for "actually, what about
  Lisbon next month?" (the prompt's own rule: replace the city, keep the rest), and
  `out_of_scope` rather than `smalltalk` for "what can you do?" (the prompt scopes
  smalltalk to greetings, thanks and goodbyes).

There is no `routing` suite and there should not be: `route()` is a pure function over a
`Classification`, and `tests/test_router.py` already covers every branch of it — twelve
cases including the two the roadmap calls out. A dataset would restate them in JSON.

Two other sets went with the ReAct orchestrator whose vocabulary they encoded
(`expected_action: QUERY_DB | NEEDS_INFO`); the current pipeline speaks `query_type` and
`moment` instead, so they would have had to be re-labelled rather than kept.

## How to run them

```bash
cd services/retriever
# no network:
uv run --no-sync python -m pytest -q -m "not integration" tests/test_eval_cases.py tests/test_classifier_cases.py
# needs OPENAI_API_KEY (~20 cheap classifier calls + the six live cases, about a minute):
uv run --no-sync python -m pytest -q -m integration tests/test_eval_cases.py tests/test_classifier_cases.py
```

The default run is what CI holds. The integration tier needs an OpenAI key but **not**
Neo4j — the Cypher cases assert on what the model generates, against a static schema
string, so a paused Aura cannot break them.

## What the tiers assert

| | deterministic | integration |
|---|---|---|
| safety | 6 cases: the four Cypher-guard verdicts and the two injection verdicts | `sf_007` — the moderation verdict, the only case of the seven that needs a live judgement |
| query generation | a generated mutation is refused and never reaches the driver | `should_not_contain` against the real generation, and `expected_patterns` (xfailed) |
| classifier | the corpus itself: 20 cases, unique ids, every case asserts something, the prompt version matches, six gaps each explained | all 20 cases, one live classification each — 14 green, 6 xfailed |

`should_not_contain` is the corpus's real gate, so it is asserted in both tiers rather
than only where a model is available. Offline it is the durable property — *whatever* the
prompt emits, `QueryBuilderTool.run` validates before executing, so a mutation is refused
— which holds across prompt revisions and costs no tokens. Online it is the literal
reading: the generator did not emit one.

`expected_patterns` is `xfail(strict=False)`. Regex over generated Cypher asserts shape,
not whether the query answers the question, and it goes red every time the prompt is
legitimately reworded. Phase 4 replaces it with execute-and-compare: run the query, compare
the rows. The patterns are kept current anyway, so the xfail reads "wrong instrument", not
"stale data" — and an XPASS is information, not a failure.

## The six known gaps in the classifier set (2026-09-22)

Found by the first live run. Each case keeps its label and is `xfail(strict=False)`, so a
weekly run reports a *regression* rather than re-reporting six holes somebody already
knows about — and a prompt fix turns the case green (XPASS) without a dataset edit in the
same commit. The two that cost a user an answer are the first two.

| case | what the prompt does today |
|---|---|
| `near-me-without-a-location` | `first_query` + `near_me: true` + no clarification. `route()` then drops the only plan, so the turn says "nothing found" instead of asking where the user is — and `router.py`'s own comment claims the classifier marks these ambiguous. |
| `empty-ask-needs-more` | "find me something" → `new_topic`, no sub-queries, no clarification. The prompt's own `ambiguous` rule, unused. |
| `bare-city-is-answerable` | "Granada" → no sub-queries, so nothing is searched. Arguable, and the owner's call: a one-word message could also be read as needing a clarification. |
| `free-gigs` | "free concerts" leaves `price_max` unset — the prompt never says free means `price_max: 0`, so paid gigs come back. |
| `two-cities-one-message` | splits the two cities correctly, then calls the moment `refinement` on a message with no history. |
| `near-me` | `query_type: "event_search"` where the label says `"nearby"`. Nothing in the prompt defines when `nearby` is the type and `route()` keys off `near_me` alone, so the value is unreachable vocabulary: either the prompt names it or the `Literal` loses it. |

## Two relabellings, 2026-08-28

Both files are `version: 2.0`. The originals are in git history; each case carries the
reason it changed.

**Safety.** `expected_violations` used a taxonomy no code produces — `mutation_detected`,
`injection_pattern`, `prompt_injection`, `harmful_content` — and no case said which
function it addressed. That is why the set was never wired: there was nothing to call.
Violations are now the guard's own keywords (`DELETE`, `CREATE`, `DROP`), every case names
its `check`, and the old label is kept as `taxonomy_v1`.

Worth knowing, from doing the wiring: `sf_004` (`1' OR '1'='1; DROP TABLE events--`) is
**not** caught by `detect_injection` — its `DROP` rule only fires on
`CONSTRAINT|INDEX|DATABASE`, and the string says `TABLE`. The Cypher guard catches it on
the bare `DROP` keyword, which is the layer that actually stops it reaching the driver, so
it is labelled a `cypher_guard` case. If user text ever needs that verdict on its own, the
`detect_injection` pattern is the thing to widen.

**Query generation.** All five `expected_patterns` lists were stale against
`QUERY_BUILDER_PROMPT` v2 and every one would have failed:

| | v1 expected | v2 says |
|---|---|---|
| `qg_001`, `qg_003` | names matched as written (`Radiohead`, `Berghain`) | match through `name_norm` — lowercase, no diacritics |
| `qg_002`, `qg_003` | `datetime(e.start_at)` **required** | "never wrap `e.start_at` in `datetime()`" — it is a native DATETIME |
| `qg_004` | `price_amount < 20` | the fields are `price_min` and `price_max`; `price_amount` is not in the schema |
| `qg_005` | an `embedding` clause, `tests_feature: semantic_search` | the query builder has no vector search and its prompt never mentions embeddings |

The two banned shapes moved from `expected_patterns` to `should_not_contain`, so a
regression towards them is now caught rather than demanded. `qg_005` is re-pointed at what
the system actually does with "similar to X" — `Genre` nodes keyed by the slug
`indie-rock`; semantic search stays a phase-4 question. `expected_cypher_structure` and
`date_context` were dropped: nothing consumed them, and dates are resolved from the asker's
clock at generation time, not from the case.

## Next

Phase 3 is error analysis — reading the production corpus (`eval_records` joined to
`conversation_logs` and `turn_feedback`; the query is in
`docs/explain/eval-phases-0-1.html` §5) and naming the failure modes by hand. The judge
rubric comes from those labels, not before them.

Phase 4 is the real harness: `python -m evals.run --suite <name>` over six suites
(routing, classifier, cypher, retrieval, answer-quality, safety), the deterministic tier in
CI, LLM tiers nightly. That is when `evals/` grows code again — and when
execute-and-compare retires the xfail above.
