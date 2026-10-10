---
status: todo
step: retrieval
next: owner approves the design, then step 1
---
# Follow-up context: what carries over to the next query

Owner, 2026-10-10: a follow-up must decide which details carry over to the next
query, or whether it is a new query. Today the classifier re-reads the chat text and
re-emits the whole search. After a "nothing found" reply it often forgets the town
(two open gaps in the classifier set: `the-city-carries-through-other-concerts`,
`a-named-show-keeps-the-place`). A prompt line passed 1 run in 3.

## Design (proposed)
- Each turn's search details (city, venue, genre, dates, radius...) go back to the
  chat in a new `context` frame. The chat keeps them on that answer and sends them
  back with the history. The server stays stateless.
- The classifier gets "previous search: {...}" and decides per turn:
  `refinement` (keep, then change what this turn says) or `new_topic` (start clean).
- `enforce()` does the merge in code: on a refinement, every field this turn left
  empty is copied from the previous search. The model only says what changed.
- Rejected: storing it on the server (Redis by conversation): the server has no
  conversation id, and a lost key would silently drop the context.
- Cost: one protocol change (new frame + one optional request field, TS mirror).

## Steps
- [ ] 1. Protocol: `Context` frame and `previous` request field, Python + TS mirror.
- [ ] 2. Classifier: previous search in the prompt; merge in `enforce()`.
- [ ] 3. Chat: keep the frame on the message, send the latest one back.
- [ ] 4. The two open gaps pass three runs in a row; replay the conversation thread.
