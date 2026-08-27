---
name: explain-doc
description: Generate a deep-dive HTML explainer in docs/explain/ — system and data-flow schemas with the explained work located on them, code snippets with file:line refs, decisions with reasons, scalability and security notes, key takeaways per section, and a next-steps + recommendations close. Use when the owner asks to explain or document a phase, feature, subsystem, or branch as a document ("like the eval doc", "make an explain doc").
---

Produce a self-contained HTML document in `docs/explain/` explaining a piece of the system —
typically one or two phases of work, a subsystem, or a branch. The reference example is
`docs/explain/eval-phases-0-1.html` (eval phases 0 & 1); match its depth and structure.

## Process

1. **Scope.** Confirm from the request what is being explained (phases, commits, a subsystem).
   Read `handoff.md` (if not already read this session), the relevant roadmap section, and the
   commits involved (`git show --stat`).
2. **Read the real code.** Every snippet quoted must come from the working tree, trimmed but
   faithful. Verify every `file:line` reference with `grep -n` against current HEAD, and name
   that commit in the footer — line refs rot, the footer dates them.
3. **Write the doc** from `template.html` in this skill's directory: copy it, keep its CSS
   verbatim (tokens, light/dark, badges, figures, takeaway boxes — do not regenerate), replace
   the placeholder content. Save as `docs/explain/<kebab-topic>.html`.
4. **Deliver** with SendUserFile, `display: render`. Surface any actionable findings from step
   5's recommendations in the chat message too — the doc is where they're argued, the message
   is where they're seen.
5. **If a recommendation is later acted on**, update the doc's item from `warntag` to
   `goodtag` past-tense with what was done — mark resolved, never delete, the doc stays honest
   as a record.

## Required structure

1. **Why this exists** — the problem or audit finding that motivated the work, in terms of
   what was impossible before. Key-takeaways box.
2. **The system, and where the work lands** — one overview schema of the real architecture
   with the new pieces color-badged per phase/unit, pre-existing infrastructure grey. Omit
   services the work doesn't touch (say so in the caption). Key-takeaways box.
3. **One section per phase/unit**, each with: *goal* (one paragraph), *data flow* (a schema —
   sequence diagram for request paths, state machine for UI, whatever shows the mechanism),
   *how the data moves and transforms* (the code walk: snippets in flow order, each with a
   `file:line` caption bar), *decisions and why* (numbered ①②…/ⓐⓑ…, each marker also placed
   on the schemas at the point the decision bites), *for a scalable system* (real ceilings and
   their upgrade paths, not generic advice), *security* (trust boundaries, who holds which
   keys, what input is hostile), *key takeaways*.
4. **A cross-cutting section** if there is a unifying mechanism (a join key, a shared
   contract) — with the query/usage example the work was built to enable.
5. **What comes next + recommendations and observations** — remaining phases as a status
   table, then a numbered list of things *discovered while writing the doc* (stale comments,
   double-writes, missing retention, injection surfaces). No padding: every item actionable
   or explicitly "accepted, because…".

## Rules

- **Diagrams show the mechanism**, not box-art: who writes what, where the key is born, what
  runs on which thread, what happens on failure. Inline SVG only, theme-aware via the
  template's CSS vars, decision markers keyed to the decision lists.
- **Explain decisions as trade-offs**: what was rejected and why, what the chosen shape costs,
  where the known ceiling is.
- Scalability and security sections describe *this code's* actual edges (thread-per-turn,
  service-role key sprawl, attacker-influenceable corpus) — never checklist boilerplate.
- Self-contained: no external scripts, styles, fonts, or images. English. Wide content
  scrolls in its own container.
- Don't store what another doc already holds — link or cite `handoff.md` / roadmap instead of
  duplicating their content.
