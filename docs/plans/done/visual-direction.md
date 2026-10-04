---
status: done
step: foundation
next: none
---
# Visual direction (program phase 2)

Brand v1, the type-scale lift, the composer menu and the feedback thumbs on assistant turns
are merged. Brand rules: `assets/brand/brand-rules.md`. The token file records what the app ships.

Constraints that still hold for any restyle:
- Protocol types come from `services/shared/ts/protocol.ts`, never redeclared.
- Every string goes through `src/i18n/translations.ts` in four languages.
