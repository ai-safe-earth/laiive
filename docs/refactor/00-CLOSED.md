# 00 — Closed

The refactor described in this folder is **closed as of 2026-08-19**. Phases 0–5 were built
and verified live; Phase 6 delivered CI, hardened images, the internal-key boundary, the
compose topology and the deploy configs, and hands the live deploy itself to `DEPLOY.md`.

`refactor/foundation` (147 commits) was merged into `main`, which had not moved since the
pre-refactor tree. That tree is preserved on branch **`legacy/pre-refactor`** and tag
**`legacy-main-2026-08-19`** — nothing was rewritten or dropped to make the merge work
(`main` was a strict ancestor, so the merge carried no conflicts).

The k3s detour (D19) was decided and withdrawn on the same day; the work is parked on branch
`experiment/k3s` and is not part of the closed refactor.

## What these six documents are now

Historical record, not instructions. They are the reasoning behind the current architecture
and the decision log (D1–D19), and the project tracker reads them. When one of them
disagrees with the code, the code is right and the document is a snapshot of an earlier
opinion.

The moving picture lives in the root `handoff.md`; the stable rules live in the root
`CLAUDE.md`.

## What stayed open at closing time

Owner-driven, tracked in `handoff.md`, none of them blocking the merge:

- the live deploy (`DEPLOY.md`), gated on Supabase migration `20260818000010`;
- the Aura repair-sweep drain (a graph write);
- the Google sign-in click-through with a real account;
- a browser walkthrough of the Phase 4d multi-event walk.
