---
status: todo
step: supply
next: start services/search/flows/serve.py against the public gateway
---
# Scheduler

`services/search/flows/serve.py` is not running, so no sweep schedule fires.

## Steps
- [ ] Run `serve.py` with `GATEWAY_URL=https://laiive-gateway.fly.dev` in the root `.env`.
- [ ] On first run, delete the stale `backfill-nightly` deployment in Prefect Cloud by hand.
- [ ] Per-city schedules and priorities, report retention, an alert when sweep quality drops
      below the baselines in `evals-and-monitoring.md`.
- [ ] Optional: containerize `serve.py`, or move `prefect.yaml` to a managed pool.
