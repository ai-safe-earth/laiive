# HANDOFF - laiive (updated 2026-09-09)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Plans:
`~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md` (evolution, A-G) and
`~/.claude/plans/pro-user-settings-is-optimized-metcalfe.md` (pro settings, five phases).

**`v0.4.0` is live at https://laiive.com** (2026-09-08): migration 26 applied, gateway on
Fly, SPA from `main`. `develop` is **3 commits ahead** — PR #102, undeployed, and unlike
phase 1 this one does need a gateway deploy.

## Pro settings — 2 of 5 phases done

Phase 1 (#98): `/pro/org` is three labelled bands; `/account` is personal settings plus
every organisation you belong to. Phase 2 (#100): invitations — an owner or admin invites
an address and gets a link to send by hand, there being no mail provider in this project.
Accepting grants `pro` through a trigger, so an invitee who is not yet a promoter can
redeem, and binds to the invited address via the verified email claim. Adversarial review
caught the one that mattered: the signed-out flow never worked, because `/auth` deletes
the postAuth stash on mount by design. Fixed with `?next=` — guarding the mount clear
alone would not survive `googleSignIn` overwriting the stash on the way out.

**Phases 3-5:** entity edit path (~4-5d, **is** roadmap Phase E), dedup (~4d), wizard (~2d).

## What first real use turned up (#102)

Publishing never asked which organisation it was for — `orgForPublish` fell back to
`seats[0]` unordered while `ProSubmit` printed `orgs[0]` from a different query. Fixed.

That was **not** why the reported events were missing: all nine predate v0.3.0
(2026-09-06), which first recorded ownership on a publish, so they have no
`entity_ownership` row. `backfill_ownership.sql` is untracked in the repo root, verified,
awaiting a Supabase run. Events only — the same publishes made three venue nodes for one
room, and filing those would make the duplication permanent. Phase 4's case, with evidence.

## Shipped but barely exercised

Invitations never redeemed by a second real account. Six adoption probe checks never ran,
`start_at_claim` has never met a real model, and no sweep has run since the `now()` fix.
Nothing anywhere sets `verified` on a claim, so "in review" is permanent.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-09-09",
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
      "text": "Two npm advisories on the gateway lockfile, both unassessed: fast-uri (high) and fastify (medium), services/gateway/package-lock.json. The GitHub UI reports 8 high and 3 moderate, which is the same alerts counted across branches - gh api repos/ai-safe-earth/laiive/dependabot/alerts deduplicates to two packages. Neither has been looked at and the gateway is the only published surface, so this is the one security item ahead of feature work",
      "severity": "high",
      "owner": "oscar",
      "since": "2026-09-06"
    },
    {
      "text": "The owner cannot see nine of their own published events on /pro/org, because they were published before v0.3.0 (2026-09-06) added ownership recording and so have no entity_ownership row. backfill_ownership.sql is untracked in the repo root, generated from the graph by owner_id and verified against postgres:16-alpine - 9 rows inserted, idempotent on re-run because the ON CONFLICT names the partial index predicate. It is a Supabase write, so it is oscar's to run, and the file should be deleted afterwards",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-09"
    },
    {
      "text": "Accepting an invitation binds to the verified email claim, which assumes an account cannot freely change its Supabase email. Supabase requires confirmation on both addresses by default, but the project setting is unverified - if secure email change is off, somebody holding a leaked invite link could set their account email to the invited address and redeem it. Read it in the same GET /v1/projects/<ref>/config/auth call as the redirect allow-list",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-09"
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
      "text": "develop is 3 commits ahead of main and undeployed - PR #102, merged 2026-09-09. It carries the publish-organization fix and the roster and invite simplifications, so unlike phase 1 this one does need a gateway deploy as well as the Cloudflare build. Small, but the pattern of quiet backlog is what produced the twelve-day and sixty-commit versions of this same line",
      "severity": "low",
      "owner": "oscar",
      "since": "2026-09-09"
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
      "title": "Run backfill_ownership.sql in the Supabase SQL editor, then delete the file - it is untracked in the repo root. Nine events this account published become visible on /pro/org, which is the thing actually blocking daily use. Verified idempotent, so a second run is harmless. Events only on purpose: the venues would carry three nodes for one room into the org page permanently",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Read the two npm advisories on the gateway lockfile - fast-uri (high) and fastify (medium) - and decide whether a bump is a one-line lockfile change or a fastify major. gh api repos/ai-safe-earth/laiive/dependabot/alerts is the deduplicated view; the UI count is the same alerts across branches. The gateway is the only published surface, so this is the one security item ahead of feature work",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Ship the three develop commits as v0.4.1: release PR develop -> main, merge as a merge commit, make release on main (which now works from PowerShell), push with --follow-tags AND then git push origin <tag> because cz writes a lightweight tag that --follow-tags ignores, make fly-deploy-gateway, then merge main back into develop LOCALLY. The gateway changed this time, so it is not a Cloudflare-only release",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Read the Supabase auth config once and settle two blockers in the same call: that the redirect allow-list carries <origin>/** for laiive.com, www, laiive.pages.dev and the develop alias with Site URL https://laiive.com (DEPLOY.md section 5 step 2, closes the Restyle phase), and that secure email change is on, which is what the invitation email binding assumes",
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
      "title": "Triage the 17 dry_run sweep reports before building G. Zero have ever been dismissed, so either every sweep was clean or the reject path has friction the approve path does not - and G's approval-ratio learning would train one-sided on an approve-only corpus. Read the reject path in services/search/agent/api.py alongside the reports themselves",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {"date": "2026-09-06", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-08", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-09", "model": "opus-5", "person": "oscar", "credits": null, "hours": null}
  ]
}
```
