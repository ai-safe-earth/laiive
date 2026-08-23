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


def test_sweep_202_then_results_land_on_the_report(mock_reports_http, mock_neo4j):
    """202 immediately; the background worker patches the report to dry_run.

    TestClient runs BackgroundTasks before returning, so the terminal patch
    is assertable in the same call.
    """
    response = client.post("/sweep", json={"city": "Berlin"})
    assert response.status_code == 202
    body = response.json()
    assert body["report_id"] == REPORT_ID
    assert body["status"] == "running"
    create_payload = mock_reports_http.post.call_args.kwargs["json"]
    assert create_payload["status"] == "running"
    terminal = mock_reports_http.patch.call_args.kwargs["json"]
    assert terminal["status"] == "dry_run"
    assert terminal["stats"]["candidates"] == 1
    assert len(terminal["candidates"]) == 1
    writes = [q for q, _ in mock_neo4j.fake_session.queries if "CREATE" in q]
    assert writes == []


def test_sweep_worker_failure_marks_the_report_failed(mock_reports_http, monkeypatch):
    from agent import discovery

    def boom(city, max_pages):
        raise RuntimeError("tavily down")

    monkeypatch.setattr(discovery, "sweep_city", boom)
    response = client.post("/sweep", json={"city": "Berlin"})
    assert response.status_code == 202
    terminal = mock_reports_http.patch.call_args.kwargs["json"]
    assert terminal["status"] == "failed"
    assert "tavily down" in terminal["error"]


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


def test_approve_already_approved_409(mock_reports_http, mock_neo4j):
    """The claim is the gate: an empty representation means someone else won."""
    mock_reports_http.get.return_value = http_response(
        200, [stored_report(status="approved")]
    )
    mock_reports_http.patch.return_value = http_response(200, [])
    response = client.post(f"/reports/{REPORT_ID}/approve", json={})
    assert response.status_code == 409
    assert "approved" in response.json()["detail"]
    # and nothing was written
    assert [
        q for q, _ in mock_neo4j.fake_session.queries if "CREATE (e:Event" in q
    ] == []


def test_approve_of_running_report_409_with_reason(mock_reports_http, mock_neo4j):
    """A running (or failed) report loses the CAS — the 409 says why."""
    mock_reports_http.get.return_value = http_response(
        200, [stored_report(status="running", candidates=[])]
    )
    mock_reports_http.patch.return_value = http_response(200, [])
    response = client.post(f"/reports/{REPORT_ID}/approve", json={})
    assert response.status_code == 409
    assert "running" in response.json()["detail"]
    assert [
        q for q, _ in mock_neo4j.fake_session.queries if "CREATE (e:Event" in q
    ] == []


def test_approve_claims_before_writing(mock_reports_http, mock_neo4j):
    """The status filter must be part of the claiming UPDATE, not a prior read."""
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    assert client.post(f"/reports/{REPORT_ID}/approve", json={}).status_code == 200
    claim = mock_reports_http.patch.call_args_list[0]
    assert claim.kwargs["params"]["status"] == "eq.dry_run"
    assert claim.kwargs["json"]["status"] == "approved"
    assert claim.kwargs["headers"]["Prefer"] == "return=representation"


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


def test_approve_carries_the_source_page_into_the_graph(mock_reports_http, mock_neo4j):
    """The candidate has carried source_url since the sweep, and approve used
    to read only its draft — so an approved event could not name the page it
    came from, while the card's own copy promised it could."""
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    client.post(f"/reports/{REPORT_ID}/approve", json={"indices": [0]})
    write_params = next(
        params
        for q, params in mock_neo4j.fake_session.queries
        if "CREATE (e:Event" in q
    )
    assert write_params["source_url"] == "https://example.com/agenda"
    # Stored beside the URL because it is what per-source questions group by.
    assert write_params["source_domain"] == "example.com"


def test_approve_without_a_source_url_still_writes(mock_reports_http, mock_neo4j):
    """A candidate from before source_url existed, or a hand-built report."""
    report = stored_report()
    del report["candidates"][0]["source_url"]
    mock_reports_http.get.return_value = http_response(200, [report])
    response = client.post(f"/reports/{REPORT_ID}/approve", json={"indices": [0]})
    assert response.status_code == 200
    write_params = next(
        params
        for q, params in mock_neo4j.fake_session.queries
        if "CREATE (e:Event" in q
    )
    assert write_params["source_url"] == ""
    assert write_params["source_domain"] == ""


def test_approve_non_uuid_user_id_does_not_break_the_update(mock_reports_http):
    """approved_by is a uuid column — a stray header value becomes null."""
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    response = client.post(
        f"/reports/{REPORT_ID}/approve",
        json={},
        headers={"X-User-Id": "not-a-uuid"},
    )
    assert response.status_code == 200
    claim_payload = mock_reports_http.patch.call_args_list[0].kwargs["json"]
    assert claim_payload["approved_by"] is None


def test_approve_update_failure_still_returns_write_results(mock_reports_http):
    """Graph writes are committed by then — surface them, never 502."""
    mock_reports_http.get.return_value = http_response(200, [stored_report()])
    # The claim succeeds; recording write_results afterwards is what fails.
    mock_reports_http.patch.side_effect = [
        http_response(200, [{"id": REPORT_ID, "status": "approved"}]),
        http_response(500, {}, text="boom"),
    ]
    response = client.post(f"/reports/{REPORT_ID}/approve", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["warnings"]


def test_report_store_failure_is_502(mock_reports_http):
    mock_reports_http.post.return_value = http_response(500, {}, text="boom")
    response = client.post("/sweep", json={"city": "Berlin"})
    assert response.status_code == 502


def test_backfill_202_then_done_with_stats(mock_reports_http, mock_neo4j):
    response = client.post("/backfill", json={"max_venues": 5})
    assert response.status_code == 202
    assert response.json()["status"] == "running"
    create_payload = mock_reports_http.post.call_args.kwargs["json"]
    assert create_payload["kind"] == "backfill"
    assert create_payload["city"] is None
    terminal = mock_reports_http.patch.call_args.kwargs["json"]
    assert terminal["status"] == "done"
    assert terminal["stats"]["embedded"] == 0
    assert terminal["stats"]["venues_geocoded"] == 0


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


def test_backfill_geocodes_venues(
    mock_neo4j_with_orphan_venue, mock_geocoder, mock_reports_http
):
    response = client.post("/backfill", json={"max_venues": 5})
    assert response.status_code == 202
    terminal = mock_reports_http.patch.call_args.kwargs["json"]
    assert terminal["stats"]["venues_geocoded"] == 1
    # The venue goes through geocode_venue (short form first, then the full
    # address), with the city as the plausibility reference.
    from agent import address_lookup

    mock_geocoder.geocode_venue.assert_called_once_with(
        "Lost Venue",
        None,
        "Berlin",
        near=mock_geocoder.geocode.return_value,
        address_resolver=address_lookup.resolve_address,
    )
    written = [
        params
        for query, params in mock_neo4j_with_orphan_venue.fake_session.queries
        if "SET v.location" in query
    ]
    assert written and written[0]["precision"] == "venue"


def test_backfill_marks_a_city_centroid_answer_as_one(
    mock_neo4j_with_orphan_venue, mock_geocoder, mock_reports_http
):
    """The provider answering with the city itself is not an address.

    Measured on the live graph: eight Barcelona venues share one pin, and that
    pin is exactly Nominatim's answer for "barcelona". Stamping those 'venue'
    would mark them verified and stop the repair sweep ever revisiting them.
    """
    mock_geocoder.geocode_venue.return_value = mock_geocoder.geocode.return_value

    assert client.post("/backfill", json={"max_venues": 5}).status_code == 202

    terminal = mock_reports_http.patch.call_args.kwargs["json"]
    assert terminal["stats"]["venues_geocoded"] == 0
    assert terminal["stats"]["venues_flagged"] == 1
    written = [
        params
        for query, params in mock_neo4j_with_orphan_venue.fake_session.queries
        if "SET v.location" in query
    ]
    assert written and written[0]["precision"] == "city_centroid"
