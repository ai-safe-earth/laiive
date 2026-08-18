"""Poll a report until its background worker finishes (the 202+poll shape).

Sweep and backfill answer 202 immediately and land their results on the
report row; the flow's only long wait is this loop of short GETs, which no
PaaS proxy idle-timeout can cut.
"""

import time

import httpx

TERMINAL = {"dry_run", "approved", "failed", "done"}
POLL_INTERVAL = 15.0
POLL_DEADLINE = 1500.0
GET_TIMEOUT = 30.0


def wait_for_report(
    gateway: str,
    report_id: str,
    jwt: str,
    interval: float = POLL_INTERVAL,
    deadline: float = POLL_DEADLINE,
) -> dict:
    elapsed = 0.0
    while True:
        response = httpx.get(
            f"{gateway}/api/admin/search/reports/{report_id}",
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=GET_TIMEOUT,
        )
        response.raise_for_status()
        report: dict = response.json()
        status = report.get("status")
        if status == "failed":
            error = report.get("error") or "no error recorded"
            raise RuntimeError(f"Report {report_id} failed: {error}")
        if status in TERMINAL:
            return report
        if elapsed >= deadline:
            raise TimeoutError(
                f"Report {report_id} still '{status}' after {int(deadline)}s"
            )
        time.sleep(interval)
        elapsed += interval
