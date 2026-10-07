"""The write verdict is recorded for every outcome, including the raising ones.

That is the whole point of the placement. `duplicate`, `invalid` and `error`
leave `_write_or_raise` as HTTPExceptions, so a record written in the route
handler after the call would capture successes and nothing else — which would
make the silent-duplicate failure mode (the one the dedup corpus exists for)
exactly as invisible as it is today.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent import push_records
from agent.api import app
from tests.conftest import SOON


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def inline_threads():
    """Record synchronously, so assertions are not racing a daemon thread.

    `_record` is replaced rather than `threading.Thread`: `agent.api.threading`
    *is* the threading module, so patching it there patches it everywhere and
    takes `asyncio.to_thread`'s executor down with it. The real
    `push_records.write` still runs — only the hand-off is inlined.
    """
    import time as _time

    from agent import api as _api

    def _sync(request_id, *, start, **fields):
        push_records.write(
            request_id,
            **fields,
            latency_ms=int((_time.perf_counter() - start) * 1000),
        )

    with patch.object(_api, "_record", _sync):
        yield


@pytest.fixture
def recording(monkeypatch):
    """A live-looking Supabase: URL set, transport mocked."""
    monkeypatch.setattr(push_records.settings, "supabase_url", "https://sb.test")
    monkeypatch.setattr(push_records.settings, "supabase_service_role_key", "k")
    http = MagicMock()
    http.post.return_value = MagicMock(status_code=201, text="")
    monkeypatch.setattr(push_records, "_http", http)
    return http


DRAFT = {
    "artists": ["Test Artist"],
    "start_at": f"{SOON}T21:00:00",
    "venue": "Test Venue",
    "address": "Kantstrasse 12a",
    "city": "Berlin",
    "price_min": 15,
}


def _posted(http) -> dict:
    assert http.post.called, "no push_records insert was attempted"
    return http.post.call_args.kwargs["json"]


class TestEveryVerdictIsRecorded:
    def test_a_silent_duplicate_is_recorded_though_it_raises(
        self, client, mock_neo4j, recording, inline_threads
    ):
        """The failure mode the whole table exists for."""
        mock_neo4j.fake_session.dedup_hit = {
            "uid": "existing-uid",
            "name": "Test Artist at Test Venue",
            "owner_id": "someone-else",
        }
        response = client.post(
            "/validate-event",
            json={"draft": DRAFT},
            headers={"x-request-id": "gw-1", "x-user-id": "me"},
        )
        assert response.status_code == 409

        row = _posted(recording)
        assert row["writer_verdict"] == "duplicate"
        assert row["request_id"] == "gw-1"
        assert row["kind"] == "create"
        assert row["entity_type"] == "event"
        # The draft is the eval payload: what was submitted, not what survived.
        assert row["draft"]["venue"] == "Test Venue"

    def test_a_clean_create_is_recorded(
        self, client, mock_neo4j, recording, inline_threads
    ):
        response = client.post(
            "/validate-event",
            json={"draft": DRAFT},
            headers={"x-request-id": "gw-2", "x-user-id": "me"},
        )
        assert response.status_code == 200

        row = _posted(recording)
        assert row["writer_verdict"] in ("created", "adopted")
        assert row["user_id"] == "me"
        assert row["entity_uid"]
        assert isinstance(row["latency_ms"], int)

    def test_an_invalid_draft_is_recorded(
        self, client, mock_neo4j, recording, inline_threads
    ):
        # Unparseable rather than merely past: parse_start_at returning None
        # is what the writer calls invalid (neo4j_writer.py:190-196).
        bad = {**DRAFT, "start_at": "sometime next spring"}
        response = client.post(
            "/validate-event",
            json={"draft": bad},
            headers={"x-request-id": "gw-3"},
        )
        assert response.status_code == 422
        assert _posted(recording)["writer_verdict"] == "invalid"


class TestTheWriteItselfIsSafe:
    def test_no_supabase_url_writes_nothing(self, monkeypatch):
        monkeypatch.setattr(push_records.settings, "supabase_url", "")
        http = MagicMock()
        monkeypatch.setattr(push_records, "_http", http)
        push_records.write(
            "r", kind="create", entity_type="event", result=MagicMock(status="created")
        )
        assert not http.post.called

    def test_a_failed_insert_counts_and_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(push_records.settings, "supabase_url", "https://sb.test")
        http = MagicMock()
        http.post.return_value = MagicMock(status_code=401, text="bad key")
        monkeypatch.setattr(push_records, "_http", http)
        before = push_records.writes_failed

        push_records.write(
            "r",
            kind="create",
            entity_type="event",
            result=MagicMock(status="created", warnings=[], message=""),
        )

        assert push_records.writes_failed == before + 1

    def test_a_transport_error_counts_and_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(push_records.settings, "supabase_url", "https://sb.test")
        http = MagicMock()
        http.post.side_effect = OSError("dns flapped")
        monkeypatch.setattr(push_records, "_http", http)
        before = push_records.writes_failed

        push_records.write(
            "r",
            kind="create",
            entity_type="event",
            result=MagicMock(status="created", warnings=[], message=""),
        )

        assert push_records.writes_failed == before + 1

    def test_an_edit_result_has_no_name_or_venue_fields(self, monkeypatch):
        """UpdateResult carries `changed` and no `name`; getattr defaults keep
        one payload builder working for both writer shapes."""
        monkeypatch.setattr(push_records.settings, "supabase_url", "https://sb.test")
        http = MagicMock()
        http.post.return_value = MagicMock(status_code=201, text="")
        monkeypatch.setattr(push_records, "_http", http)

        from laiive_shared.neo4j_writer import UpdateResult

        push_records.write(
            "r",
            kind="edit",
            entity_type="venue",
            result=UpdateResult(
                status="updated", uid="v1", changed={"city": {"old": "a", "new": "b"}}
            ),
        )
        row = json.loads(json.dumps(http.post.call_args.kwargs["json"]))
        assert row["entity_name"] is None
        assert row["changed"] == {"city": {"old": "a", "new": "b"}}
        assert row["writer_verdict"] == "updated"
