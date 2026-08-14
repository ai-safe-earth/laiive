"""API endpoints: sweep persists a report, approve replays from it."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from agent.api import app
from conftest import http_response

client = TestClient(app)

REPORT_ID = "00000000-0000-0000-0000-000000000001"


def stored_report(**overrides):
    report = {
        "id": REPORT_ID,
        "city": "Berlin",
        "status": "dry_run",
        "candidates": [
            {
                "draft": {
                    "name": "Test Night",
                    "artists": ["Test Artist"],
                    "start_at": "2027-04-01T21:00:00",
                    "venue": "Test Venue",
                    "city": "Berlin",
                    "price_min": 15,
                },
                "source_url": "https://example.com/agenda",
                "missing": [],
                "dedup_status": "new",
            },
            {
                "draft": {"name": "Dupe"},
                "source_url": "https://example.com/dupe",
                "missing": ["artists"],
                "dedup_status": "exists",
            },
        ],
        "stats": {},
    }
    report.update(overrides)
    return report


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["neo4j"] == "ok"


def test_sweep_persists_report_and_writes_nothing(mock_reports_http, mock_neo4j):
    response = client.post("/sweep", json={"city": "Berlin"})
    assert response.status_code == 200
    body = response.json()
    assert body["report_id"] == REPORT_ID
    assert body["stats"]["candidates"] == 1
    assert mock_reports_http.post.called
    writes = [q for q, _ in mock_neo4j.fake_session.queries if "CREATE" in q]
    assert writes == []


def test_sweep_validates_city():
    assert client.post("/sweep", json={"city": ""}).status_code == 422


def test_get_report_404(mock_reports_http):
    mock_reports_http.get.return_value = http_response(200, [])
    assert client.get(f"/reports/{REPORT_ID}").status_code == 404


def test_approve_writes_only_new_by_default(mock_reports_http, mock_neo4j):
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    response = client.post(f"/reports/{REPORT_ID}/approve", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert [r["index"] for r in body["results"]] == [0]
    writes = [q for q, _ in mock_neo4j.fake_session.queries if "CREATE (e:Event" in q]
    assert len(writes) == 1
    assert mock_reports_http.patch.called


def test_approve_already_approved_409(mock_reports_http):
    mock_reports_http.get.return_value = http_response(
        200, [stored_report(status="approved")]
    )
    response = client.post(f"/reports/{REPORT_ID}/approve", json={})
    assert response.status_code == 409


def test_approve_rejects_bad_indices(mock_reports_http):
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    response = client.post(f"/reports/{REPORT_ID}/approve", json={"indices": [7]})
    assert response.status_code == 422


def test_approve_source_is_admin_search(mock_reports_http, mock_neo4j):
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    client.post(f"/reports/{REPORT_ID}/approve", json={"indices": [0]})
    write_params = next(
        params
        for q, params in mock_neo4j.fake_session.queries
        if "CREATE (e:Event" in q
    )
    assert write_params["source"] == "admin_search"
    assert write_params["owner_id"] is None


def test_approve_non_uuid_user_id_does_not_break_the_update(mock_reports_http):
    """approved_by is a uuid column — a stray header value becomes null."""
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    response = client.post(
        f"/reports/{REPORT_ID}/approve",
        json={},
        headers={"X-User-Id": "not-a-uuid"},
    )
    assert response.status_code == 200
    patch_payload = mock_reports_http.patch.call_args.kwargs["json"]
    assert patch_payload["approved_by"] is None


def test_approve_update_failure_still_returns_write_results(mock_reports_http):
    """Graph writes are committed by then — surface them, never 502."""
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    mock_reports_http.patch.return_value = http_response(500, {}, text="boom")
    response = client.post(f"/reports/{REPORT_ID}/approve", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["warnings"]


def test_report_store_failure_is_502(mock_reports_http):
    mock_reports_http.post.return_value = http_response(500, {}, text="boom")
    response = client.post("/sweep", json={"city": "Berlin"})
    assert response.status_code == 502


def test_backfill_reports_counts(mock_neo4j):
    response = client.post("/backfill", json={"max_venues": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["embedded"] == 0
    assert body["venues_geocoded"] == 0


@pytest.fixture
def mock_neo4j_with_orphan_venue(mock_neo4j):
    session = mock_neo4j.fake_session
    original_run = session.run

    def run(query, **params):
        if "v.location IS NULL" in query:
            session.queries.append((query, params))
            result = MagicMock()
            result.__iter__ = lambda self: iter(
                [{"uid": "v1", "name": "Lost Venue", "address": None, "city": "Berlin"}]
            )
            return result
        return original_run(query, **params)

    session.run = run
    return mock_neo4j


def test_backfill_geocodes_venues(mock_neo4j_with_orphan_venue, mock_geocoder):
    response = client.post("/backfill", json={"max_venues": 5})
    assert response.json()["venues_geocoded"] == 1
    mock_geocoder.geocode.assert_called_with("Lost Venue, Berlin")
