# 01 — The program after the refactor

Agreed with the owner on 2026-08-19, immediately after `refactor/foundation` merged into
`main`. Order matters here: each phase is what makes the next one measurable.

Two decisions frame the whole thing:

- **Evals come before optimisation.** Accuracy, cost and voice work are all claims until
  there is a harness that can tell whether a change helped.
- **Speculative decoding is out.** It is not exposed by hosted model APIs and self-hosting was
  rejected. The latency levers here are prompt caching, parallel sub-query execution, and a
  semantic cache on the Redis the stack already runs.

---

## 1. Deploy — owner-driven, per root `DEPLOY.md`

Gated on Supabase migration `20260818000010`, which the owner pushes. Then the runbook as
written: Fly apps + redis volume, secrets per app, deploy order, Cloudflare Pages, origin
stitching, smoke checklist.

Two things only become possible once a public gateway exists: `prefect.yaml` moving off
`flows/serve.py` onto a managed pool, and the CI deploy workflow that was deferred as
untestable without secrets.

## 2. A new visual direction

**Direction first.** A design canvas — palette, type scale, spacing, motion — plus artboards
for the five real surfaces: chat with results, the empty and ambiguous states, the pro
multi-event walk, account, auth. The current tokens in `frontend/src/index.css` (fuchsia
`#FF2AA0`, electric yellow, sky cyan on black; Montserrat + IBM Plex; a second `--pro-*` theme)
are the starting point to react against. **The owner approves the look before any React
changes.**

**Then implement.** Tokens in `index.css` and `tailwind.config.ts` move the whole app at once;
after that, grow `frontend/src/components/ui/` beyond `Button`/`Input` into a real primitive
set, then the pages and `EventCardView` / `EventMap` / `MicButton`.

Two constraints hold through the restyle: protocol types are never redeclared in the frontend
(they come from `services/shared/ts/protocol.ts`), and every string goes through
`src/i18n/translations.ts` in four languages — a restyle is exactly where hardcoded English
creeps back in.

**And the feedback control** on assistant turns, wired to the gateway. It is small and visual,
and phase 7's self-improvement loop has no signal without it.

## 3. Evals + observability

Nothing after this is a claim without it.

**The baselines to beat.** Measured against the live graph in the geocoding and sweep-quality
sessions of 2026-08-18, and the numbers any change here should be compared against:

- All 35 venues stamped `venue`; none beyond the 25 km city guard; the eight Barcelona venues
  that shared one pin now have eight distinct pins.
- Genre reachability 43 → 55 of 57 events after tagging 12 artists; the hyphen-boundary genre
  match took `rock` 7 → 18 events and `pop` 16 → 23.
- 48 fabricated "free" prices cleared and 30 fabricated midnight starts marked date-only.
  Clearing the prices was lossy: a genuinely free night has lost that fact until a sweep
  re-reads its page.
- No date poisoning (the heaviest day is 5 events at 5 venues) and no non-music events in the
  corpus. There are no duplicate events; the duplication is in venues.

**One turn, one trace.** Langfuse currently wraps only the retriever's OpenAI client
(`services/retriever/agent/utils/llm_utils.py`); pusher and search use bare clients. All three
get the same wrapper, and `pipeline.run_turn` opens a trace with spans for
`classify → route → execute → compose`, tagged with prompt version, model per role, language,
resolved constraints, plan kind, row count, latency and cost.

**Capture responses, not just requests.** `services/gateway/src/logging.ts` logs the request
side only. Response capture for `/api/chat/*` — final text, card uids, classification — is what
turns production turns into eval candidates, and it is where the feedback signal lands.

**The harness** at `services/retriever/evals/`, rebuilt rather than resurrected. A
`python -m evals.run --suite <name> [--models a,b] [--baseline <report>]` CLI writing a JSON
report and a markdown diff, over six suites:

| suite | what it asserts | cost |
|---|---|---|
| routing | `route()` output vs expected `PlanKind` per sub-query | free |
| classifier | `query_type`, `moment` and each constraint field against a golden set | one cheap call per case |
| cypher | generated Cypher passes the guard, `EXPLAIN`s cleanly, returns the standard shape | one call per case |
| retrieval | recall@k over a frozen graph fixture; an integration tier against live Aura | graph only |
| answer quality | judge rubric: grounded, no listing leakage, right language, 1–3 sentences, tone | two calls per case |
| safety | injection, moderation, write-gate cases | mixed |

The deterministic tier runs in CI on every push; the LLM suites run nightly or on demand,
because they cost money. `make eval-*` targets mirror the per-service test targets.

## 4. Multi-provider model routing

A new `services/shared/laiive_shared/llm.py`: one call surface over OpenAI, Anthropic and
OpenRouter, resolving **roles** (`classifier`, `cypher`, `composer`, `extraction`,
`language_detect`, `judge`, `embeddings`) to provider-prefixed model ids, with retries, a
fallback chain on provider outage, per-call cost accounting and Langfuse tracing. It must
preserve **token streaming** — `composer.compose_stream` is the one path where fake-streaming
has regressed twice.

Everything with a module-level client migrates onto it: the retriever's `llm_utils`, the
search service's `extraction`, `laiive_shared.language`, and the pusher's three clients (whose
paths are patched by name in `services/pusher/tests/conftest.py` — the patch list moves with
them).

Role-to-model choices then come out of the eval suites' `--models` sweep and a cost/quality
table, not a hunch.

## 5. Retrieval accuracy

The current shape and what is wrong with it, in `services/retriever/agent/`:

- `pipeline.run_turn` runs sub-queries **serially** and fuses them by uid dedup in plan order.
  → Run them in parallel (a thread pool, never `async def` around blocking work) and fuse with
  reciprocal rank fusion over a real scoring function: time proximity, distance, geocode
  precision, text and vector score.
- `router.route` picks **one** leg per sub-query, and `free_text` beats structured constraints,
  so "intimate jazz in Madrid on Friday" goes vector-only. → A plan carries several legs and
  their results fuse. That is what makes the search hybrid rather than a switch statement.
- **There is no full-text index.** Adding one over event name/description and artist names
  gives exact-ish matching a leg of its own, instead of `CONTAINS` on `name_norm`.
- `QueryBuilderTool` is a single zero-shot call behind a regex guard, and
  `flexible_rows_to_cards` exists only to survive its arbitrary aliases. → Schema-aware
  few-shot, `EXPLAIN`-validate before execute, one repair attempt on error-or-zero-rows, enforce
  the standard return shape (which lets `flexible_rows_to_cards` be deleted), cache by
  normalised question shape.
- Empty-result recovery is one fallback (the named-place bbox). → A measured ladder: drop the
  weakest constraint, widen the date window, widen the radius — each rung reported to the
  composer through the `Outcome.note` plumbing that already exists.

No change here ships without a recall or precision number from phase 3.

## 6. Guardrails, semantic cache, language routing, voice

**Guardrails.** `agent/tools/safety_guard.py` moves from regex to an `EXPLAIN`-based read-only
proof; per-request cost and row ceilings; and an output guard — the composer may not name an
event that is not in ground truth. The write-path gates get eval coverage.

**Semantic cache.** Three layers on the existing Redis (`RedisGeocodeStore` is the pattern):
an embedding cache; a classifier cache keyed by normalised message, history hash, date bucket
and location bucket; and a turn-level cache that reuses **cards** on a constraint-fingerprint
plus similarity hit while always recomposing the prose. TTLs keyed to event freshness — never
serve stale prose about an event that moved.

**Language routing.** Detection already works. What is missing is a measured per-language model
choice (Catalan is the hard case), locale-aware date and price formatting on the cards, and a
per-language slice in every suite.

**Voice tuner.** The composer persona comes out of the prompt string into a versioned voice
spec — tone axes and per-language exemplars — so tone becomes a config with an A/B harness and
a judge rubric behind it, not a paragraph edited by feel.

## 7. Ingestion quality and the self-improvement loop

**Extraction optimizer** (`services/search/agent/extraction.py`): today one prompt, truncation
at `page_max_chars`, and a fallback model only when the JSON will not parse. In the order they
pay off — **JSON-LD `schema.org/Event` parsing before the LLM** (most venue pages carry it, and
it is free and exact), chunking instead of truncation, schema-enforced structured output,
per-domain adapters for the recurring listing sites, a confidence score. Measured on a
frozen-page set with hand-labelled events.

**Prefect routines**: per-city schedules and priorities, report retention, and alerting when
sweep quality drops against the recorded baselines.

**The loop**: traces + response capture + user feedback → filtered candidate cases → a nightly
eval run → a report that opens an issue when a metric regresses and proposes prompt or model
candidates, which ship only through the offline gate plus a human approve.

**Repo analysis skills** in `.claude/skills/`, alongside `handoff`, `run-stack` and
`verify-retriever`: `analyze-turn` (one query through the pipeline, printing classification,
plan, Cypher, rows, cards and cost), `eval-report`, `sweep-quality`.

---

Phases 6 and 7 can interleave; the semantic cache and the extraction optimizer do not depend on
phase 5. Everything lands as `<type>/<kebab-desc>` branches off `main`, one phase per branch.
