---
status: todo
step: guardrails
next: part 1, EXPLAIN-based read-only proof in safety_guard.py
---
# Guardrails, semantic cache, language routing, voice (program phase 6)

Four parts, in sequence.

## 1. Guardrails
- [ ] `agent/tools/safety_guard.py`: regex -> `EXPLAIN`-based read-only proof.
- [ ] Per-request cost and row ceilings.
- [ ] Output guard: the composer may not name an event that is not in ground truth.
- [ ] Eval coverage for the write-path gates.

## 2. Semantic cache (on the existing Redis; `RedisGeocodeStore` is the pattern)
- [ ] Embedding cache.
- [ ] Classifier cache keyed by normalised message, history hash, date and location bucket.
- [ ] Turn cache reusing cards on a constraint fingerprint + similarity; always recompose the
      prose. TTLs tied to event freshness.

## 3. Language routing
- [ ] Measured per-language model choice (Catalan is the hard case).
- [ ] Locale-aware date and price formatting on cards.
- [ ] A per-language slice in every suite.

## 4. Voice tuner
- [ ] Composer persona out of the prompt into a versioned voice spec (tone axes,
      per-language exemplars), with an A/B harness and a judge rubric.
