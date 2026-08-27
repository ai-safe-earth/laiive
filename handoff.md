# HANDOFF - laiive (updated 2026-08-27)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Evolution plan
(six areas, A-G, approved 2026-08-25): `~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md`.

**laiive is live at https://laiive.com**, `v0.2.0` shipped 2026-08-25. PR #79
(over-engineering audit) merged into `develop`. Nothing deployed since v0.2.0.

## Open PR

**#80 `feat/eval-records` -> develop, 11 commits.** Eval phases 0+1: retriever adopts the
gateway `x-request-id` and writes `eval_records` (migration 18); thumbs-down ->
`turn_feedback` via a native gateway route (migration 19); thumbs-up as an inert stored
label (migration 21, **unapplied**; retention and the phase-3 query filter to downs;
apply 21 before deploying the gateway or every feedback post 502s); `make dev` one-terminal stack
plus the two bugs it uncovered (Makefile env whitespace, loguru `exc_info` silencing SSE
errors); feedback route excluded from conversation logging; telemetry retention (migration
20, **unapplied**); `docs/explain/` + the `explain-doc` skill; programme-wide status doc
`docs/explain/program-status-2026-08.html` (whole-plan status, evidence-checked).

## Eval state

Phases 0 (capture) and 1 (cheap label) built; migrations 18+19 **applied** (verified
2026-08-27), corpus accumulating on its own. One `request_id` joins `conversation_logs`
(request), `eval_records` (answer), `turn_feedback` (label). Deep-dive with schemas and
decisions: `docs/explain/eval-phases-0-1.html`. Corrected order holds: capture -> cheap
label -> wire existing cases (phase 2, next) -> error analysis -> judges.

## Open

- Migration `20260827000020` (nightly pg_cron prune of the two telemetry tables past 90
  days, turn_feedback-referenced turns exempt) awaits owner-run `supabase db push`;
  confirm the 90-day window is the wanted policy while pushing.
- Phase D/G migrations must renumber (D -> 22, G -> 23; rating took 21): the plan file's
  20260825000016/17 slots now sort before applied history and `db push` skips them.
- `flows/serve.py` still not served, so no schedule fires. 17 reports in `dry_run`, zero
  ever dismissed. Redirect allow-list unread (`DEPLOY.md` 5 step 2). OG card bare.
- `assets/Laiive_Pro_Walkthrough_hq.mp4` (7.4 MB) untracked - needs a home decision.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-08-27",
  "deadline": null,
  "people": [
    "oscar"
  ],
  "plans": [
    {
      "name": "refactor",
      "path": "docs/refactor/",
      "status": "done"
    },
    {
      "name": "roadmap",
      "path": "docs/roadmap/",
      "status": "active"
    }
  ],
  "phases": [
    {
      "name": "Restyle - new visual direction",
      "status": "active",
      "start": "2026-08-19",
      "end": null,
      "plan": "roadmap"
    },
    {
      "name": "Evolution - six areas",
      "status": "active",
      "start": "2026-08-25",
      "end": null,
      "plan": "roadmap"
    },
    {
      "name": "Ingestion + self-improvement",
      "status": "active",
      "start": "2026-08-22",
      "end": null,
      "plan": "roadmap"
    },
    {
      "name": "Evals + observability",
      "status": "active",
      "start": "2026-08-26",
      "end": null,
      "plan": "roadmap"
    },
    {
      "name": "Multi-provider model routing",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap"
    },
    {
      "name": "Retrieval accuracy",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap"
    },
    {
      "name": "Guardrails, cache, language, voice",
      "status": "planned",
      "start": null,
      "end": null,
      "plan": "roadmap"
    }
  ],
  "blockers": [
    {
      "text": "The Supabase redirect allow-list is unverified and gates Google sign-in in production: with bare origins rather than <origin>/** patterns the return to /auth/callback is silently dropped for the Site URL. Read it with GET /v1/projects/<ref>/config/auth",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-08-21"
    },
    {
      "text": "17 sweep reports sit in dry_run (11 approved, 9 done) - the backlog grew from about 5 on 2026-08-25. Nothing reaches the graph until they are approved, and zero reports have ever been dismissed, so either every sweep was clean or the reject path has friction the approve path does not. Triage before building G: its approval-ratio learning trains one-sided on an approve-only corpus",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-08-23"
    },
    {
      "text": "flows/serve.py is not running, so no schedule fires. Every sweep so far was triggered by hand; the admin dashboard shows this as a reasoned scheduler verdict instead of a silent next-run time",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-23"
    },
    {
      "text": "The Aura free instance auto-pauses and its DNS record disappears while paused; on resume reads work but writes fail with 'No write service currently available'. Cost three aborted repair runs before it settled",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-18"
    },
    {
      "text": "prefect.yaml git-clones main of ai-safe-earth/laiive at run time and needs a github-laiive-pat Secret block; moot under the local serve() shape, relevant again only when the managed pool is revived. Kept in the repo deliberately - PR #79 considered deleting it and held",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-14"
    }
  ],
  "nextSteps": [
    {
      "title": "Apply migrations 20260827000020 + 21 with supabase db push - owner-run, and BEFORE the next gateway deploy (the gateway now sends rating on every feedback insert); confirm the 90-day retention window is the wanted policy while pushing",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Eval phase 2 - make the 12 quarantined cases run. A parametrized loader in services/retriever/tests, hard assertions for the 7 deterministic safety cases, should_not_contain kept as a real gate and expected_patterns xfailed until execute-and-compare replaces regex, re-check the 5 cypher cases against today prompt, lift the pre-commit exclude, flip langfuse_enabled default to False (config.py:42 says True while .example.env says false), rewrite evals/README.md",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Eval phase 3 - error analysis: read the corpus weekly (downs joined to conversation and answer, the query in docs/explain/eval-phases-0-1.html section 5) and name the failure modes by hand; the judge rubric comes from these labels, not before them",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Phase D (orgs + claims): migration renumbered to 20260827000022 (the plan file's 20260825000016 now sorts before applied history and db push would skip it; 21 is the feedback rating) - claim status/revocation, entity_edits audit, create_organization RPC with pro floor, user_may_edit helper; gateway-native /api/orgs + /api/claims + /api/publish wrapper, /pro/org screen. Full design in the approved plan file",
      "est": 3,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Phase E (edits + verification): first update functions in laiive_shared.neo4j_writer, pusher edit routes behind gateway authz, /admin claims queue with verify/revoke, the card flips on the claim stamp, CTA deep-links to /pro/claim",
      "est": 3,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Phases F/G (discovery): frozen-page eval set first, JSON-LD before the LLM (verify Tavily raw_content keeps ld+json), chunking over truncation, Torino seeds + credit ceiling, review-signal columns + human-gated hint drafting (migration 23 now that rating takes 21 and D 22). Migration 17's columns are read by no service until this lands, and both approve paths must gate on kind first",
      "est": 4,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Verify the Supabase redirect allow-list carries <origin>/** for laiive.com, www, laiive.pages.dev and the develop alias, and that Site URL is https://laiive.com - read it, do not infer it (DEPLOY.md section 5 step 2). Closing this closes the Restyle phase",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {
      "date": "2026-08-26",
      "model": "opus-5",
      "person": "oscar",
      "credits": null,
      "hours": null
    },
    {
      "date": "2026-08-27",
      "model": "fable-5",
      "person": "oscar",
      "credits": null,
      "hours": null
    },
    {
      "date": "2026-08-27",
      "model": "fable-5",
      "person": "oscar",
      "credits": null,
      "hours": null
    }
  ]
}
```
