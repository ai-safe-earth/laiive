# Prompt for Claude Code — laiive live accents

Paste everything below the line into Claude Code, with this folder (`assets/brand/live-accents/`) and the rest of `assets/brand/` available in the repo.

---

Add the laiive **live accents** to the React frontend. Materials are in `assets/brand/live-accents/`:

- `live-accents.css` — the full, locked implementation (tokens, world gradient, keyframes, classes, reduced-motion fallback). Use its values exactly.
- `useLiveAccents.ts` — reference hook that writes each accent's screen position into `--hx/--hy`.
- `mask-mark.png` — stencil of the laiive mark with the mouth cut out (keeps the exact logo shape). `mask-saved.svg` — saved icon stencil.
- `demo.html` — open it in a browser: that is the target look and motion.

**Concept.** The screen is a black window. Every fuchsia accent is a hole in it, showing one shared, moving coloured world fixed to the viewport. A light travels from accent to accent; a violet counter-light moves opposite it. All accents must sample the SAME world — never give an element its own independent gradient or animation.

**Do this:**

1. Copy `live-accents.css` into `frontend/src/styles/` and import it once from `index.css` (after the `:root` tokens). Copy `mask-mark.png` and `mask-saved.svg` into `frontend/public/brand/`.
2. Add `useLiveAccents.ts` to `frontend/src/hooks/` and call `useLiveAccents()` once in the app root.
3. Apply the classes:
   - **Mark** (header lockup and the large empty-state lips): replace the fuchsia `<img>`/`<svg>` with `<div class="live-accent live-accent--mask live-mark" role="img" aria-label="laiive">` at the same size. The wordmark LAIIVE stays cream `#F4EDE2`, not live.
   - **Fills** — every element currently painted with `bg-primary` (primary buttons, FREE chips, the send button, active pills): add `live-accent`. Keep the dark ink `#0C0A0A` label/glyph on top.
   - **Text** — fuchsia headline words in Bebas Neue ≥ 28px: `live-accent live-accent--text` (needs `display:inline-block`). Do NOT use it on body text or anything < 28px; those stay flat `--primary`.
   - **Saved icon** (header): `live-accent live-accent--mask live-saved`.
4. Leave flat: focus rings, borders, `--ring`, amber (`--secondary`) elements, cyan pro elements, and everything on pro screens. Live accents are consumer-side only.
5. Create a small `<LiveAccent as=… variant="fill|text|mask" mask="mark|saved">` wrapper so components don't hand-write class strings.
6. Brand docs: add to `brand-rules.md` → "Accents are live: holes onto one shared world (`live-accents.css`). New colours `--live-base #D4007F`, `--live-1 #FF4FB2`, `--live-2 #8A2BE2` exist ONLY inside the world gradient — never as flat UI colours." Add the three tokens to `brand-tokens.css` with that comment. This reverses the earlier "no gradients" rule for accents only; the app ground stays flat `#0C0A0A`.

**Check before you finish:**
- Scroll the chat and open a sheet: accents keep sampling the same world (no seams, no jump when a hole moves).
- `prefers-reduced-motion: reduce` → every accent is flat `#FF2AA0`.
- Logo shape is identical to `assets/brand/mark-fuchsia-alpha.png`, mouth line visible.
- No layout thrash: one `getBoundingClientRect` pass per frame at most, and only when something changed.
- If accents sit far from the itinerary in `@keyframes live-tour`, retune those stops (viewport %) so the spot visits each one; keep the 5s loop.
