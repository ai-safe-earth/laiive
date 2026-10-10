---
status: done
step: retrieval
next: none; merge after #147
---
# Follow-up context: what carries over to the next query

Owner, 2026-10-10: a follow-up must decide which details carry over to the next
query, or whether it is a new query. Today the classifier re-reads the chat text and
re-emits the whole search. After a "nothing found" reply it often forgets the town
(two open gaps in the classifier set: `the-city-carries-through-other-concerts`,
`a-named-show-keeps-the-place`). A prompt line passed 1 run in 3.

## Design (approved by the owner, 2026-10-10; first in the fix order)
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
- [x] 1. Protocol: `Context` frame and `previous` request field, Python + TS mirror.
- [x] 2. Classifier: previous search in the prompt; merge in `enforce()`.
- [x] 3. Chat: keep the frame on the message, send the latest one back.
- [x] 4. The two open gaps pass three runs in a row (done: 3 of 3, then 6 of 6).
      Not done: a replay of the conversation thread, because the logged turns
      carry no `previous`; the classifier cases stand in for it.

## Decisions (2026-10-10)
- Frame `search.context` and request field `previous`, the same round trip as the
  pusher's `walk.state`. The chat sends the latest assistant answer that has one,
  so a "thanks" in between does not reset the search.
- Merged in groups: place (city, country, venue, near me), radius, dates, genre,
  artist, venue type, free text, price. A group the turn touches is not refilled,
  so "and in Torino?" after a venue in Bergamo drops the venue.
- `cleared` names what the turn removes ("any genre"), so the merge does not put
  it back.
- `previous` is client input: only known fields survive, strings are cut to 80
  characters, and never `query_text` or `needs_custom_cypher`.
- Side fix found by the live runs: an ambiguous search the model left empty
  ("any events today?" without a location) now still asks with the button, and
  the prompt says an ambiguous search keeps what was said (prompt v6).
- Live classifier, prompt v6: 33 of 33 in 5 of the last 6 runs; the one failure
  was `towns-around-a-place` leaving out the radius once.
