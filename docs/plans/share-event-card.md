---
status: active
step: launch
next: push feat/share-event-card and open a PR
---
# Share event card

Branch `feat/share-event-card` (`01baeee`, `555fa08`), local, unpushed.
Share icon on the card: WhatsApp, Instagram (copies + opens the app), Facebook (sheet on
phones), device sheet, copy link. The link is `laiive.com/?event=<uid>`.

## Steps
- [ ] Push and PR.
- [ ] `/api/events` becomes anonymous GET-only; the live gateway still answers 401. Deploy the
      gateway before or with the SPA.
- [ ] Add a Simple Icons (CC0) line to `THIRD_PARTY_NOTICES.md`.
- [ ] Test on real phones: WhatsApp from iPhone Safari, the Facebook icon on an iPhone with the
      app, a link inside Instagram's in-app browser on Android.
