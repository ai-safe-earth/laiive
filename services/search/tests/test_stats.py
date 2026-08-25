"""The dashboard aggregation: pure folds, the scheduler verdict, one call."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from agent import stats
from agent.api import app
from conftest import http_response
from fastapi.testclient import TestClient

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def report(
    created,
    status="dry_run",
    credits=0,
    candidates=0,
    write_results=None,
    kind="sweep",
):
    return {
        "id": "r",
        "city": "Bergamo",
        "kind": kind,
        "status": status,
        "created_at": created,
        "approved_at": None,
        "stats": {"tavily_credits": credits, "candidates": candidates},
        "write_results": write_results,
    }


def test_credits_fold_month_to_date_and_weeks():
    rows = [
        report("2026-08-25T08:00:00+00:00", credits=6),
        report("2026-08-18T08:00:00+00:00", credits=5),
        report("2026-07-30T08:00:00+00:00", credits=7),  # last month, recent week
    ]
    summary = stats.credits_summary(rows, NOW)
    assert summary["month_to_date"] == 11
    assert summary["budget"] == 1000
    assert summary["projected_month_end"] == round(11 / 25 * 31)
    assert {"week": "2026-W35", "credits": 6} in summary["by_week"]
    assert {"week": "2026-W31", "credits": 7} in summary["by_week"]


def test_reports_fold_backlog_and_write_outcomes():
    rows = [
        report("2026-08-25T08:00:00+00:00", candidates=12),
        report(
            "2026-08-20T08:00:00+00:00",
            status="approved",
            write_results=[
                {"status": "created"},
                {"status": "created"},
                {"status": "duplicate"},
            ],
        ),
        report("2026-08-24T08:00:00+00:00", candidates=5),
    ]
    summary = stats.reports_summary(rows)
    assert summary["by_status"] == {"dry_run": 2, "approved": 1}
    assert summary["backlog"]["count"] == 2
    assert summary["backlog"]["candidates"] == 17
    # The oldest waiting report, not the oldest row: staleness is what the
    # number warns about.
    assert summary["backlog"]["oldest_created_at"] == "2026-08-24T08:00:00+00:00"
    approved = next(r for r in summary["recent"] if r["status"] == "approved")
    assert approved["write_summary"] == {"created": 2, "duplicate": 1}


def test_scheduler_unconfigured_says_so(monkeypatch):
    monkeypatch.setattr(stats.settings, "prefect_api_url", "")
    assert stats.scheduler_status(NOW) == {
        "configured": False,
        "alive": False,
        "reason": "unconfigured",
        "deployments": [],
    }


def _prefect_fake(deployments, scheduled, finished):
    http = MagicMock()
    http.post.side_effect = [
        http_response(200, deployments),
        http_response(200, scheduled),
        http_response(200, finished),
    ]
    return http


DEPLOYMENT = {
    "id": "d1",
    "name": "bergamo-province-weekly",
    "status": "READY",
    "schedules": [{"schedule": {"cron": "0 7 * * 2"}}],
}


def test_scheduler_flags_a_run_nothing_is_polling_for(monkeypatch):
    """READY proves registration; a run sitting past its start plus grace
    proves nothing is executing — by OUR clock, not Prefect's Late-marker
    service, which can lag while serve.py is just as dead."""
    monkeypatch.setattr(
        stats.settings, "prefect_api_url", "https://prefect.example/api"
    )
    monkeypatch.setattr(stats.settings, "prefect_api_key", "k")
    forgotten = [
        {
            "deployment_id": "d1",
            "expected_start_time": "2026-08-25T11:00:00+00:00",  # an hour late
            # Still labelled Scheduled: the late-marker has not run. Stale anyway.
            "state": {"type": "SCHEDULED", "name": "Scheduled"},
        }
    ]
    monkeypatch.setattr(stats, "_prefect", _prefect_fake([DEPLOYMENT], forgotten, []))
    section = stats.scheduler_status(NOW)
    assert section["configured"] is True
    assert section["alive"] is False
    assert section["reason"] == "stale_runs"
    assert section["stale_runs"] == 1
    assert section["deployments"][0]["cron"] == "0 7 * * 2"
    # A past-dated run is not an upcoming one.
    assert section["deployments"][0]["next_run"] is None


def test_an_empty_workspace_is_not_a_dead_scheduler(monkeypatch):
    monkeypatch.setattr(
        stats.settings, "prefect_api_url", "https://prefect.example/api"
    )
    monkeypatch.setattr(stats.settings, "prefect_api_key", "k")
    monkeypatch.setattr(stats, "_prefect", _prefect_fake([], [], []))
    section = stats.scheduler_status(NOW)
    assert section["alive"] is False
    assert section["reason"] == "no_deployments"
    assert section["stale_runs"] == 0


def test_scheduler_alive_when_ready_and_on_time(monkeypatch):
    monkeypatch.setattr(
        stats.settings, "prefect_api_url", "https://prefect.example/api"
    )
    monkeypatch.setattr(stats.settings, "prefect_api_key", "k")
    upcoming = [
        {
            "deployment_id": "d1",
            "expected_start_time": "2026-08-25T13:00:00+00:00",
            "state": {"type": "SCHEDULED", "name": "Scheduled"},
        }
    ]
    finished = [
        {
            "deployment_id": "d1",
            "start_time": "2026-08-18T07:00:02+00:00",
            "state": {"type": "COMPLETED", "name": "Completed"},
        }
    ]
    monkeypatch.setattr(
        stats, "_prefect", _prefect_fake([DEPLOYMENT], upcoming, finished)
    )
    section = stats.scheduler_status(NOW)
    assert section["alive"] is True
    assert section["reason"] is None
    row = section["deployments"][0]
    assert row["next_run"] == "2026-08-25T13:00:00+00:00"
    assert row["last_run_state"] == "COMPLETED"


def test_scheduler_survives_a_prefect_blip(monkeypatch):
    monkeypatch.setattr(
        stats.settings, "prefect_api_url", "https://prefect.example/api"
    )
    monkeypatch.setattr(stats.settings, "prefect_api_key", "k")
    http = MagicMock()
    http.post.side_effect = RuntimeError("timeout")
    monkeypatch.setattr(stats, "_prefect", http)
    section = stats.scheduler_status(NOW)
    assert section["configured"] is True
    assert section["alive"] is False
    assert section["reason"] == "unreachable"
    assert "timeout" in section["error"]


def test_the_endpoint_answers_the_whole_dashboard_in_one_call(monkeypatch):
    monkeypatch.setattr(stats, "build", lambda: {"generated_at": "x"})
    client = TestClient(app)
    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json() == {"generated_at": "x"}
