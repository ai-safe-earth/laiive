# 00 — Closed

The refactor described in this folder is **closed as of 2026-08-19**. Phases 0–5 were built
and verified live; Phase 6 delivered CI, hardened images, the internal-key boundary, the
compose topology and the deploy configs, and hands the live deploy itself to `DEPLOY.md`.

`refactor/foundation` was merged into `main` through PR #29. The pre-refactor tree is
preserved on branch **`legacy/pre-refactor`** and tag **`pre-refactor-main`**, both at
`542952f`. Nothing was rewritten or dropped to make the merge work.

`main` was not the untouched ancestor it looked like: it carried six commits the branch had
never seen, one of them a real change (`5a0a97c`, the owner's README revision from March).
`origin/main` was merged into the branch first and the README resolved by hand — the owner's
newer marketing copy, the branch's technical sections. The tag `legacy-main-2026-08-19` was
cut before this was noticed and points six commits short of the real tip; delete it.

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
