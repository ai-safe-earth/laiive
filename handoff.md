# HANDOFF - laiive (updated 2026-09-15)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Plans:
`~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md` (evolution, A-G) and
`~/.claude/plans/pro-user-settings-is-optimized-metcalfe.md` (pro settings, five phases).

**`v0.4.2` is live.** Unreleased on `develop`: #107-#117 (graph errors, dedup eval set, vitest
4, pro settings phase 3 / Phase E, lookup fields, js-yaml, the #116 composer pass, the report
dismiss fix). Next release is **v0.5.0**: a Fly deploy of gateway + pusher + retriever **and
search**, plus the SPA. Search is in the list because `services/search/agent/graph.py` imports
`laiive_shared.neo4j_writer` directly and the shared writer grew 714 lines this cycle.

## Open now: #119, the consumer app at phone size

`feat/card-type-at-phone-size`, 2 commits, all checks green, mergeable, sitting on #117.
#116 lifted only the conversation. This lifts everything around it: Bebas event titles
`xl`->`2xl` (condensed caps at 18px read nearer 14), card body lines `sm`->`md`, card pills
and the price badge `xs`->`sm`, chips `sm`->`md`, status lines and hints `xs`->`sm`, `/saved`
section rules and the menu role line `2xs`->`xs`, account chip initials `xs`->`sm`. The pill's
44px touch overlay is recentred (`-top-7`->`-top-6`) so the floor still holds exactly.
`2xs` is now promoter and admin chrome only; inputs stay at `base` (iOS zooms below 16px).
`brand-rules.md`'s type table is amended in the same PR. The role line is the one change that
reaches the promoter surface - `UserMenu` is one component on both. Pro and admin screens are
untouched and have not been looked at on a phone.

## Phase 3 shipped

Events are editable end to end: `update_*` in the shared writer (PATCH, per-field deltas),
pusher `PATCH /events|venues|artists/{uid}`, gateway routes asking `user_may_edit` then
filing `entity_edits`, an Edit button on `/pro/org` reusing EventForm, prompt v7 pointing
"change my event" at it. Venue/artist edit **routes** work, their **forms** do not exist;
rename and relinking are excluded by design (name_norm is the MERGE identity). E3 is **not
built** - nothing sets `verified`, the claimed-card tick is inert.

## Dedup evidence, search backlog, dev box

Adoption cannot fire through chat: nameless drafts get derived names and the exact name_norm
key misses - three attempts, two silent duplicates, zero adoptions. `dedup_review.csv` (in
`services/pusher/evals/`) holds 52 verified cases, 21 of them silent duplicates today, and is
**merged unreviewed**; the owner's pass over it gates Phase 4.

Search: the `now()` fix is observed. Backlog **37 dry_run reports / 892 candidates**, zero ever
dismissed - #117 fixed the half of that which was a bug (zero-candidate reports had no dismiss
button at all); the cleanup decision itself is still open. `running`/`failed` reports remain
unclearable and that one is backend: `dismiss_report` only accepts `dry_run`.

Dev box: `gh pr edit` is **broken against this repo** - every call dies on the GraphQL
Projects-classic deprecation (`repository.pullRequest.projectCards`). `gh pr create` is fine;
to edit a title or body use `gh api -X PATCH repos/ai-safe-earth/laiive/pulls/N --input f.json`.
A `tail`/`ls` naming `docs/pm-log.jsonl` is refused by the deny rule, appends are not.
`Auth.test.tsx` times out on 1-2 specs in the parallel `npm test` here under load and passes
alone and on CI: 5s `testTimeout` against a 30s file, not the code.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-09-15",
  "deadline": null,
  "people": ["oscar"],
  "plans": [
    {"name": "refactor", "path": "docs/refactor/", "status": "done"},
    {"name": "roadmap", "path": "docs/roadmap/", "status": "active"}
  ],
  "phases": [
    {"name": "Evolution - six areas", "status": "active", "start": "2026-08-25", "end": null, "plan": "roadmap"},
    {"name": "Ingestion + self-improvement", "status": "active", "start": "2026-08-22", "end": null, "plan": "roadmap"},
    {"name": "Evals + observability", "status": "active", "start": "2026-08-26", "end": null, "plan": "roadmap"},
    {"name": "Multi-provider model routing", "status": "planned", "start": null, "end": null, "plan": "roadmap"},
    {"name": "Retrieval accuracy", "status": "planned", "start": null, "end": null, "plan": "roadmap"},
    {"name": "Guardrails, cache, language, voice", "status": "planned", "start": null, "end": null, "plan": "roadmap"}
  ],
  "blockers": [
    {
      "text": "Phase 4 (dedup) is gated on the owner reviewing the 52-case eval set merged unreviewed in #108: services/pusher/evals/dedup_review.csv, fill verdict/should_instead per row, then it becomes datasets/dedup/test_cases.json - the acceptance suite Phase 4 is built against",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-13"
    },
    {
      "text": "Phase G is still gated twice, though the UI half is fixed: the approval corpus is one-sided (11 approvals all Aug 14-23, zero dismissals ever, so approval-ratio learning would train on era not quality) and the 37-report/892-candidate backlog cleanup decision is pending - dismiss 3 zero-new + ~13 superseded same-city duplicates. #117 shipped the missing dismiss button, so the backlog is now actually clearable",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-12"
    },
    {
      "text": "There is no staging backend. Pages builds an SPA preview per branch but VITE_API_URL is one project-level variable pointing at the single production gateway, so any frontend change on develop needing a new route 404s on the preview until a deploy - #119's preview renders the new type scale but cannot hold a conversation. Pages supports separate Preview and Production variables; the fix costs a second gateway, pusher and retriever on Fly plus a decision about whether preview publishes write into the production graph",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-03"
    },
    {
      "text": "The writer's query contract is hand-copied into three fake sessions (shared, pusher, search conftests), and the edit path added update branches to two of them - four places now drift silently when a RETURN changes. Collapsing them into services/shared/laiive_shared/testing.py is about 1.5h and net -100 lines",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-02"
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
      "title": "Review #119 on a real phone, merge it, then ship v0.5.0: release PR develop -> main, make release, push with --follow-tags AND git push origin <tag>, then make fly-deploy-gateway AND fly-deploy-pusher AND fly-deploy-retriever AND fly-deploy-search (search imports the shared writer directly), then merge main back into develop locally",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Review the dedup eval CSV case by case in Excel (verdict + should_instead), hand back corrections, convert to datasets/dedup/test_cases.json - unblocks Phase 4",
      "est": 1,
      "owner": "oscar",
      "phase": "Evals + observability",
      "plan": "roadmap"
    },
    {
      "title": "Exercise the shipped edit path once against production after the deploy: edit a real event's price from /pro/org, confirm the card refreshes and the entity_edits row lands with the delta; in the same sitting, ask the chat to change an event and confirm the v7 prompt points at the Edit button, and check whether a weekday-contradicting flyer gets questioned (start_at_claim's ask-behaviour is still unobserved)",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Report backlog cleanup, now that the dismiss button exists: approve the dismissal list (3 zero-new + ~13 superseded duplicates -> ~21 reviewable reports led by Venaria 100, Romano 64, Bergamo 56, Torino 53) and work it down",
      "est": 1,
      "owner": "oscar",
      "phase": "Ingestion + self-improvement",
      "plan": "roadmap"
    },
    {
      "title": "E3: admin verify/revoke - POST /api/admin/claims/:id/verify|revoke, Supabase row first then idempotent graph stamp with one retry, card tick goes live; ends 'in review is permanent'",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Venue and artist edit forms on /pro/org: the routes, writer whitelists and lookup fields (capacity, description, city) all exist - only the UI is missing",
      "est": 2,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Give /pro and /admin the same phone pass #116 and #119 gave the consumer app - they were deliberately excluded and have never been looked at on a 5.5in screen; admin is a desktop tool and exempt from the 44px floor, /pro is not",
      "est": 1,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    },
    {
      "title": "Phase 4 dedup (multi-signal suggest-at-entry: name similarity OR artist overlap + venue + date -> chat asks 'same event?'), built against the reviewed eval set; the cross-city probe false positive and the derived-name collision are its two extra cases with evidence",
      "est": 4,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {"date": "2026-09-11", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-13", "model": "fable-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-15", "model": "opus-5", "person": "oscar", "credits": null, "hours": null}
  ]
}
```
