# HANDOFF - laiive (updated 2026-09-06)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Evolution plan
(six areas, A-G, approved 2026-08-25): `~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md`.

**laiive is live at https://laiive.com**, `v0.2.0` shipped 2026-08-25. `develop` is **60 commits
ahead of `main`, nothing deployed since v0.2.0** — still the top risk. The develop preview's
"network error" is the toast `Route POST:/api/publish not found`: one hand-deployed gateway
(main) serves both preview and production and has no phase D routes. Only the deploy fixes it.

## Three PRs open, all into `develop`, none merged

- **#94 `fix/release-prep`** — merge **before** the deploy. Retriever never got its
  `SUPABASE_*` secrets, so `eval_records` would ship dead and silent; `CONTRIBUTING.md` deployed
  *after* the merge (the skew) and back-merged without the local-only warning (PR #66);
  `learning.py` sent `"now()"` as a string, so **every sweep so far recorded nothing** behind one
  caught warning. Fix is not retroactive.
- **#95 `fix/ai-safety-hardening`** — merge **after** the release. `WRITES_DISABLED` on the
  gateway (boot-time, exact `"true"`, whole `/api/admin/search` prefix); `/ingest`'s arbitrary
  URL fetch removed (no scheme/host check, zero call sites); model snapshots pinned in the three
  `config.py` **and** `.example.env`; `.mcp.json` read-only; `verify-retriever` was selecting
  integration tests by a filename deleted in the Phase 2 refactor, so it passed on nothing.
- **#96 `feat/pro-identity`** — after the release **and after migration 23**. kind x relation
  asked once on `/pro`. Also fixes the doubted-field mark: `status-waiting` was never a token,
  so it rendered colourless in production.

Green on every branch: gateway 61, pusher 75, search 125, retriever 200 (not integration),
frontend typecheck + 160.

## Shipped but barely exercised, and open

Phase D (#87-#91): adoption verified against a real Neo4j only as far as the core, six checks
never ran. Correction layer (#92, #93): `start_at_claim` unverified against a real model, every
test mocks OpenAI. Phase C did not fully ship — `EventCardView.tsx:120` computes `verified` from
source alone, so `claimed` arrives on the wire (`executor.py:38`) and is never rendered; one
line, belongs to E. Evals: 0-2 merged, phase 3 kit in #86, error analysis by hand is next.
Aura paused - blocks the probe, the orphan node, the flyer, #96 end to end and the deploy itself.
Migrations 20-22 applied is asserted but unproven; `migration list --linked` settles it.
`flows/serve.py` not served; 17 reports in `dry_run`, zero dismissed; allow-list unread.

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
      "text": "develop is 60 commits ahead of main and nothing has been deployed since v0.2.0 on 2026-08-25. It carries all of phase D and the correction layer. Confirmed in the browser on 2026-09-05 as the cause of the develop preview failure: the toast reads Route POST:/api/publish not found, because the single hand-deployed gateway is main and lacks phase D's orgs.ts. The deploy order matters and CONTRIBUTING.md had it backwards until #94: Cloudflare Pages builds main automatically on merge while every Fly deploy is manual, so the four Fly apps must be deployed from develop BEFORE the release merge, not after it",
      "severity": "high",
      "owner": "oscar",
      "since": "2026-08-25"
    },
    {
      "text": "The Aura free instance is paused and needs a manual resume in the console; while paused its DNS record disappears and on resume reads route to a follower while writes fail. It blocks the six unrun checks of the adoption probe, deleting the orphan Laiive Probe Artist 8f9f909 node, any real end-to-end run of the push pipeline, the end-to-end check of PR #96, and the Fly deploy itself - the three Python services fail readyz at boot without it",
      "severity": "high",
      "owner": "oscar",
      "since": "2026-09-03"
    },
    {
      "text": "Migration 20260905000023_member_relation.sql is not applied, and PR #96's frontend must not deploy ahead of it - useMyOrgs selects a relation column that would not exist and ProSubmit reads undefined orgs as zero, replacing /pro with the founding form for every pro. The ordering is one-way and safe in only one direction: p_relation is declared default null and migration 22's five-argument create_organization is dropped in the same file, so applying it now cannot break the deployed five-argument frontend or the gateway's two-argument bootstrap. Applying is a Supabase write, refused to Claude. Also unproven from the repo: that migrations 20-22 are applied at all, which npx supabase migration list --linked settles. Migration 21 missing would make every thumbs-up POST 502 the moment the new SPA is live",
      "severity": "high",
      "owner": "oscar",
      "since": "2026-09-05"
    },
    {
      "text": "The search learning tables have recorded nothing since they were built. learning.py sent the literal string now() as both timestamps; PostgREST passes it as JSON, Postgres refuses the cast, _upsert raises, and because record_sources runs first, record_queries and promote_queries never ran either - discovery.py:367 catches it and logs one warning, correct handling of a failure nobody was told about. Fixed in #94 but not retroactively: the source and query ranking has been steering off an empty table, and phase G's approval-ratio learning would train on the same nothing. Triage the 17 dry_run reports before building G, and remember zero have ever been dismissed, so either every sweep was clean or the reject path has friction the approve path does not",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-06"
    },
    {
      "text": "start_at_claim, which the whole weekday check depends on, is never exercised: every pusher test mocks OpenAI, so whether the model obeys the new v4 prompt rule is unknown. A missing weekday claim is silent by design and covered by test_no_weekday_claimed_is_silent, so nothing would report it broken; any real loss would be upstream of checks.py, and no such path was found. One real flyer through the local stack settles it",
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
      "title": "Merge PR #94, then deploy the four Fly apps from a clean develop - BEFORE any merge to main. git checkout develop && git pull --ff-only origin develop, make fly-secrets-check, make fly-secrets (now carries the two retriever SUPABASE_* keys), then make fly-deploy-retriever, -pusher, -search, -gateway with flyctl checks list -a <app> after each. Gateway last, it is the only published surface. Use the make targets, not raw flyctl: it resolves both --config and --dockerfile against the positional build context",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Resume Aura in the console, then one trip to the credentials: npx supabase migration list --linked to prove 20-22 are applied, flyctl secrets list -a laiive-retriever to check LANGFUSE_ENABLED (its default flipped True to False this release), and npx supabase db push to apply migration 23. Optional 20s pgTAP check first via a throwaway postgres:16-alpine container - do not pass --single-transaction, the enum ADD VALUE fails spuriously inside one and reads like a migration bug",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Cut the release once the backends are new: PR develop -> main titled release: v0.3.0, merge as a merge commit never a squash, make release on main (cz bump dies under Git Bash without --yes, which the target passes), push with --follow-tags, then merge main back into develop LOCALLY - git fetch origin && git checkout develop && git pull --ff-only origin develop && git merge origin/main && git push origin develop. Never a PR with main as head: the repo deletes head branches on merge and the owner's role bypasses the rule, which is how PR #66 deleted production's branch on 2026-08-23",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Smoke-test the three things this release actually changes, not DEPLOY.md's first-deploy checklist: POST /api/publish returns anything other than 404 (the recorded toast), one pro walk reaches the event form with the corrections and doubts panel rendered, and POST /api/chat/feedback returns 204 rather than 502 - that last one is the migration-21 canary and the fastest signal a migration is missing. Use curl.exe, not PowerShell's curl alias",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Merge PR #95 (ai-safety hardening) then PR #96 (pro identity) into develop, in that order. #95 depends on nothing; #96 needs migration 23 live first. Neither belongs in the release - bundling an unapplied-yesterday schema change into a 60-commit deploy converts a clean deploy into a debuggable one",
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
      "title": "Verify the Supabase redirect allow-list carries <origin>/** for laiive.com, www, laiive.pages.dev and the develop alias, and that Site URL is https://laiive.com - read it, do not infer it (DEPLOY.md section 5 step 2). Closing this closes the Restyle phase",
      "est": 1,
      "owner": "oscar",
      "phase": "Restyle - new visual direction",
      "plan": "roadmap"
    },
    {
      "title": "Phase E (edits + verification): update functions in laiive_shared.neo4j_writer, pusher edit routes behind gateway authz using the user_may_edit helper migration 22 already ships, /admin claims queue with verify/revoke, the card flips on the claim stamp. Near-zero today - entity_edits and user_may_edit exist with zero callers, e.claim_verified is read by executor.py and written by nothing, neo4j_writer.py has no update path at all. The smallest useful slice is update_venue plus PATCH /api/venues/:uid writing entity_edits. Do not start it on top of an undeployed backlog",
      "est": 3,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {"date": "2026-09-05", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-05", "model": "fable-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-06", "model": "opus-5", "person": "oscar", "credits": null, "hours": null}
  ]
}
```
