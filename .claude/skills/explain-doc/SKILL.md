---
name: explain-doc
description: Generate a deep-dive HTML explainer in docs/explain/ — architecture and data-flow schemas locating the work, code walks with verified file:line refs, decisions with reasons, and actionable recommendations. Use when the owner asks to explain or document a phase, feature, subsystem, or branch as a document ("like the eval doc", "make an explain doc").
---

Produce a self-contained HTML document in `docs/explain/` explaining a piece of the system.
The skill argument names the topic (phases, a subsystem, a branch); if it's missing, ask.
Sources of truth, in order: this file owns the structure, `template.html` (in this skill's
directory) owns the CSS and markup conventions, and the newest doc in `docs/explain/`
calibrates depth and diagram idiom — skim one of its sections, don't study the whole file.

## Process

1. **Scope.** `ls docs/explain/` first: a topic continuing earlier work gets a NEW doc that
   links its predecessor instead of re-explaining it — and while there, flip any prior-doc
   recommendation this work resolved (`warntag` → `goodtag`, past tense; never delete one).
   Then read the relevant `docs/roadmap/` section and the commits involved
   (`git show --stat`).
2. **Read the real code.** Every snippet quoted must come from the working tree, trimmed but
   faithful. Verify every `file:line` with `grep -n` in the working tree; the footer names
   the current commit and flags any quoted file that has uncommitted changes.
3. **Write the doc** from `template.html`: copy it, keep its CSS verbatim, replace the
   placeholder content. For markup the template doesn't stub (sequence-diagram figures, the
   status table), copy the pattern from the newest existing doc. Save as
   `docs/explain/<kebab-topic>.html` and commit it (`docs(explain): <topic>`).
4. **Deliver** with SendUserFile, `display: render`, and repeat the doc's closing
   recommendations in the chat message — the doc is where they're argued, the message is
   where they're seen.

## Structure

1. **Why this exists** — the problem or finding that motivated the work, in terms of what
   was impossible before.
2. **The system, and where the work lands** — one overview schema of the real architecture,
   new pieces color-badged per unit, pre-existing infrastructure grey; omit services the
   work doesn't touch and say so in the caption.
3. **One section per phase/unit**: *goal* (a paragraph) → *data flow* (a schema: sequence
   diagram for request paths, state machine for UI) → *how the data moves and transforms*
   (snippets in flow order, each with a `file:line` caption bar) → *decisions and why*
   (numbered ①②…/ⓐⓑ…, each marker also placed on the schema where the decision bites) →
   *for a scalable system* (real ceilings and their upgrade paths) → *security* (trust
   boundaries, who holds which keys, what input is hostile).
4. **A cross-cutting section** if there is a unifying mechanism (a join key, a shared
   contract) — with the query/usage example the work was built to enable.
5. **What comes next + recommendations** — remaining phases as a status table when the work
   sits in a phased plan (otherwise straight to recommendations), then a numbered list of
   things *discovered while writing* (stale comments, double-writes, missing retention).
   Every item actionable or explicitly "accepted, because…".

Scale to the topic: a single-unit topic uses one accent (`--p0`) and no legend, and any
subsection with nothing real to say (a bugfix with no security edge) is omitted — an omitted
section beats an invented one.

## Rules

- End every top-level section with a key-takeaways box.
- **Diagrams show the mechanism**: who writes what, where the key is born, what runs on
  which thread, what happens on failure. Every arrow is labeled with what crosses it — an
  unlabeled arrow is box-art. Inline SVG only, theme-aware via the template's CSS vars.
- **Decisions are trade-offs**: what was rejected and why, what the chosen shape costs,
  where the known ceiling is. Scalability and security sections describe *this code's*
  actual edges, never checklist boilerplate.
- Self-contained: no external scripts, styles, fonts, or images. Wide content scrolls in
  its own container. English.
- Don't restate what `handoff.md` or the roadmap already holds — cite it.
