---
status: todo
step: self-improvement
next: wait for traffic and feedback volume
---
# Self-improvement loop (program phase 7)

Traces + response capture + user feedback -> filtered candidate cases -> a nightly eval run ->
a report that opens an issue when a metric regresses and proposes prompt or model
candidates. Those ship only through the offline gate plus a human approve.

Needs the eval infrastructure and real volume first. Possible repo skills: `analyze-turn`,
`eval-report`, `sweep-quality`.
