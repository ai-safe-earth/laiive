"""Run the schedules from this machine, Prefect Cloud only sees the calendar.

`prefect.yaml`'s `git_clone` pull step needs a managed work pool, which has no
private networking — so it needed a public gateway URL and a `github-laiive-pat`
Secret block neither of which exist yet (Phase 6 rethink, handoff.md). `serve()`
needs none of that: it registers both deployments' schedules with Prefect Cloud
and then blocks, executing runs in this process against whatever `GATEWAY_URL`
resolves to (default `http://127.0.0.1:8000`, i.e. the local stack). No work
pool, no worker, no image, no PAT — the trade-off is that schedules only fire
while this process and the stack are up; a missed run shows Late in the Cloud UI.

Same dual-import guard as city_sweep.py / backfill.py: Prefect (and a bare
`python flows/serve.py`) can load this as a top-level module with either
`flows/` or its parent on sys.path.
"""

try:
    from flows.backfill import backfill
    from flows.city_sweep import city_sweep
except ImportError:
    from backfill import backfill  # type: ignore[no-redef]
    from city_sweep import city_sweep  # type: ignore[no-redef]

from prefect import serve
from prefect.schedules import Cron

if __name__ == "__main__":
    serve(
        city_sweep.to_deployment(
            name="city-sweep-weekly",
            schedule=Cron("0 6 * * 1", timezone="Europe/Madrid"),
        ),
        backfill.to_deployment(
            name="backfill-nightly",
            schedule=Cron("30 4 * * *", timezone="Europe/Madrid"),
        ),
    )
