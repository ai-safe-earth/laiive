---
status: active
step: foundation
next: owner lists the next frontend change
---
# Frontend tweaks before continuing the roadmap

A batch of small frontend changes the owner asked for on 2026-10-07, ahead of step 2.

## Steps
- [x] 1. Delete the opening film on the chat (`laiive-intro.mp4`, `introAt`, its test).
- [x] 2. Live accents from `assets/brand/live-accents/PROMPT.md`: CSS, hook, `LiveAccent` wrapper,
  live mark / saved icon / primary fill / FREE chip / account chip, brand docs.

## Decisions
- Live accents: the missing `mask-mark.png` is replaced by the existing
  `mark-mono-fuchsia-knockout.png` (same outline, mouth transparent, checked by pixel).
- No empty-state lips and no live headline text: neither exists in the app yet (owner: keep the
  grey LAIIVE). The `text` variant is ready for when one does.
- The header saved icon goes live (owner's call), so it is fuchsia now, not grey.
- `<LiveAccent>` wrapper built (owner's call); `liveAccent()` gives the class string for Button.
- The waiting send stays flat fuchsia at 45%; disabled buttons drop the world (`disabled:bg-none`).
- The hook reads all positions before writing any, and skips unchanged ones.
- Risk to watch: the locked CSS animates two inherited properties on `:root`, which restyles the
  whole page every frame. Fine on a short chat; check on a slow phone with a long thread.
- The chat's grey LAIIVE wordmark stays: it is the empty-chat backdrop, not part of the film.
- `UserMenu` keeps passing `state={{ from }}`: the Account page's back link reads it.
- The promoter walkthrough video on /pro is a different video and stays.
- Branched from `cleanup`, not `develop`: `develop` has no `docs/plans/` yet.
