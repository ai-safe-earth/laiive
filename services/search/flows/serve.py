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
    from flows.city_sweep import BERGAMO_PROVINCE, TORINO_PROVINCE, city_sweep
except ImportError:
    from backfill import backfill  # type: ignore[no-redef]
    from city_sweep import (  # type: ignore[no-redef]
        BERGAMO_PROVINCE,
        TORINO_PROVINCE,
        city_sweep,
    )

from prefect import serve
from prefect.schedules import Cron

if __name__ == "__main__":
    serve(
        # One deployment per province rather than one sweep of both: the flow
        # runs its cities sequentially at minutes each, so twenty towns in one
        # run is over an hour in which any failure is reported against a single
        # run. Split, each province gets its own history and its own retry, and
        # the two never overlap on Tavily and OpenAI.
        #
        # Tue/Thu 07:00, clear of the nightly backfill at 04:30 — which is the
        # other Tavily spender, one search per venue it cannot geocode.
        city_sweep.to_deployment(
            name="bergamo-province-weekly",
            parameters={"cities": BERGAMO_PROVINCE},
            schedule=Cron("0 4 * * 3", timezone="Europe/Madrid"),
        ),
        city_sweep.to_deployment(
            name="torino-province-weekly",
            parameters={"cities": TORINO_PROVINCE},
            schedule=Cron("0 7 * * 3", timezone="Europe/Madrid"),
        ),
        backfill.to_deployment(
            name="backfill-nightly",
            schedule=Cron("30 4 * * 1", timezone="Europe/Madrid"),
        ),
    )
