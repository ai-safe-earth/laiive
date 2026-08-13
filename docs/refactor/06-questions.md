# 06 — Questions (answered 2026-08-13)

All questions answered by the owner; decisions promoted to `05-decisions.md` (D5–D16).

## A. Product / UX

1. **Public event pages?** → Chat-only for now.
2. **Languages** → In chat: no fixed list — the assistant adapts to the user's language
   (standard multilingual-model behavior). App UI texts outside the chat: en/es/it/ca,
   selectable in profile settings and at first signup.
3. **Anonymous users** → Allowed, rate-limited at the API gateway; UI suggests login to
   increase quota.
4. **Pro Google login** → Yes; pro signup also collects data about the venues, artists
   or events they manage/own.
5. **Maps** → Embedded map inside the expanded card, shown when the map button is
   clicked (not just a deep link).

## B. Architecture / code

6. **Shared Python code** → Shared package (`services/shared`). Both consumers are
   ours; keep it DRY; CI catches breaks.
7. **Package manager** → npm. No bun.
8. **Geocoding** → Nominatim (free); switch to Google only on rate limits or bad
   accuracy.
9. **SEARCH trigger** → CLI + admin endpoint only; UI only when a non-dev needs it.
10. **Search API** → Keep Brave; no evaluation of alternatives unless it fails.
11. **Evals** → Quarantine datasets, delete broken runners; rebuild coverage later.
12. **Old Aura `5ce2d474`** → Verified in the Aura console (2026-08-13): the account
    has one org (laiive.com), one project, one instance — `2099d44c` (RUNNING, AuraDB
    **Free**, 0 nodes). `5ce2d474` does not exist. Dead, confirmed.
    ⚠ Free tier ⇒ `NODE KEY` constraints unavailable → the UNIQUE + NOT NULL fallback
    in `03-ontology.md` is the default DDL; Free instances pause after inactivity.

## C. Operations

13. **Key rotation** → Done (OpenAI, Aura, Langfuse — all updated in root `.env`).
    Connectivity to `2099d44c` with the rotated credentials verified from the
    retriever's own config loader.
14. **Canonical remote** → `https://github.com/ai-safe-earth/laiive` = git remote
    **`origin`**. (Naming caution: the git remote *named* `laiive` points to the
    OscarArroyoVega fork — PRs go to `origin`.)
15. **Supabase** → Fresh project (new migrations from scratch; the old project
    `ccdlygjdizpesdblymaq` is reference material only).
16. **Budget** → $30–50/month total (LLM + hosting). Drives mini-first model policy
    and free-tier-first infra (see 05/R2–R3).

## D. Approval gates

17. Phase 1 schema DDL on Aura `2099d44c` — still gated on an explicit go.
18. Pushes go to `origin` (ai-safe-earth/laiive) only when explicitly requested.
