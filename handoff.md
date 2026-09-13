# HANDOFF - laiive (updated 2026-09-13)

State only. Rules: `CLAUDE.md`. Programme: `docs/roadmap/01-program.md`. Plans:
`~/.claude/plans/read-claude-md-and-handoff-md-sparkling-star.md` (evolution, A-G) and
`~/.claude/plans/pro-user-settings-is-optimized-metcalfe.md` (pro settings, five phases).

**`v0.4.2` is live** (advisories + the trustProxy fix, gateway deployed). Everything since
sits on `develop` unreleased: graceful graph errors (#107), the dedup eval set (#108),
vitest 4 (#109), and **pro settings phase 3 / Phase E (#110-#113)**. The next release is a
**Fly deploy of gateway + pusher + retriever** plus the SPA — not Cloudflare-only.

## Phase 3 shipped — what exists now

Events are editable end to end: `update_event/venue/artist` in the shared writer (PATCH
semantics, per-field old/new deltas), pusher `PATCH /events|venues|artists/{uid}`, gateway
routes asking `user_may_edit` before the write and filing `entity_edits` after (migration
22's first callers), an Edit button on `/pro/org`'s event cards reusing EventForm, and the
chat (prompt v7) pointing "change my event" at that button. Venue/artist edit **routes**
work; their **forms** do not exist yet. Venue rename and artist relinking are excluded by
design (name_norm is the MERGE identity). E3 (admin verify/revoke) is **not built**, so
nothing sets `verified` yet and the card tick for claimed swept listings stays inert.
Open PRs: #114 (venue/artist hits carry capacity/city/description), #115 (js-yaml patch).

## The dedup evidence and its eval set

The live flyer test proved adoption cannot fire through chat: nameless drafts get derived
names and the exact name_norm key misses — three attempts, two silent duplicates (both
deleted), zero adoptions. `services/pusher/evals/dedup_review.csv` holds 52 verified
cases (21 end in a silent duplicate today) — **merged unreviewed**; the owner's
verdict/should_instead pass is the gate for Phase 4 and turns it into
`datasets/dedup/test_cases.json`.

## Search

The `now()` fix is observed, not believed: one Bergamo sweep moved both learning tables
(a domain crossed to `blocked`, query `runs` incremented). The review backlog is **37
dry_run reports / 892 candidates** (the old 17 was stale), zero ever dismissed — the
dismiss button does not render on zero-candidate reports (`AdminReport.tsx:218-244`,
action bar inside `candidates.length > 0`), there is no queue-level dismiss, and
`running`/`failed` reports cannot be cleared at all. All 11 approvals date Aug 14-23.
Dependabot: 13 stale alerts clear on rescan; the real pair (js-yaml) is #115.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-09-13",
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
      "text": "Phase G is gated twice: the approval corpus is one-sided (11 approvals all Aug 14-23, zero dismissals ever, so approval-ratio learning would train on era not quality) and the 37-report/892-candidate backlog cleanup decision is pending - dismiss 3 zero-new + ~13 superseded same-city duplicates, plus the one-line dismiss-button fix in AdminReport.tsx:218-244",
      "severity": "medium",
      "owner": "oscar",
      "since": "2026-09-12"
    },
    {
      "text": "There is no staging backend. Pages builds an SPA preview per branch but VITE_API_URL is one project-level variable pointing at the single production gateway, so any frontend change on develop needing a new route 404s on the preview until a deploy. Pages supports separate Preview and Production variables; the fix costs a second gateway, pusher and retriever on Fly plus a decision about whether preview publishes write into the production graph",
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
      "title": "Merge #114 and #115, then ship: release PR develop -> main, make release, push with --follow-tags AND git push origin <tag>, then make fly-deploy-gateway AND fly-deploy-pusher AND fly-deploy-retriever (shared, pusher, gateway and retriever source all changed since v0.4.2), then merge main back into develop locally",
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
      "title": "Report backlog cleanup: approve the dismissal list (3 zero-new + ~13 superseded duplicates -> ~21 reviewable reports led by Venaria 100, Romano 64, Bergamo 56, Torino 53) and ship the one-line dismiss-button fix so zero-candidate reports stop being dead ends",
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
      "title": "Phase 4 dedup (multi-signal suggest-at-entry: name similarity OR artist overlap + venue + date -> chat asks 'same event?'), built against the reviewed eval set; the cross-city probe false positive and the derived-name collision are its two extra cases with evidence",
      "est": 4,
      "owner": "oscar",
      "phase": "Evolution - six areas",
      "plan": "roadmap"
    }
  ],
  "sessions": [
    {"date": "2026-09-09", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-11", "model": "opus-5", "person": "oscar", "credits": null, "hours": null},
    {"date": "2026-09-13", "model": "fable-5", "person": "oscar", "credits": null, "hours": null}
  ]
}
```
