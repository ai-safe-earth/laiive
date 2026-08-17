---
name: handoff
description: Write the root handoff.md at the end of a working session, including the machine-readable JSON block the project tracker parses. Use whenever updating, appending to, or creating the handoff, or when a session is ending and the next one needs to start fresh.
---

# Handoff

One handoff per repository: `handoff.md` at the root. Never start a second one. When work happens
inside a plan folder (`docs/refactor/`), keep writing to the root handoff and list the folder under
"plans" so the paths stay findable.

Write the human part however you like, then append this machine block as the last thing in the
file, replacing the previous one.

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
  "sessions": [{ "date": "2026-08-12", "model": "opus-5", "credits": 40, "person": "dro", "hours": 2.5 }]
}
```

## Rules

- `plans` only points at folders. The work itself stays in `phases`, `blockers`, `nextSteps` and
  `sessions`, each tagged with `plan` when it belongs to one.
- ISO dates, `null` when unknown.
- `status`: `green` | `amber` | `red`.
- phase `status`: `done` | `active` | `planned`.
- `severity`: `critical` | `high` | `medium` | `low`.
- `est` in working days.
- One `sessions` entry per working session.
- Append `decisions` and `sessions`, never rewrite past ones.
- Commit the handoff on whatever branch you are working in.
- No emoji.
