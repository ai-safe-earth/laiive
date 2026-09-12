# pusher evals — the dedup review set

`dedup_review.csv` is 52 labelled conversations probing how the pusher handles
near-duplicate events: name variations (case, diacritics, band order, separators,
typos, nameless flyers), date/time variance (same day different hour, midnight
boundary, weekday contradictions), venue variance (typed vs picked, cross-city
same-name venues), ownership states (unowned swept, own event, somebody else's)
and full conversation shapes (walks, corrections, double pastes, outages).

Born from the live test of 2026-09-12: three publish attempts against one swept
listing produced two silent duplicates and zero adoptions, because today's dedup
key is exact `name_norm` + venue + calendar day. Under these 52 realistic cases,
today's code silently duplicates in 21 of them.

## The columns

| column | meaning |
|---|---|
| `graph_state` | what already exists in the graph before the conversation |
| `conversation` | the turns, `\|\|`-separated (`user:` / `assistant:` / `tool:`) |
| `expected_tools` | the tool/endpoint sequence the conversation should drive |
| `current_outcome` | what **today's code does** — derived from the writer's real rules and independently re-verified per case |
| `current_reason` | the rule that produces that outcome |
| `expected_outcome` | what **should** happen (the multi-signal dedup spec: surface the candidate, confirm same → adopt/edit, different → differentiate) |
| `expected_reply` | gist of what the user should be told |
| `notes` | verifier corrections / repairs, where any |
| `verdict` | **yours** — OK if `expected_outcome`/`expected_reply` are right, KO otherwise |
| `should_instead` | **yours** — when KO, what should happen instead |

`current_outcome` vocabulary: `adopted`, `created_ok` (genuinely new, correct),
`created_duplicate` (a near-duplicate lands silently — the failure mode),
`duplicate_409`, `clarify_first`, `invalid_422`, `error_503`.

## How to review

Open the CSV in Excel (semicolon-delimited, UTF-8 BOM — it opens straight into
columns on a European locale). Go case by case and fill only the last two
columns. `current_outcome` is descriptive, not up for review — it says what the
code does today, verified; the review question is always whether
`expected_outcome` is the product you want.

## What this becomes

After the review pass, the corrected set graduates to
`datasets/dedup/test_cases.json` in the retriever-evals style
(`services/retriever/evals/README.md`) and becomes the acceptance suite for
roadmap Phase 4 (multi-signal dedup, suggest-at-entry) and the Phase 3 edit
path (`OWN-*` cases). Until then this CSV is the source of truth; do not wire
tests to it directly.
