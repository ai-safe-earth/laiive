---
status: blocked
step: supply
next: owner reviews services/pusher/evals/dedup_review.csv
---
# Dedup (pro settings phase 4)

## Steps
- [ ] Owner fills `verdict` + `should_instead` for the 52 cases in
      `services/pusher/evals/dedup_review.csv`.
- [ ] Convert to `datasets/dedup/test_cases.json`, the acceptance suite.
- [ ] Fix adoption through chat: nameless drafts get derived names, so the exact
      `name_norm` key misses.
