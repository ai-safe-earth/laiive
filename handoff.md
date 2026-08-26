# HANDOFF - laiive (updated 2026-08-26)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Evolution plan
(six areas, A-G, approved 2026-08-25): `~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md`.

**laiive is live at https://laiive.com**, `v0.2.0` shipped 2026-08-25. `main` == `develop`,
no open PRs, tag back-merged. Phases A/B/C (#69/#70/#71) and the release (#76) are all in.

## Uncommitted on `feat/source-prospecting` (local only; branch == origin/develop)

- `supabase/migrations/20260825000017_search_source_prospecting.sql` — `search_sources`
  gains cities, agenda_urls, venues_covered, fields_filled, vouched_by/at (GIN on cities);
  `search_reports` kind check widened. 16 is reserved for phase D, so phase G's
  review-signal columns move to 18. Its measurement: ranking a source by `candidates_new`
  puts songkick 24 bare listings over ecodibergamo 9 complete ones; `fields_filled` stops it.
- `flows/serve.py` — schedules moved: bergamo Wed 04:00, torino Wed 07:00, backfill Mon only.
- `.claude/` tooling, `CLAUDE.md`, `assets/Laiive_Pro_Walkthrough_hq.mp4`.

## Eval audit, 2026-08-26 — analysis only, no code changed

Report: https://claude.ai/code/artifact/a4c78e31-b905-457a-ba20-c9252372c9d7 (13 findings).

- **Answers are never stored.** `gateway/src/logging.ts` captures the request side only —
  123 chat turns, 111 payloads, 6 users, zero labelable outputs.
- **The two halves cannot be joined.** Gateway injects `x-request-id` (`proxy.ts:23`); the
  retriever ignores it and mints `uuid4()` (`api.py:363`). Both fixes land together.
- Capture belongs retriever-side: `_generate()`'s `finally:` block already holds the whole
  `TurnResult`. A gateway tee would touch the streaming path that has regressed twice.
- The 12 eval cases on disk are imported by nothing and quarantined from lint; the 7 safety
  ones are deterministic and can gate CI in half a day.
- Roadmap §3 builds the harness and judge rubric before the corpus they should come from.
  Corrected: capture → cheap label → wire existing cases → error analysis → judges → harness.
- `learning.py` ranks query phrasings on `candidates_new / runs` — novelty, not correctness.
  Migration 17 fixes this for *sources*; *phrasings* still see no human verdict.

## Open

- `flows/serve.py` still not served, so no schedule fires. Sweep backlog grew to 17 reports
  in `dry_run` (11 approved, 9 done), zero ever dismissed.
- Redirect allow-list unread (`DEPLOY.md` 5 step 2). OG card bare. `lucide-react` unused.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-08-26",
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
      "status": "planned",
      "start": null,
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
      "text": "17 sweep reports sit in dry_run (11 approved, 9 done) - the backlog grew from about 5 on 2026-08-25. Nothing reaches the graph until they are approved, and zero reports have ever been dismissed, so either every sweep was clean or the reject path has friction the approve path does not",
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
      "text": "prefect.yaml git-clones main of ai-safe-earth/laiive at run time and needs a github-laiive-pat Secret block; moot under the local serve() shape, relevant again only when the managed pool is revived",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-14"
    }
  ],
  "nextSteps": [
    {
      "title": "Commit and PR the source-prospecting work sitting uncommitted on feat/source-prospecting: migration 20260825000017 (search_sources gains cities, agenda_urls, venues_covered, fields_filled, vouched_by/at; search_reports kind check widened) plus the flows/serve.py schedule moves. The branch is local only and identical to origin/develop",
      "est": 2,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Eval phase 0 - capture the answer and give it a joinable id. Read x-request-id in retriever chat_stream and chat instead of minting uuid4 (api.py:363), add an eval_records migration (final_text, card_uids, cyphers, query_type, moment, retrieval_notes, row_count, latency_ms, errors; service-role RLS), and write the record from the existing finally: block in _generate(). Keep the write off the yield path or the done frame is delayed",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Eval phase 2 - make the 12 quarantined cases run. A parametrized loader in services/retriever/tests, hard assertions for the 7 deterministic safety cases, should_not_contain kept as a real gate and expected_patterns xfailed until execute-and-compare replaces regex, re-check the 5 cypher cases against today prompt, lift the pre-commit exclude, flip langfuse_enabled default to False (config.py:37 says True while .example.env says false), rewrite evals/README.md",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Eval phase 1 - a thumbs-down with an optional reason on the assistant message, a turn_feedback table and a POST /api/chat/feedback route on the gateway. No thumbs-up: the down is the informative event. Depends on nothing and compounds while the rest is built",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Phase D (orgs + claims): migration 20260825000016 (claim status/revocation, entity_edits audit, create_organization RPC with pro floor, user_may_edit helper), gateway-native /api/orgs + /api/claims + /api/publish wrapper, /pro/org screen. Full design in the approved plan file",
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
      "title": "Phases F/G (discovery): frozen-page eval set first, JSON-LD before the LLM (verify Tavily raw_content keeps ld+json), chunking over truncation, Torino seeds + credit ceiling, review-signal columns + human-gated hint drafting (migration 18 now that 17 is taken)",
      "est": 4,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Verify the Supabase redirect allow-list carries <origin>/** for laiive.com, www, laiive.pages.dev and the develop alias, and that Site URL is https://laiive.com - read it, do not infer it (DEPLOY.md section 5 step 2)",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {
      "date": "2026-08-24",
      "model": "opus-5",
      "person": "oscar",
      "credits": null,
      "hours": null
    },
    {
      "date": "2026-08-25",
      "model": "fable-5",
      "person": "oscar",
      "credits": null,
      "hours": null
    },
    {
      "date": "2026-08-26",
      "model": "opus-5",
      "person": "oscar",
      "credits": null,
      "hours": null
    }
  ]
}
```
