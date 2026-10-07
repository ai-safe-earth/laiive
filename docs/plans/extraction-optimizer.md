---
status: todo
step: supply
next: parse JSON-LD schema.org/Event before calling the LLM
---
# Extraction optimizer (program phase 7)

`services/search/agent/extraction.py` today: one prompt, truncation at `page_max_chars`,
fallback model only when the JSON fails to parse. In payoff order:

- [ ] JSON-LD `schema.org/Event` parsing before the LLM (free and exact).
- [ ] Chunking instead of truncation.
- [ ] Schema-enforced structured output.
- [ ] Per-domain adapters for recurring listing sites.
- [ ] Confidence score.

Measure on a frozen-page set with hand-labelled events. Check drafts against page-derived
truth, not draft counts.
