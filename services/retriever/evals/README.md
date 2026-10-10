# evals — labelled data, wired to the code

The harness that used to be documented here never existed: five guides described a
`config.py`, a `runners/` package and a `run_evals.py` that were not in the tree, and the
`utils/` sketches read log formats nothing produces. All of it is deleted — recoverable
from git history if a rewrite wants to look.

What survives is labelled data, and as of phase 2 it runs. There is still no `evals`
harness to invoke: the twelve cases are loaded by pytest, from
[`../tests/test_eval_cases.py`](../tests/test_eval_cases.py).

## The five datasets

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

- `datasets/answer_quality/test_cases.json` — eleven replies for `agent/composer.py`, over the
  ten situations its prompt names (results, refinement, empty, ambiguous, smalltalk,
  out_of_scope, unsafe, two non-English asks, and one carrying a retrieval note). Cards are
  fixtures under a `cards` key, so no graph is read.

  **Checked by rule, not by judge.** The roadmap budgeted two judge calls per case; most of
  the rubric does not need one. "1–3 short sentences", "never list events, dates, venues or
  prices", "one question, never a list" and "answer in the conversation's language" are all
  read off the text by a rule, and a rule does not have a bad day. The judge is deferred to
  where it would actually earn its keep — tone — and that is worth building when tone is
  what is being changed.

  The leakage rule is literal on purpose: event name, venue, the time at the door, the
  month and the price. A paraphrase ("the first one, on the Saturday") gets past it. That
  is the ceiling, and it still catches the enumeration the prompt forbids.

- `datasets/retrieval/` — the frozen graph, and the cases read off it.
  `graph.json` is eighteen events over Madrid, Barcelona and Bergamo, seeded into a
  throwaway Neo4j by `tests/graph_fixture.py`; `test_cases.json` holds ten recall cases for
  the template and nearby legs; `vector_cases.json` holds four for the vector leg;
  `embeddings.json` holds the frozen vectors that make the vector leg free to run.

  **Why a container and not a mock.** Everything above `self.neo4j.execute_read(...)` is
  pure Python and `tests/test_executor.py` covers it. Below that line is the database, and a
  `Mock` returns whatever it was told to whatever the query says — it can prove a row maps
  to a card and nothing at all about whether the query finds the event. So the fixture is a
  real Neo4j on port 7689 (`make test-graph-up`), wiped and re-seeded per session.

  **Seeded through the writer.** `laiive_shared.neo4j_writer.write_event`, the same path the
  pusher and the search service use, so uid derivation, `name_norm`, genre families and
  timezone resolution come out exactly as in production and cannot drift. Two collaborators
  are frozen instead of live: the geocoder (the fixture's own coordinates, which is what
  makes the nearby leg's metres assertable) and the embedder.

  **Dates are offsets, not timestamps** — every leg filters on upcoming events, so a fixture
  of fixed dates would quietly stop testing anything a week after it was written. Every
  event is at least a day out, since an event later *today* stops being upcoming at its own
  start time and would fail for whoever ran the suite that evening.

  **Vectors are frozen.** `evals/freeze_embeddings.py` embeds the event texts and each
  vector case's question once and checks the result in (343 KB). Embedding live would make
  the same case score differently on different days, and a moving number is not a
  measurement. The file is valid only for `text-embedding-3-small`; change the model and it
  must be regenerated, which a test asserts rather than leaves to memory.

  **The ceiling, stated plainly:** green here means the retrieval *code* is right, not that
  production answers well. The fixture has no bad geocodes, no duplicate venues and no
  missing genres — which is exactly what the real graph does have. That stays the Aura
  tier's question.

There is no `routing` suite and there should not be: `route()` is a pure function over a
`Classification`, and `tests/test_router.py` already covers every branch of it — twelve
cases including the two the roadmap calls out. A dataset would restate them in JSON.

Two other sets went with the ReAct orchestrator whose vocabulary they encoded
(`expected_action: QUERY_DB | NEEDS_INFO`); the current pipeline speaks `query_type` and
`moment` instead, so they would have had to be re-labelled rather than kept.

## Real-user feedback, grouped into threads

`python -m agent.scripts.feedback [--days 7] [--no-save]` reads every thumb and every
unflagged failure from Supabase and groups them into threads (lines of failure or
success), with counts and a trend against the last run. `failure_modes.json` holds the
thread names, descriptions and counts so the names carry over between runs; it never
holds user text. Plan: `docs/plans/real-user-feedback.md`.

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
| classifier | the corpus itself: 26 cases, unique ids, every case asserts something, the prompt version matches, no open gaps | all 26 cases, one live classification each; prompt v4 adds four from user feedback (a named place is never "near me"); v5 adds two: a search with no place needs the user's location |
| answer quality | every case names a situation, a sentence budget and a language; the fixtures resolve; the prompt version matches | all 11 cases, one live composition each (plus one language call) — 10 green since prompt v3 |
| retrieval | — | **`graph` tier, not `integration`:** 14 recall cases against the frozen graph, no OpenAI key, so CI holds them on every push |

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

## What execute-and-compare found in the cypher prompt (2026-09-23)

Both found on the first run, both invisible to the regex the corpus used until v3.0, and
both fixed in `QUERY_BUILDER_PROMPT` (now v3) with the suite re-run to prove it.

1. **The prompt invited a syntax error.** Its mandated RETURN shape ends with
   `collect(DISTINCT art.name) AS artists`, which aggregates — so `e`, `v` and `c` are out
   of scope afterwards, and the `ORDER BY e.start_at` the model naturally appended is a
   syntax error Neo4j refuses. Three of the five cases died on it. In production that is the
   whole long-tail leg failing whenever it sorts by date. The prompt now says to order by
   the returned alias, which is what the hand-written templates in `executor.py` have always
   done.
2. **The relationship went backwards about half the time.** `(v:Venue)-[:HOSTED_AT]->(e:Event)`
   is the wrong direction; it raises nothing and returns zero rows, which reaches the person
   asking as "there is nothing on". The prompt now says direction is part of the pattern,
   names that exact inversion, and offers the undirected form when in doubt. Three runs green
   after, where it failed in two of three before.

One label of mine was wrong and is corrected in the dataset: `qg_003` asked for "next
month", the model read it as the calendar month and dropped a gig two days out. That is a
defensible reading, and a case about venue matching should not also be a case about what
"next month" means — the question now says "in the next 30 days".

## The one known gap in the answer-quality set (2026-09-22, closed in prompt v3)

`italian-question-italian-answer` — the reply names the event and the act ("I Lupi suonano
al Druso"), which the prompt forbids outright, because the cards say that next to the text.

Probed before it was written down, since the case's language was the obvious suspect and
the obvious suspect was wrong: **it is the single result, not the Italian.** With one card
the reply leaked 3/3 in Italian and 1 in 2 in English; with three cards, English and
Spanish held 2/2. The prompt's "NEVER list events" has no rule for the case where there is
exactly one thing to not-list, and the model reaches for it to have something to say.

**Closed 2026-10-08 (prompt v3)** with one rule: a single result is no exception, nod to
the kind of music. The first wording's example, "one rock night", tripped the leak rule
anyway: the fixture event is called "Notte Rock", so "una notte rock" matched its name.
That is the literal rule's ceiling (a generic event name), so the example became "one rock
gig". Probed 8 of 8 clean, then the live suite 10 of 10 twice.

## The six known gaps in the classifier set (2026-09-22, all closed in prompt v3)

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

**How v3 closed them (2026-10-08).** The two rules that must always hold are code, in
`classifier.enforce()`, not prompt wording: a message with no history is always
`first_query` (it can neither refine nor change a topic), and `near_me` without a shared
location is `ambiguous` with a clarification. The prompt gained three rules: "free" is
`price_max: 0`, a bare place name is a search there, and "find me something" is ambiguous.
`nearby` left the `Literal` (a stray one is read as `event_search`), and the `near-me`
label followed. A first attempt that put the history rule in the prompt instead flipped
"actually, what about Lisbon?" to `new_topic`; code was the steadier place for it.

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
