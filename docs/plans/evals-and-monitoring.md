---
status: active
step: evals
next: fix the 6 classifier gaps xfailed in services/retriever/evals/README.md
---
# Evals and monitoring (program phase 3)

Evals come before optimisation: accuracy, cost and voice work are claims until a suite
can tell whether a change helped.

## Done
- Tracing on Arize Phoenix (`laiive_shared/tracing.py`): one `turn` span per request with
  `moderate -> classify -> route -> execute -> compose`, carrying the gateway request id.
  `run_turn` is a sync generator, so parenting is passed explicitly (`stage`/`start_child`).
- Response capture in `eval_records` (retriever) and `push_records` (pusher). The gateway
  logs requests only, on purpose.
- Suites: classifier (20 cases, weekly), cypher (execute-and-compare, weekly), retrieval
  (14 cases on a throwaway Neo4j, every push), answer quality (10 cases, weekly), safety (7).
  Routing suite dropped: `tests/test_router.py` covers it.

## Steps
- [x] Before deploy: `supabase db push` (table `push_records` missing live); pusher needs
      `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` Fly secrets. Merge PR #128.
      Done 2026-10-08: migration pushed, secrets set (digests match the retriever's),
      all four services deployed, shipped in v0.7.0.
- [x] PR the local branch `chore/one-fake-neo4j-session` (`88d8fad`), stacked on #128.
      Rebased onto develop 2026-10-08 (now `9193382`, clean); shared 224, pusher 91,
      search 142 pass.
- [ ] Fix the 6 classifier gaps xfailed in `services/retriever/evals/README.md`. Worst two:
      "gigs near me" with no location, and "find me something". Both should ask, not
      answer "nothing found".
- [ ] Composer names the event and act when there is one result (the prompt has no rule for it).
- [ ] `python -m evals.run --models a,b` CLI: deferred to model-routing.

## Baselines (live graph, 2026-08-18)
- 35 venues stamped `venue`, none beyond the 25 km city guard.
- Genre reachability 55 of 57 events. 48 fake "free" prices cleared (lossy), 30 fake
  midnight starts marked date-only. No duplicate events; duplication is in venues.
