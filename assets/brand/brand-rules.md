# laiive brand rules — enforceable list

Version 1 · direction **4a** (consumer) + **3b** (promoter) · august 2026.
Normative document: `brand-guide.pdf`. This file is the short version an agent
can check work against. When this file and the PDF disagree, the PDF wins.

## Locked — do not change without the brand owner

- **The mark outline.** Every mark file is the exact silhouette of the original
  `laiive1.png`, recoloured pixel-for-pixel. Never redraw, re-trace, rotate,
  outline, gradient, or place it in a circle it wasn't supplied in.
- **Fuchsia leads.** `#FF2AA0` is the brand colour.
- **Dark-first.** There is no light mode. Ground is `#0C0A0A`.
- **Lowercase `laiive`** in body copy; `LAIIVE` only as the wordmark.

## Product surface

- **Chat is the app.** No tab bar, no home screen, no titles row, no section
  headers, no onboarding copy, no explanatory text about the AI.
- The entire chrome inventory: bare mark + `LAIIVE` top-left; saved then
  account icon top-right (icons only, no labels); one `+` at the composer that
  opens **voice input and nothing else**; the composer, placeholder `ask`.
- Filters, city, date and price are **said**, not selected. An understood
  constraint is echoed in the answer, never rendered as a chip.
- Language and preferences live in **settings, inside the account menu** — never
  in a header.
- `saved` has no feature behind it yet; the icon ships anyway so the bar is final.
- Touch targets ≥ 44px. Nothing square: pills 999px, event cards 20px, sheets 26px.

## Colour means something

| Colour | Means | Never |
|---|---|---|
| `#FF2AA0` fuchsia | brand, and “free” | a background for body text |
| `#FFB100` amber | price, mic, tickets, the card rail | answer text, if it is also on pills |
| `#00CFEA` cyan | promoter side only: PRO badge, focus, “in review” | anywhere in the consumer app |
| `#E72828` red | errors, delete | a highlight |
| `#F4EDE2` cream | every answer laiive gives | card titles (those are `#FFFFFF`) |

- **Never white text on fuchsia or amber below 18px** — 3.45:1, fails. Use
  `#0C0A0A` (6.1:1).
- Body and UI text ≥ 4.5:1; icons and decorative shapes ≥ 3:1.
- Composer placeholder floor is `#A79797`. Nothing dimmer anywhere.
- No gradients, no glows, no yellow, no orange. Those tokens were deleted.

## Type

- **Bebas Neue** — wordmark (24–54px, +0.04em) and event titles (18px, +0.03em),
  caps only. Never body copy, never a label, never below 16px.
- **DM Sans** — answers 15px/1.5, user messages 14.5px/1.4, card meta 12.5px,
  pills 11px/700.
- **IBM Plex Mono** — labels, hex values, status pills, technical chrome only.

## Voice

- Second person, present tense, short. Answer first, reason second. Numbers only
  when they change a decision (price, door time, walking distance).
- Reference line: *“Three rooms worth leaving the house for tonight.”*
- Banned: “discover”, “curated”, “unlock”, “experiences”, feed/engagement
  language, exclamation marks.
- Error and empty states are answers, not apologies: offer the next real option,
  never “try again”, never an error code on the consumer side, never a
  permission nag.

## Promoter (pro) specifics

- Same ground as consumer (`#0C0A0A`), conversation **flat** on the page — no
  chat panel.
- The event-details form is the one place allowed a visible frame: `#241B1B`,
  20px radius, 1.5px `rgba(244,237,226,.32)`.
- Fuchsia does not appear below the header. Cyan is the PRO badge, the focus
  ring, the card edge and “in review”.
- Composer icons are warm-neutral, never accent-filled.
- Primary action (`publish to laiive`) is cream `#F4EDE2` with `#0C0A0A` ink.
- Required-field markers are amber (`needs you`), missing fields go red on both
  label and border, and the publish button disables with a fill hint — this
  mirrors `EventForm.tsx`, where REQUIRED = artists, start_at, venue, address,
  city, price_min.
- Status is always a tinted pill (10% fill, 40% border, full-strength text) and
  always carries its word — never a bare dot.

## Files

- Marks, app icons and the OG ground: this folder, `mark-*.png`,
  `appicon-1024-*.png`, `og-base-1200x630.png`. Filenames are the contract.
- Icon set: `icons.svg` (14 symbols, 24px grid, 1.7px stroke, round caps).
  If a screen needs a fifteenth icon, the screen is doing too much.
- Reference implementations: `reference-screens.html` (consumer chat + pro
  submit, static markup with the real hex values and spacing).
- Tokens: `brand-tokens.css` — drop-in for the `:root` block of
  `frontend/src/index.css`.
