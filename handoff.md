# HANDOFF - laiive (updated 2026-09-08)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Evolution plan
(six areas, A-G, approved 2026-08-25): `~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md`.
Pro settings plan (five phases, approved 2026-09-08):
`~/.claude/plans/pro-user-settings-is-optimized-metcalfe.md`.

**`v0.3.0` is live at https://laiive.com** (2026-09-06, 79 commits). No open PRs, tree clean,
zero pending migrations. `develop` is **9 commits ahead of `main`** — pro settings phase 1,
merged as #98 and not deployed. Nothing gates it; only the SPA changed, so the Fly deploys
are no-ops and Cloudflare builds `main` on the release merge.

## Pro settings — phase 1 of 5 done (#98)

`/pro/org` is three labelled bands instead of six flat panels: what the organisation **is**
(with your seat and the other members inside it), what it **manages**, what it has
**published** (last, opening on the recent five). `/account` is personal plus a list of every
organisation and your seat — it read `orgs[0]` and hardcoded it, so a second org was silently
invisible. Initials in the header, org switcher as a tab strip.

Migration 25 applied: an org-scoped SELECT policy on `profiles` through a `shares_org_with`
definer, so the roster shows names not uuids. First policy here to widen SELECT beyond the
row owner; check 11 forces RLS and asserts both directions. Eleven of eleven, and that run
was also check 10's first ever.

**Phases 2-5, in the plan file:** invitations (~2d, cheapest — `organization_invitations`
already exists complete and #98 paid its dependency), entity edit path (~4-5d, this **is**
roadmap Phase E), dedup (~4d), onboarding wizard (~2d).

## Shipped but barely exercised

Phase D adoption: six probe checks never ran. `start_at_claim` has still never met a real
model. The `now()` fix is deployed but no sweep has run since, so the learning tables filling
is unobserved. Phase C did not fully ship — `EventCardView.tsx:120` computes `verified` from
source alone, so `claimed` arrives on the wire and is never rendered; one line, belongs with
Phase E. Evals: 0-2 merged, phase 3 kit in #86, and the corpus only began filling 2026-09-06.

Open: two npm advisories on the gateway lockfile, unread. `flows/serve.py` not served; 17
reports in `dry_run`, zero dismissed; Supabase redirect allow-list unverified.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-09-08",
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
      "text": "Two npm advisories on the gateway lockfile, both unassessed: fast-uri (high) and fastify (medium), services/gateway/package-lock.json. The GitHub UI reports 8 high and 2 medium, which is the same two alerts counted across branches - gh api repos/ai-safe-earth/laiive/dependabot/alerts deduplicates to two packages. Neither has been looked at and the gateway is the only published surface, so this is the one security item ahead of feature work",
      "severity": "high",
      "owner": "oscar",
      "since": "2026-09-06"
    },
    {
      "text": "develop is 9 commits ahead of main and undeployed - pro settings phase 1, merged as #98 on 2026-09-08. Nothing gates it and migration 25 is already applied, so unlike the 60-commit backlog there is no ordering hazard: only frontend changed, the four Fly deploys would be no-ops, and Cloudflare builds main on the release merge. It is here because twelve days of undeployed work was the last top risk and the pattern repeats quietly",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-08"
    },
    {
      "text": "The search learning tables were empty until 2026-09-06 and are still unproven. learning.py sent the literal string now() as both timestamps, PostgREST passed it as JSON, Postgres refused the cast, _upsert raised, and because record_sources runs first neither record_queries nor promote_queries ever ran - discovery.py:367 caught it and logged one warning. Fixed and deployed in v0.3.0 but not retroactively, and no sweep has run since the fix, so that the tables now fill is unobserved. One sweep then a row count settles it. Phase G must not assume history that does not exist",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-06"
    },
    {
      "text": "start_at_claim, which the whole weekday check depends on, has never met a real model: every pusher test mocks OpenAI, so whether it obeys the v4 prompt rule is unknown. A missing weekday claim is silent by design and covered by test_no_weekday_claimed_is_silent, so nothing would report it broken; any real loss would be upstream of checks.py and no such path was found. One real flyer settles it, and Aura is up, so nothing blocks it",
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
      "title": "Read the two npm advisories on the gateway lockfile - fast-uri (high) and fastify (medium) - and decide whether a bump is a one-line lockfile change or a fastify major. gh api repos/ai-safe-earth/laiive/dependabot/alerts is the deduplicated view; the UI count of 8 high is the same alerts across branches. The gateway is the only published surface, so this is the one security item ahead of feature work",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Ship pro settings phase 1: release PR develop -> main titled release: v0.3.1, merge as a merge commit, make release on main, push with --follow-tags AND then git push origin <tag> because cz writes a lightweight tag that --follow-tags ignores, then merge main back into develop LOCALLY. Only the SPA changed, so the Fly deploys are no-ops and Cloudflare builds main on the merge. Then check /pro/org shows names rather than uuids, which is what migration 25 bought",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Everything queued behind Aura, in one sitting: re-run the adoption probe for the six checks that never ran (created_at untouched, ticket_url and source_url surviving, no duplicate, artist attached, second sweep refused, other promoter refused), delete the orphan Laiive Probe Artist 8f9f909 node, and put one real flyer through the local stack - a listing whose weekday contradicts its date, at a venue with a swept dry_run event, which exercises start_at_claim and adoption against a real graph in one pass. make dev GATEWAY_PORT=8100, because :8000 is the A02_VaiVia squatter",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Run one sweep against the deployed search service, then count rows in search_sources and search_queries. Until that returns non-zero the now() fix is believed rather than observed, and it is the precondition for phase G being worth starting at all",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "Pro settings phase 2 - invitations. The cheapest of the four remaining and its dependency is paid: organization_invitations already exists complete (token hash, expires_at, accepted_at, partial unique index on pending invites per email, a SELECT policy) with zero code referencing it, and #98 shipped the profiles policy the roster needed. Write the invite, accept and revoke routes, then replace the rosterNote line with a real control - phase 1 deliberately rendered no disabled button, so this adds one rather than un-disabling one",
      "est": 2,
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
    },
    {
      "title": "Pro settings phase 3, which IS roadmap Phase E: the entity edit path. update functions in laiive_shared.neo4j_writer where the adoption SET clause is already the statement minus the MATCH key, pusher edit routes behind the user_may_edit helper migration 22 shipped with zero callers, entity_edits finally written, venue and artist cards with real fields, and an edit button on the event card reusing EventForm with a different onSave - no SSE change, because the read path /api/events?uids= already exists end to end. Carries the one-line Phase C fix in EventCardView, and the pusher prompt change so the chat answers 'how do I change an event' with the route rather than a form",
      "est": 5,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Triage the 17 dry_run sweep reports before building G. Zero have ever been dismissed, so either every sweep was clean or the reject path has friction the approve path does not - and G's approval-ratio learning would train one-sided on an approve-only corpus. Read the reject path in services/search/agent/api.py alongside the reports themselves",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {"date": "2026-09-06", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-06", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-08", "model": "opus-5", "person": "oscar", "credits": null, "hours": null}
  ]
}
```
