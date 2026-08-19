"""Weekly per-city discovery sweep — one Prefect task per city (D17).

Per-city tasks give per-city retries and run history; the markdown artifact
is the human review surface. Sweeps stay dry-run — approving a report is a
human action on POST /api/admin/search/reports/{id}/approve, never this flow.
"""

import httpx
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact

# Prefect loads the entrypoint as a top-level module; whether `flows/` or its
# parent ends up on sys.path depends on how the file was loaded.
try:
    from flows.auth import gateway_url, get_admin_jwt
    from flows.polling import wait_for_report
except ImportError:
    from auth import gateway_url, get_admin_jwt  # type: ignore[no-redef]
    from polling import wait_for_report  # type: ignore[no-redef]

DEFAULT_CITIES = ["Madrid", "Barcelona", "Berlin"]

# /sweep answers 202 in well under a minute; the sweep itself (2-6 min live)
# runs in the service's background and lands on the report we then poll.
REQUEST_TIMEOUT = 60.0


@task(retries=2, retry_delay_seconds=120, timeout_seconds=1800)
def sweep_city(city: str, max_pages: int | None = None) -> dict:
    # The JWT is minted inside the task so it is never a task parameter
    # (Prefect surfaces those in the UI) and so a retry gets a fresh one.
    gateway = gateway_url()
    jwt = get_admin_jwt()
    body: dict = {"city": city}
    if max_pages is not None:
        body["max_pages"] = max_pages
    response = httpx.post(
        f"{gateway}/api/admin/search/sweep",
        json=body,
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    report_id: str = response.json()["report_id"]
    report = wait_for_report(gateway, report_id, jwt)
    return {
        "city": report.get("city") or city,
        "report_id": report_id,
        "stats": report.get("stats") or {},
        "candidates": report.get("candidates") or [],
    }


def render_report(results: list[dict], failures: dict[str, str]) -> str:
    """Markdown artifact body: per-city stats + the new candidates to review."""
    lines = ["# City sweep — dry run", ""]
    for r in results:
        stats = r.get("stats") or {}
        lines += [
            f"## {r.get('city', '?')} — report `{r.get('report_id', '?')}`",
            "",
            f"- pages: {stats.get('pages_searched', 0)} searched, "
            f"{stats.get('pages_with_events', 0)} with events; "
            f"drafts: {stats.get('drafts_extracted', 0)} "
            f"({stats.get('skipped_past', 0)} past, filtered)",
            f"- candidates: {stats.get('candidates', 0)} — "
            f"new {stats.get('new', 0)}, exists {stats.get('exists', 0)}, "
            f"similar {stats.get('similar', 0)}",
            "",
        ]
        new = [c for c in (r.get("candidates") or []) if c.get("dedup_status") == "new"]
        if new:
            lines += [
                "| name | start | venue | missing |",
                "| --- | --- | --- | --- |",
            ]
            for c in new:
                draft = c.get("draft") or {}
                lines.append(
                    f"| {draft.get('name') or '—'} "
                    f"| {draft.get('start_at') or '—'} "
                    f"| {draft.get('venue') or '—'} "
                    f"| {', '.join(c.get('missing') or []) or '—'} |"
                )
            lines.append("")
        lines += [
            "Approve: `POST /api/admin/search/reports/"
            f"{r.get('report_id', '?')}/approve`",
            "",
        ]
    if failures:
        lines += ["## Failed cities", ""]
        lines += [f"- **{city}**: {error}" for city, error in failures.items()]
        lines.append("")
    return "\n".join(lines)


@flow(name="city-sweep")
def city_sweep(cities: list[str] | None = None, max_pages: int | None = None) -> dict:
    """Sweep each city in turn (sequential — the search endpoint is a
    minutes-long synchronous call; concurrent sweeps would stack Tavily and
    OpenAI load for no schedule benefit)."""
    cities = cities or DEFAULT_CITIES
    results: list[dict] = []
    failures: dict[str, str] = {}
    for city in cities:
        try:
            results.append(sweep_city(city, max_pages))
        except Exception as e:  # noqa: BLE001 — one bad city must not eat the sweep
            failures[city] = str(e)

    create_markdown_artifact(
        key="city-sweep",
        markdown=render_report(results, failures),
        description="Dry-run sweep report — review, then approve via the API",
    )
    if failures:
        raise RuntimeError(f"Sweep failed for: {', '.join(failures)}")
    return {
        "reports": [
            {"city": r.get("city"), "report_id": r.get("report_id")} for r in results
        ]
    }


if __name__ == "__main__":
    city_sweep()
