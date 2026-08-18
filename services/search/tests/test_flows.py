"""Prefect flows are thin HTTP clients — tests exercise the plain functions
(`task.fn`, the pure renderer) with httpx mocked; no Prefect runtime, no
network. The flow bodies themselves are wiring and run live in 5b's verify."""

from unittest.mock import MagicMock

import pytest

from flows import auth, backfill, city_sweep, polling


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GATEWAY_URL", "http://gw.test:8000/")
    monkeypatch.setenv("SUPABASE_URL", "https://supa.test")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "pk-test")
    monkeypatch.setenv("SUPABASE_ADMIN_EMAIL", "bot@test")
    monkeypatch.setenv("SUPABASE_ADMIN_PASSWORD", "pw")


def http_response(status_code=200, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    if status_code >= 400:
        import httpx

        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=MagicMock(), response=response
        )
    return response


class TestAuth:
    def test_env_beats_prefect(self):
        # env is set by the fixture — no Prefect API involved at all
        assert auth.gateway_url() == "http://gw.test:8000"

    def test_password_grant(self, monkeypatch):
        post = MagicMock(return_value=http_response(payload={"access_token": "jwt-1"}))
        monkeypatch.setattr(auth.httpx, "post", post)
        assert auth.get_admin_jwt() == "jwt-1"
        call = post.call_args
        assert call.args[0] == "https://supa.test/auth/v1/token"
        assert call.kwargs["params"] == {"grant_type": "password"}
        assert call.kwargs["headers"]["apikey"] == "pk-test"  # pragma: allowlist secret
        assert call.kwargs["json"] == {
            "email": "bot@test",
            "password": "pw",  # pragma: allowlist secret
        }

    def test_grant_without_token_raises(self, monkeypatch):
        monkeypatch.setattr(
            auth.httpx, "post", MagicMock(return_value=http_response(payload={}))
        )
        with pytest.raises(RuntimeError, match="no access_token"):
            auth.get_admin_jwt()


class TestSweepTask:
    def test_posts_then_polls_the_report(self, monkeypatch):
        monkeypatch.setattr(city_sweep, "get_admin_jwt", lambda: "jwt-2")
        post = MagicMock(
            return_value=http_response(
                202, payload={"report_id": "r1", "city": "Madrid", "status": "running"}
            )
        )
        monkeypatch.setattr(city_sweep.httpx, "post", post)
        poll = MagicMock(
            return_value={
                "id": "r1",
                "city": "Madrid",
                "status": "dry_run",
                "stats": {"candidates": 2},
                "candidates": [{"dedup_status": "new"}, {"dedup_status": "exists"}],
            }
        )
        monkeypatch.setattr(city_sweep, "wait_for_report", poll)

        result = city_sweep.sweep_city.fn("Madrid", max_pages=3)

        assert result["report_id"] == "r1"
        assert result["stats"] == {"candidates": 2}
        assert len(result["candidates"]) == 2
        call = post.call_args
        assert call.args[0] == "http://gw.test:8000/api/admin/search/sweep"
        assert call.kwargs["json"] == {"city": "Madrid", "max_pages": 3}
        assert call.kwargs["headers"]["Authorization"] == "Bearer jwt-2"
        assert poll.call_args.args == ("http://gw.test:8000", "r1", "jwt-2")

    def test_max_pages_omitted_when_none(self, monkeypatch):
        monkeypatch.setattr(city_sweep, "get_admin_jwt", lambda: "jwt")
        post = MagicMock(return_value=http_response(202, payload={"report_id": "r"}))
        monkeypatch.setattr(city_sweep.httpx, "post", post)
        monkeypatch.setattr(city_sweep, "wait_for_report", MagicMock(return_value={}))
        city_sweep.sweep_city.fn("Berlin")
        assert post.call_args.kwargs["json"] == {"city": "Berlin"}

    def test_gateway_error_raises(self, monkeypatch):
        import httpx

        monkeypatch.setattr(city_sweep, "get_admin_jwt", lambda: "jwt")
        monkeypatch.setattr(
            city_sweep.httpx, "post", MagicMock(return_value=http_response(503))
        )
        with pytest.raises(httpx.HTTPStatusError):
            city_sweep.sweep_city.fn("Madrid")


class TestRenderReport:
    def test_new_candidates_tabled_others_counted(self):
        results = [
            {
                "city": "Barcelona",
                "report_id": "r-abc",
                "stats": {
                    "pages_searched": 4,
                    "pages_with_events": 2,
                    "drafts_extracted": 10,
                    "skipped_past": 3,
                    "candidates": 7,
                    "new": 1,
                    "exists": 5,
                    "similar": 1,
                },
                "candidates": [
                    {
                        "dedup_status": "new",
                        "missing": ["price_min"],
                        "draft": {
                            "name": "Rock Fest",
                            "start_at": "2026-09-01T20:00:00",
                            "venue": "Poble Espanyol",
                        },
                    },
                    {"dedup_status": "exists", "draft": {"name": "Old One"}},
                ],
            }
        ]
        md = city_sweep.render_report(results, {})
        assert "## Barcelona — report `r-abc`" in md
        assert "new 1, exists 5, similar 1" in md
        assert "| Rock Fest | 2026-09-01T20:00:00 | Poble Espanyol | price_min |" in md
        assert "Old One" not in md  # only "new" rows need review
        assert "reports/r-abc/approve" in md
        assert "Failed cities" not in md

    def test_failures_listed(self):
        md = city_sweep.render_report([], {"Madrid": "503 Service Unavailable"})
        assert "## Failed cities" in md
        assert "**Madrid**: 503" in md


class TestBackfillTask:
    def test_posts_then_polls_for_stats(self, monkeypatch):
        monkeypatch.setattr(backfill, "get_admin_jwt", lambda: "jwt-3")
        post = MagicMock(return_value=http_response(202, payload={"report_id": "r9"}))
        monkeypatch.setattr(backfill.httpx, "post", post)
        poll = MagicMock(
            return_value={"id": "r9", "status": "done", "stats": {"embedded": 4}}
        )
        monkeypatch.setattr(backfill, "wait_for_report", poll)

        result = backfill.run_backfill.fn(50)

        assert result == {"embedded": 4}
        call = post.call_args
        assert call.args[0] == "http://gw.test:8000/api/admin/search/backfill"
        assert call.kwargs["json"] == {"max_venues": 50}
        assert call.kwargs["headers"]["Authorization"] == "Bearer jwt-3"
        assert poll.call_args.kwargs["deadline"] == backfill.BACKFILL_DEADLINE


class TestWaitForReport:
    def _get_sequence(self, monkeypatch, payloads):
        responses = [http_response(payload=p) for p in payloads]
        get = MagicMock(side_effect=responses)
        monkeypatch.setattr(polling.httpx, "get", get)
        monkeypatch.setattr(polling.time, "sleep", MagicMock())
        return get

    def test_polls_until_terminal(self, monkeypatch):
        get = self._get_sequence(
            monkeypatch,
            [
                {"id": "r1", "status": "running"},
                {"id": "r1", "status": "running"},
                {"id": "r1", "status": "dry_run", "candidates": []},
            ],
        )
        report = polling.wait_for_report("http://gw.test:8000", "r1", "jwt")
        assert report["status"] == "dry_run"
        assert get.call_count == 3
        assert (
            get.call_args.args[0] == "http://gw.test:8000/api/admin/search/reports/r1"
        )

    def test_failed_report_raises_with_error(self, monkeypatch):
        self._get_sequence(
            monkeypatch, [{"id": "r1", "status": "failed", "error": "tavily down"}]
        )
        with pytest.raises(RuntimeError, match="tavily down"):
            polling.wait_for_report("http://gw.test:8000", "r1", "jwt")

    def test_deadline_raises(self, monkeypatch):
        self._get_sequence(monkeypatch, [{"id": "r1", "status": "running"}] * 3)
        with pytest.raises(TimeoutError, match="still 'running'"):
            polling.wait_for_report(
                "http://gw.test:8000", "r1", "jwt", interval=10.0, deadline=15.0
            )
