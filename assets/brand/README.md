# assets/brand — laiive brand handoff (v1)

For Claude Code, working on `ai-safe-earth/laiive`. Read `brand-rules.md` first;
it is the checkable version of `brand-guide.pdf`, which is normative.

## Contents

| File | What it is |
|---|---|
| `brand-rules.md` | Enforceable rules: what's locked, colour meanings, type, voice, pro specifics |
| `brand-tokens.css` | Drop-in `:root` block for `frontend/src/index.css` (HSL, existing token names) |
| `icons.svg` | 17 symbols, 24px grid, 1.7px stroke — `<use href="/brand/icons.svg#saved"/>` |
| `reference-screens.html` | Static markup of the consumer chat and the pro submit screen, real values |
| `brand-guide.pdf` | The full guide — export from *laiive Brand Guide* and drop it here |
| `mark-*.png` (14) | The mark, one outline, recoloured per ground. Filenames are the contract |
| `appicon-1024-*.png` (2) | Launcher / store icon, primary and alternate |
| `og-base-1200x630.png` | Social card ground — set the text in HTML, never bake it in |

## Order of work in the frontend

1. `frontend/src/index.css` — replace the `:root` block with `brand-tokens.css`.
   Delete `--gradient-*` and `--glow-*`; nothing should reference them after.
2. `frontend/tailwind.config.ts` — `fontFamily` → `bebas` / `sans` / `mono`
   (see the tail of `brand-tokens.css`); remove `backgroundImage` and `boxShadow`
   extensions tied to the deleted gradient/glow vars.
3. `frontend/index.html` — swap the Google Fonts link; replace the favicon with
   `appicon-1024-cream-on-fuchsia.png` (and `mark-mono-fuchsia-knockout.png` at
   ≤20px); point `og:image` at a card built on `og-base-1200x630.png`.
4. `src/pages/Chat.tsx` — strip to the four chrome elements in `brand-rules.md`:
   bare mark + wordmark, saved + account icons, one `+` (voice only), composer.
   No tab bar, no titles, no explanatory copy.
5. `src/components/EventCardView.tsx` — card `#241B1B` r20 + hairline, Bebas 18px
   title, meta `#B5A6A6` 12.5px, amber price pill with `#0C0A0A` ink, "FREE" in
   fuchsia with `#0C0A0A` ink, actions as neutral pills, tickets amber.
   Answer groups get the 2px amber rail at 50%, indent 11px.
6. `src/components/UserMenu.tsx` — remove the language row from the header;
   language moves into settings inside the account menu.
7. `src/pages/ProSubmit.tsx` + `src/components/EventForm.tsx` — consumer ground,
   flat conversation, cream-framed form card, pill fields, amber required
   markers, red missing state, cream publish button, warm-neutral composer icons.
   Keep the existing REQUIRED set and validation behaviour exactly.
8. `src/pages/Auth.tsx`, `Account.tsx` — same tokens; no new patterns.

## Two things that are not decided yet

- **saved** has artwork and a place in the bar, but no feature. Wire the icon,
  leave the behaviour.
- The **empty/error copy** in the artwork set is the tone, not final strings —
  translations live in `src/i18n/translations.ts` and need the same four languages.

## Provenance

The mark is the original `laiive1.png` outline, recoloured pixel-for-pixel —
never redrawn. Palette derives from the previous system (`#FF2AA0` unchanged);
`#FFD500` and `#FF8C00` were retired, `#00CFEA` moved to the promoter side.
Type moves from Montserrat 700 + IBM Plex Sans to Bebas Neue + DM Sans, both
SIL OFL, with IBM Plex Mono for labels.
