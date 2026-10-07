---
status: active
step: supply
next: deploy search, run one Bergamo sweep, read the dry-run report
---
# Bergamo sweep

#127 merged. Expect about 56 upcoming candidates.

## Steps
- [ ] Deploy search. Run one Bergamo sweep. Read the dry-run report.
- [ ] Eppen page 2 "carries almost no dates": Tavily stripped dates on 3 of 4 fetches,
      about 37 candidates lost. Decide retry or drop.

Rejected designs are recorded in `services/search/agent/extraction.py`. Do not reuse them.
