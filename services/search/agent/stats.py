"""Aggregated numbers for the admin dashboard — one GET, one payload.

Lives on the search service because it already holds both credentials the
numbers come from (the Supabase service-role key and the Neo4j driver), so
the gateway's admin proxy covers it with zero new routes there. One call
answers the whole dashboard because the gateway rate limit is per-user across
all of /api/* — a dashboard that browses its own sections into a 429 is worse
than none.

Sections degrade independently: a paused Aura or an unreachable Prefect Cloud
turns its section into an error note, never a 502 for the queue counts the
screen is mostly there to show.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger

from config import settings

from . import graph, reports
from .learning import _get as store_get

# Reports considered for counts and trends: everything inside the credit
# chart's eight weeks (a TIME window — a row cap alone undercounts the budget
# once a month out-sweeps it) plus every still-waiting report whatever its
# age. The row cap is only a runaway guard.
REPORT_WINDOW = 500
CREDIT_WEEKS = 8

TAVILY_MONTHLY_BUDGET = 1000

# How long a Scheduled run may sit past its expected start before the
# scheduler is called dead. serve() polls every few seconds when it runs at
# all, so fifteen minutes late means nothing is polling.
LATE_GRACE = timedelta(minutes=15)

_prefect = httpx.Client(timeout=5.0)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fold_write_summary(write_results: list | None) -> dict[str, int]:
    """write_results rows → {created: n, duplicate: n, ...}."""
    counts = Counter(
        row.get("status") or "unknown"
        for row in (write_results or [])
        if isinstance(row, dict)
    )
    return dict(counts)


def reports_summary(rows: list[dict]) -> dict:
    by_status = Counter(row.get("status") or "unknown" for row in rows)
    backlog = [row for row in rows if row.get("status") == "dry_run"]
    oldest = min(
        (row.get("created_at") for row in backlog if row.get("created_at")),
        default=None,
    )
    return {
        "by_status": dict(by_status),
        "backlog": {
            "count": len(backlog),
            "candidates": sum(
                int((row.get("stats") or {}).get("candidates") or 0) for row in backlog
            ),
            "oldest_created_at": oldest,
        },
        "recent": [
            {
                "id": row.get("id"),
                "city": row.get("city"),
                "kind": row.get("kind"),
                "status": row.get("status"),
                "created_at": row.get("created_at"),
                "approved_at": row.get("approved_at"),
                "stats": row.get("stats") or {},
                "write_summary": fold_write_summary(row.get("write_results")),
            }
            for row in rows[:25]
        ],
    }


def credits_summary(rows: list[dict], now: datetime) -> dict:
    """Tavily spend, read off the reports because that is where each sweep
    already records what it cost — a monthly allowance nobody can see is one
    nobody notices spending."""
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_to_date = 0
    by_week: dict[str, int] = {}
    week_floor = now - timedelta(weeks=8)
    for row in rows:
        created = _parse_ts(row.get("created_at"))
        if created is None:
            continue
        credits = int((row.get("stats") or {}).get("tavily_credits") or 0)
        if created >= month_start:
            month_to_date += credits
        if created >= week_floor:
            year, week, _ = created.isocalendar()
            key = f"{year}-W{week:02d}"
            by_week[key] = by_week.get(key, 0) + credits
    elapsed_days = max((now - month_start).days + 1, 1)
    # Days in this month, without reaching for calendar: the 28th + 4 days is
    # always next month, whose day-1 minus one day is this month's last.
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    days_in_month = (next_month - month_start).days
    return {
        "month_to_date": month_to_date,
        "budget": TAVILY_MONTHLY_BUDGET,
        "projected_month_end": round(month_to_date / elapsed_days * days_in_month),
        "by_week": [
            {"week": week, "credits": by_week[week]} for week in sorted(by_week)
        ],
    }


def sources_summary(rows: list[dict]) -> dict:
    def yield_of(row: dict) -> float:
        pages = float(row.get("pages") or 0.0)
        return (
            round(float(row.get("pages_with_events") or 0.0) / pages, 3)
            if pages
            else 0.0
        )

    return {
        "counts_by_status": dict(
            Counter(row.get("status") or "candidate" for row in rows)
        ),
        "top": [
            {
                "domain": row.get("domain"),
                "status": row.get("status"),
                "pages": round(float(row.get("pages") or 0.0), 1),
                "yield": yield_of(row),
                "candidates_new": round(float(row.get("candidates_new") or 0.0), 1),
                "events_written": round(float(row.get("events_written") or 0.0), 1),
            }
            for row in rows[:15]
        ],
    }


def queries_summary(rows: list[dict]) -> dict:
    def entry(row: dict) -> dict:
        return {
            "template": row.get("template"),
            "runs": int(row.get("runs") or 0),
            "pages_with_events": round(float(row.get("pages_with_events") or 0.0), 1),
            "candidates_new": round(float(row.get("candidates_new") or 0.0), 1),
        }

    by_status: dict[str, list[dict]] = {"standing": [], "trial": []}
    retired = 0
    for row in rows:
        status = row.get("status") or "trial"
        if status == "retired":
            retired += 1
        elif status in by_status:
            by_status[status].append(entry(row))
    return {**by_status, "retired_count": retired}


def graph_summary() -> dict:
    """Exactly what the dashboard renders, and nothing it drops on the floor —
    every read here is a scan of a paused-prone Aura free instance."""
    with graph._driver.session(database=settings.neo4j_database) as session:
        quality = session.run(
            "MATCH (e:Event) RETURN count(*) AS events, "
            "avg(CASE WHEN coalesce(e.start_time_known, true) THEN 1.0 ELSE 0.0 END)"
            " AS time_known, "
            "avg(CASE WHEN e.price_min IS NOT NULL THEN 1.0 ELSE 0.0 END)"
            " AS price_known"
        ).single()
        venues = session.run("MATCH (v:Venue) RETURN count(v) AS n").single()
        artists = session.run("MATCH (a:Artist) RETURN count(a) AS n").single()
        per_day = [
            {"day": str(record["day"]), "count": record["n"]}
            for record in session.run(
                "MATCH (e:Event) WHERE e.created_at >= datetime() - duration('P30D') "
                "RETURN date(e.created_at) AS day, count(*) AS n ORDER BY day"
            )
        ]
    events = quality["events"] if quality else 0
    return {
        "events": events,
        "venues": venues["n"] if venues else 0,
        "artists": artists["n"] if artists else 0,
        "events_last_30d": per_day,
        "quality": {
            "start_time_known_pct": round((quality["time_known"] or 0.0) * 100)
            if quality and events
            else None,
            "price_known_pct": round((quality["price_known"] or 0.0) * 100)
            if quality and events
            else None,
        },
    }


def scheduler_status(now: datetime) -> dict:
    """What Prefect Cloud believes about the schedules — which is what fires.

    READY deployments prove registration, not execution: serve() re-asserts
    its crons on every restart and then has to keep polling. The Late check is
    the execution half — a run sitting Scheduled past its start plus grace
    means nothing is polling, whatever the deployment status says.
    """
    if not (settings.prefect_api_url and settings.prefect_api_key):
        return {
            "configured": False,
            "alive": False,
            "reason": "unconfigured",
            "deployments": [],
        }
    # Everything below — the calls AND the payload parsing — is one guarded
    # unit: Prefect changing a field shape must degrade this section, never
    # 500 the dashboard.
    try:
        base = settings.prefect_api_url.rstrip("/")
        headers = {"Authorization": f"Bearer {settings.prefect_api_key}"}
        response = _prefect.post(
            f"{base}/deployments/filter", headers=headers, json={"limit": 20}
        )
        response.raise_for_status()
        deployments = response.json()

        response = _prefect.post(
            f"{base}/flow_runs/filter",
            headers=headers,
            json={
                "flow_runs": {"state": {"type": {"any_": ["SCHEDULED"]}}},
                "sort": "EXPECTED_START_TIME_ASC",
                "limit": 20,
            },
        )
        response.raise_for_status()
        scheduled = response.json()

        response = _prefect.post(
            f"{base}/flow_runs/filter",
            headers=headers,
            json={
                "flow_runs": {
                    "state": {"type": {"any_": ["COMPLETED", "FAILED", "CRASHED"]}}
                },
                "sort": "START_TIME_DESC",
                "limit": 20,
            },
        )
        response.raise_for_status()
        finished = response.json()

        next_by_deployment: dict[str, dict] = {}
        stale_runs = 0
        for run in scheduled:
            deployment_id = run.get("deployment_id")
            expected = _parse_ts(run.get("expected_start_time"))
            # Our own clock decides staleness, not Prefect's Late-marker
            # service: a run still labelled "Scheduled" hours past its start
            # is exactly the dead-serve() state this panel exists to catch.
            if expected is not None and now - expected > LATE_GRACE:
                stale_runs += 1
            elif deployment_id and deployment_id not in next_by_deployment:
                # First run that is actually upcoming — a past-dated late run
                # must not render as a live "next" time.
                next_by_deployment[deployment_id] = run

        last_by_deployment: dict[str, dict] = {}
        for run in finished:
            deployment_id = run.get("deployment_id")
            if deployment_id and deployment_id not in last_by_deployment:
                last_by_deployment[deployment_id] = run

        rows = []
        all_ready = True
        for deployment in deployments:
            ready = deployment.get("status") == "READY"
            all_ready = all_ready and ready
            schedules = deployment.get("schedules") or []
            cron = None
            for entry in schedules:
                cron = (entry.get("schedule") or {}).get("cron")
                if cron:
                    break
            upcoming = next_by_deployment.get(deployment.get("id"))
            last = last_by_deployment.get(deployment.get("id"))
            rows.append(
                {
                    "name": deployment.get("name"),
                    "status": deployment.get("status"),
                    "cron": cron,
                    "next_run": (upcoming or {}).get("expected_start_time"),
                    "last_run_state": ((last or {}).get("state") or {}).get("type"),
                    "last_run_at": (last or {}).get("start_time"),
                }
            )
    except Exception as e:
        logger.warning(f"Prefect Cloud unreachable for the scheduler panel: {e}")
        return {
            "configured": True,
            "alive": False,
            "reason": "unreachable",
            "error": str(e),
            "deployments": [],
        }

    # One verdict, but the reason travels with it: "nothing is polling" is a
    # claim the UI must only make when stale runs prove it — an empty
    # workspace and a Prefect blip are different sentences.
    if not deployments:
        reason = "no_deployments"
    elif stale_runs:
        reason = "stale_runs"
    elif not all_ready:
        reason = "not_ready"
    else:
        reason = None
    return {
        "configured": True,
        "alive": reason is None,
        "reason": reason,
        "stale_runs": stale_runs,
        "deployments": rows,
    }


def build() -> dict:
    """The whole dashboard payload.

    The report read raises (a dashboard with no queue counts is no
    dashboard); every other section degrades in place, keeping its shape —
    Aura pauses, Supabase 401s and Prefect blips are routine here and must
    not blank the screen. The five sections are independent network waits,
    so they run concurrently rather than stacking their timeouts.
    """
    now = datetime.now(timezone.utc)
    since = (now - timedelta(weeks=CREDIT_WEEKS)).isoformat()
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows_future = pool.submit(reports.stats_rows, REPORT_WINDOW, since)
        sources_future = pool.submit(
            store_get,
            "search_sources",
            {"select": "*", "order": "candidates_new.desc", "limit": "100"},
        )
        queries_future = pool.submit(
            store_get,
            "search_queries",
            {"select": "*", "order": "candidates_new.desc", "limit": "100"},
        )
        graph_future = pool.submit(graph_summary)
        scheduler_future = pool.submit(scheduler_status, now)

        rows = rows_future.result()  # ReportStoreError -> the 502 handler
        try:
            sources_section = sources_summary(sources_future.result())
        except Exception as e:
            logger.warning(f"Source ranking unreadable for the dashboard: {e}")
            sources_section = {"counts_by_status": {}, "top": [], "error": str(e)}
        try:
            queries_section = queries_summary(queries_future.result())
        except Exception as e:
            logger.warning(f"Query ranking unreadable for the dashboard: {e}")
            queries_section = {
                "standing": [],
                "trial": [],
                "retired_count": 0,
                "error": str(e),
            }
        try:
            graph_section: dict = graph_future.result()
        except Exception as e:
            logger.warning(f"Graph unreachable for the dashboard: {e}")
            graph_section = {"error": str(e)}
        scheduler_section = scheduler_future.result()  # degrades internally

    return {
        "generated_at": now.isoformat(),
        "window": REPORT_WINDOW,
        "reports": reports_summary(rows),
        "credits": credits_summary(rows, now),
        "sources": sources_section,
        "queries": queries_section,
        "graph": graph_section,
        "scheduler": scheduler_section,
    }
