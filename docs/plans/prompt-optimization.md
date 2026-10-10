---
status: todo
step: self-improvement
next: needs the owner's OK to add the dspy dependency
---
# Prompt optimisation with DSPy

Owner, 2026-10-10: the prompts (classifier, composer, query builder) should be
tuned with DSPy, against the eval datasets, instead of by hand.

## Open
- Roadmap step: owner's call (model-routing, guardrails or self-improvement).
- DSPy is a new dependency: the owner's OK before it is added.
- The datasets are the training set and the gate: a tuned prompt ships only if it
  passes the offline suites, the same as a hand edit.
