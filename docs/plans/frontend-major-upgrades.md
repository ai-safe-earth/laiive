---
status: todo
step: upgrades
next: upgrade vitest 2 -> 4 alone and run the frontend suite
---
# Frontend major upgrades

PR #137 (2026-10-08) took every security patch that needed no major version jump. The
frontend still shows 15 `npm audit` items (2 critical, 6 high, 7 moderate). All of them
need a major upgrade. Gateway is already clean.

| package | now | target | ships to users? | why |
|---|---|---|---|---|
| vitest (+ tinypool, vite-node, @vitest/mocker) | 2.1 | 4.x | no, tests only | the two critical items |
| vite (+ esbuild) | 5.4 | 7 or 8 | no, build and dev server | esbuild dev-server read bug |
| tailwindcss (+ braces, micromatch, chokidar, postcss-selector-parser) | 3.4 | 4.x | no, build only | most of the highs |
| react-router-dom | 6.30 | 7.x | yes | moderate, but it is in the bundle |

## Steps (one PR each, smallest risk first)
- [ ] 1. vitest 2 -> 4 (match the gateway, which is on 4). Fix config and any changed
      mocking APIs. Gate: 207 frontend tests pass.
- [ ] 2. vite 5 -> 7 or 8 with `@vitejs/plugin-react` to match. Gate: build, dev server on
      8081, typecheck, tests, Cloudflare preview loads.
- [ ] 3. react-router 6 -> 7 (23 files import it). v6 "future" flags first, then the bump.
      Gate: tests, plus a click-through of every route on the preview.
- [ ] 4. Tailwind 3 -> 4. The biggest: config moves into CSS (`tailwind.config.ts`,
      `postcss.config.js`, `index.css`, the brand tokens and `live-accents.css`).
      Run the official upgrade tool, then compare screenshots of chat, auth and admin
      in light and dark, before and after.
- [ ] 5. `npm audit` clean on the frontend; close the GitHub alerts.

## Decisions
- One major per PR, so a broken page points at one package.
- Nothing ships to users except react-router, so steps 1, 2 and 4 carry no user-facing
  security risk today; they are hygiene and future-proofing.
