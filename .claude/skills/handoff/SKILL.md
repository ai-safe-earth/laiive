---
name: handoff
description: Write the root handoff.md at the end of a working session, including the machine-readable JSON block the project tracker parses. Use whenever updating, appending to, or creating the handoff, or when a session is ending and the next one needs to start fresh.
---

# Handoff

One handoff per repository: `handoff.md` at the root. Never start a second one. When work happens
inside a plan folder (`docs/refactor/`), keep writing to the root handoff and list the folder under
"plans" so the paths stay findable. Non-code progress (branding, strategy, docs, artwork) goes to
`product-status.md`, not here.

Read `handoff.md` before planning or writing code. If it conflicts with the repo, trust the repo
and say so.

Write the human part first — state only, 40 lines maximum, no narrative and no history (git log
keeps that). Then append the machine block as the last thing in the file, replacing the previous
one.

<!-- pmctl:handoff v1 -->
```json
{
  "project": "laiive",
  "org": "ai safe earth",
  "status": "amber",
  "updated": "2026-08-15",
  "deadline": "2026-09-30",
  "people": ["ana", "dro"],
  "plans": [
    { "name": "refactor", "path": "docs/refactor/", "status": "active" },
    { "name": "billing", "path": "docs/billing/", "status": "done" }
  ],
  "phases": [
    { "name": "Build", "status": "active", "start": "2026-06-11", "end": null, "plan": "refactor",
      "decisions": [{ "date": "2026-07-02", "text": "Postgres over Mongo, reporting needs joins" }] }
  ],
  "blockers": [{ "text": "Waiting on the provider API key", "severity": "high", "owner": "dro", "since": "2026-08-01" }],
  "nextSteps": [{ "title": "Wire auth to the new schema", "est": 3, "owner": "ana", "phase": "Build", "plan": "refactor" }],
  "sessions": [{ "date": "2026-08-12", "model": "opus-5", "credits": null, "person": "dro", "hours": null }]
}
```

## Rules

**Structure**
- `plans` only points at folders. The work itself stays in `phases`, `blockers`, `nextSteps` and
  `sessions`, each tagged with `plan` when it belongs to one.
- ISO dates, `null` when unknown.
- `status`: `green` | `amber` | `red`.
- phase `status`: `done` | `active` | `planned`.
- `severity`: `critical` | `high` | `medium` | `low`.
- `est` in working days.
- No emoji.

**Writing**
- One `sessions` entry per working session.
- Append `decisions` and `sessions`, never rewrite past ones.
- `credits` and `hours`: leave `null` unless the human gives the numbers. Never estimate them.
- Remove a `nextSteps` entry when it is done. If it produced a decision, add that decision to
  its phase.
- Remove a blocker only when it is actually resolved, and record the resolution as a decision.
- Keep the last 20 `sessions`. Move older ones to `docs/handoff-archive.json` unchanged.
- `decisions` are permanent; they stay with their phase when the phase is `done`.
- Commit the handoff on whatever branch you are working in.

**Stop and ask**
- Personal data, retention, consent, payments or legal text: record it as a blocker with the
  decision needed, and stop. Do not decide it.

## When to invoke

At the end of every working session, and whenever a milestone step is finished, a decision is
made, or a blocker appears. Always before `/clear` or exiting. Not on every turn.
