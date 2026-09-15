# laiive brand rules — enforceable list

Version 1.1 · direction **4a** (consumer) + **3b** (promoter) · august 2026 ·
composer + claim-invitation amendments 2026-08-25.
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
  account icon top-right (icons only, no labels); the composer, placeholder
  `ask`.
- **The composer, both surfaces** (order amended 2026-09-15): attach, field,
  mic, send — the two controls that act on what you just typed sit next to it,
  as they do in every other chat app. The field is a pill at one line and grows
  with the message to six, then scrolls; enter sends, shift+enter breaks the
  line. The send is filled with the surface's accent — fuchsia on the consumer
  side, cyan on pro, dark ink on both — and **keeps it at 45% while it waits**
  rather than taking the grey disabled fill: the send is never the colourless
  control in the row. The accent belongs to the send alone; the mic never wears
  it. While a reply streams the send slot is stop. Voice is the mic itself;
  there is no `+`. Attach exists on pro only, warm-neutral, first in the row.
- **A live mic is amber** (`#FFB100`, dark ink, pulsing) and puts a bar meter
  (`▁▂▃▄▅▆▇`, amber, mono) inside the field it is dictating into. The meter is
  decoration — `aria-hidden` — because the button already says "stop and
  transcribe". Amber is the only accent the mic may wear, and only while live.
- **The account chip** is two characters on the surface's accent with dark ink:
  first and last word of the display name, or the first two letters when there
  is only one word. No initials at all (no name, no email) keeps the outline
  account icon instead.
- Filters, city, date and price are **said**, not selected. An understood
  constraint is echoed in the answer, never rendered as a chip.
- Language and preferences live in **settings, inside the account menu** — never
  in a header.
- `saved` opens the saved list. The same glyph is the pill on a card; saved is carried
  by colour and by the label, never by a filled bookmark — the symbol sets `fill="none"`
  on itself, which no rule in the page can reach.
- Touch targets ≥ 44px. Nothing square: pills 999px, event cards 20px, sheets 26px.

## Colour means something

| Colour | Means | Never |
|---|---|---|
| `#FF2AA0` fuchsia | brand, “free”, the consumer composer’s filled send, and the account chip | a background for body text; the mic |
| `#FFB100` amber | price, tickets, the card rail, a live mic | answer text, if it is also on pills |
| `#00CFEA` cyan | promoter side only: PRO badge, focus, “in review”, the composer’s filled send | anywhere in the consumer app; the mic |
| `#E72828` red | errors, delete; the web-sourced card mark and the claim invitation under it (the one exception) | a highlight |
| `#F4EDE2` cream | every answer laiive gives | card titles (those are `#FFFFFF`) |

- **Never white text on fuchsia or amber below 18px** — 3.45:1, fails. Use
  `#0C0A0A` (6.1:1).
- Body and UI text ≥ 4.5:1; icons and decorative shapes ≥ 3:1.
- Composer placeholder floor is `#A79797`. Nothing dimmer anywhere.
- No gradients, no glows, no yellow, no orange. Those tokens were deleted.

## Type

One rem scale, `theme.fontSize` in `frontend/tailwind.config.ts`. Use the token
names only — never `text-[Npx]`: px ignores the phone's text-size setting, and
the reference screens were drawn at sizes that read fine on a monitor and not
on a 5.5" screen (lifted 2026-08-28).

| token | px | role |
|---|---|---|
| `2xs` | 11 | promoter and admin badges and status pills only |
| `xs` | 12.5 | mono section labels and the role line (+0.11em caps) |
| `sm` | 14 | secondary copy, card pills, price badge (700), status lines, account chip |
| `md` | 15 | buttons, chips, UI copy, toasts, card meta (lifted 2026-09-15) |
| `base` | 16 | every input — below 16px iOS zooms the page on focus |
| `lg` | 17 | your own messages in the chat, 1.45 leading (lifted 2026-09-15) |
| `xl` | 18 | answers, 1.55 leading (lifted 2026-09-15) |
| `2xl` | 21 | section heads; Bebas event titles (+0.03em, lifted 2026-09-15) |
| `3xl` | 24 | page titles, wordmark (the wordmark alone may go up to 54px) |
| `4xl` | 28 | pro watermark |

- **Bebas Neue** — wordmark (+0.04em) and event titles, caps only. Never body
  copy, never a label, never below `xl`.
- **DM Sans** — everything else.
- **IBM Plex Mono** — labels, hex values, status pills, technical chrome only.
- Touch targets ≥ 44px on every consumer and promoter control; admin screens
  are desktop tools and exempt.

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

- Its own ground, one step warmer than consumer (`--pro-bg #14100F`), conversation
  **flat** on the page — no chat panel. Controls are **filled** (`--pro-control`): an
  empty pill reads as a hole over the watermark.
- The event-details form is the one place allowed a visible frame: `#241B1B`,
  20px radius, 1.5px `rgba(244,237,226,.32)`.
- Fuchsia does not appear below the header. Cyan is the PRO badge, the focus
  ring, the card edge and “in review”.
- The composer accent is cyan and lives on the filled send alone. The mic and
  the attach control stay warm-neutral, and on this surface they are **filled**
  (`#282220`, as is the field) rather than transparent: the promoter ground
  carries the watermark, and an unfilled pill on it reads as a hole in the
  lettering instead of a control.
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
