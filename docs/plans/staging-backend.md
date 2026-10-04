---
status: todo
step: launch
next: decide whether preview publishes may write to the production graph
---
# Staging backend

None exists. `VITE_API_URL` is one Pages variable pointing at the production gateway, so a
frontend change needing a new route 404s until the services deploy.

## Steps
- [ ] Decide: may preview publishes write to the production graph?
- [ ] A second gateway, pusher and retriever on Fly; point Pages previews at them.
