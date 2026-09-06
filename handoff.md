# HANDOFF - laiive (updated 2026-09-06)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Evolution plan
(six areas, A-G, approved 2026-08-25): `~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md`.

**`v0.3.0` is live at https://laiive.com** (2026-09-06, 79 commits, first release since v0.2.0
on 2026-08-25). `develop` and `main` are in sync, no open PRs, working tree clean. The
undeployed-backlog risk that sat here for twelve days is gone.

## Verified in production after the deploy

`POST /api/publish` returns 401 rather than 404 — the toast that broke the develop preview.
The live SPA bundle carries `agency`, `freelance` and `status-review`, so the new code is served
and the schema it needs is applied. A real Spanish chat query streams classifying -> searching ->
events.result -> 32 token deltas. Migrations 20-23 all applied, zero pending;
`organization_members.relation` is selectable and `kind=eq.agency` is accepted. Retriever secrets
went 10 -> 12, so `eval_records` writes instead of returning early on an empty URL. Aura is up
(189 events, 96 venues, 159 artists, 114 future). All four Fly apps deployed and healthy.

## What shipped unproven

The search learning fix is deployed but **no sweep has run since**, so that `search_sources` and
`search_queries` actually fill is still unobserved - and every sweep before today recorded
nothing, so the ranking has no history to stand on. Phase D adoption: six probe checks never ran.
`start_at_claim` has still never met a real model. Phase C did not fully ship -
`EventCardView.tsx:120` computes `verified` from source alone, so `claimed` arrives on the wire
(`executor.py:38`) and is never rendered; one line, belongs to E.

## Traps confirmed this session

`cz` writes a **lightweight** tag, so `git push --follow-tags` pushes nothing - `v0.3.0` needed an
explicit `git push origin v0.3.0`. v0.2.0 is on the remote, so this has not bitten before, but
`CONTRIBUTING.md` step 4 still reads as if one command does both. Separately: `develop` was the
head branch of the release PR and the repo deletes head branches on merge - the same mechanic that
ate `main` in PR #66. Branch protection is what saved it, not the workflow.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-09-06",
  "deadline": null,
  "people": ["oscar"],
  "plans": [
    {"name": "refactor", "path": "docs/refactor/", "status": "done"},
    {"name": "roadmap", "path": "docs/roadmap/", "status": "active"}
  ],
  "phases": [
    {"name": "Restyle - new visual direction", "status": "active", "start": "2026-08-19", "end": null, "plan": "roadmap"},
    {"name": "Evolution - six areas", "status": "active", "start": "2026-08-25", "end": null, "plan": "roadmap"},
    {"name": "Ingestion + self-improvement", "status": "active", "start": "2026-08-22", "end": null, "plan": "roadmap"},
    {"name": "Evals + observability", "status": "active", "start": "2026-08-26", "end": null, "plan": "roadmap"},
    {"name": "Multi-provider model routing", "status": "planned", "start": null, "end": null, "plan": "roadmap"},
    {"name": "Retrieval accuracy", "status": "planned", "start": null, "end": null, "plan": "roadmap"},
    {"name": "Guardrails, cache, language, voice", "status": "planned", "start": null, "end": null, "plan": "roadmap"}
  ],
  "blockers": [
    {
      "text": "Two npm advisories on the gateway lockfile, both unassessed: fast-uri (high) and fastify (medium), services/gateway/package-lock.json. GitHub reports 8 high and 2 medium but that is the same two alerts counted across branches - gh api dependabot/alerts deduplicates to two packages. Neither has been looked at, and the gateway is the only published surface, so they are worth reading before anything else on the security side",
      "severity": "high",
      "owner": "oscar",
      "since": "2026-09-06"
    },
    {
      "text": "The search learning tables were empty until today and are still unproven. learning.py sent the literal string now() as both timestamps, PostgREST passed it as JSON, Postgres refused the cast, _upsert raised, and because record_sources runs first neither record_queries nor promote_queries ever ran - discovery.py:367 caught it and logged one warning. Fixed and deployed in v0.3.0 but not retroactively, and no sweep has run since the fix, so that the tables now fill is unobserved. One sweep then a row count settles it. Phase G's approval-ratio learning must not assume history that does not exist",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-06"
    },
    {
      "text": "start_at_claim, which the whole weekday check depends on, has never met a real model: every pusher test mocks OpenAI, so whether it obeys the v4 prompt rule is unknown. A missing weekday claim is silent by design and covered by test_no_weekday_claimed_is_silent, so nothing would report it broken; any real loss would be upstream of checks.py and no such path was found. One real flyer settles it, and Aura is up now, so nothing blocks it",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-05"
    },
    {
      "text": "There is no staging backend. Pages builds an SPA preview per branch but VITE_API_URL is one project-level variable pointing at the single production gateway, so any frontend change on develop needing a new route 404s on the preview until a deploy. Pages supports separate Preview and Production variables; the fix costs a second gateway, pusher and retriever on Fly plus a decision about whether preview publishes write into the production graph",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-03"
    },
    {
      "text": "The writer's query contract is hand-copied into three fake sessions (shared, pusher, search conftests). Changing a RETURN unhooks them silently and the fake then answers the write with an empty row - it broke PR #90's search job and again during the adoption work. Now matched on column names rather than whole RETURN lines: sturdier, not fixed. They have also drifted - search's copy returns params[venue_uid] where pusher and shared return params[picked_uid], so search's fake cannot exercise venue adoption. Collapsing them into services/shared/laiive_shared/testing.py is about 1.5h and net -100 lines",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-02"
    },
    {
      "text": "The Supabase redirect allow-list is unverified and gates Google sign-in in production: with bare origins rather than <origin>/** patterns the return to /auth/callback is silently dropped for the Site URL. Read it with GET /v1/projects/<ref>/config/auth",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-08-21"
    },
    {
      "text": "flows/serve.py is not running, so no schedule fires. Every sweep so far was triggered by hand; the admin dashboard shows this as a reasoned scheduler verdict instead of a silent next-run time. When it first runs, the stale backfill-nightly deployment in Prefect Cloud must be deleted by hand",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-08-23"
    }
  ],
  "nextSteps": [
    {
      "title": "Read the two npm advisories on the gateway lockfile - fast-uri (high) and fastify (medium) - and decide whether a bump is a one-line lockfile change or a fastify major. gh api repos/ai-safe-earth/laiive/dependabot/alerts is the deduplicated view; the GitHub UI count of 8 high is the same alerts across branches. The gateway is the only published surface, so this is the one security item ahead of feature work",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Everything that was queued behind Aura, now unblocked, in one sitting: re-run the adoption probe for the six checks that never ran (created_at untouched, ticket_url and source_url surviving, no duplicate, artist attached, second sweep refused, other promoter refused), delete the orphan Laiive Probe Artist 8f9f909 node, and put one real flyer through the local stack - a listing whose weekday contradicts its date, at a venue with a swept dry_run event, which exercises start_at_claim and adoption against a real graph in one pass. make dev GATEWAY_PORT=8100, because :8000 is the A02_VaiVia squatter",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Run one sweep against the deployed search service and then count rows in search_sources and search_queries. Until that returns non-zero, the now() fix is only believed, not observed - and it is the precondition for phase G being worth starting at all",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Verify the Supabase redirect allow-list carries <origin>/** for laiive.com, www, laiive.pages.dev and the develop alias, and that Site URL is https://laiive.com - read it, do not infer it (DEPLOY.md section 5 step 2). Closing this closes the Restyle phase",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    },
    {
      "title": "Triage the 17 dry_run sweep reports before building G. Zero have ever been dismissed, so either every sweep was clean or the reject path has friction the approve path does not - and G's approval-ratio learning would train one-sided on an approve-only corpus. Read the reject path in services/search/agent/api.py alongside the reports themselves",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Phase E (edits + verification): update functions in laiive_shared.neo4j_writer, pusher edit routes behind gateway authz using the user_may_edit helper migration 22 already ships, /admin claims queue with verify/revoke, the card flips on the claim stamp. Near-zero today - entity_edits and user_may_edit exist with zero callers, e.claim_verified is read by executor.py and written by nothing, neo4j_writer.py has no update path at all. The smallest useful slice is update_venue plus PATCH /api/venues/:uid writing entity_edits, and it carries the one-line Phase C fix in EventCardView",
      "est": 3,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Eval phase 3 - error analysis: read the corpus weekly (downs joined to conversation and answer, the query in docs/explain/eval-phases-0-1.html section 5) and name the failure modes by hand; the judge rubric comes from these labels, not before them. eval_records only started writing today, so the corpus begins now",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Invitations - the phase D2 tail. /pro/org's roster is read-only and says so; organization_members has no invite path, so an org is one person until this lands. Other seats show a UUID because there is no profiles policy for reading another member's name - it comes with this",
      "est": 2,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {"date": "2026-09-05", "model": "fable-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-06", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-06", "model": "opus-5", "person": "oscar", "credits": null, "hours": null}
  ]
}
```
