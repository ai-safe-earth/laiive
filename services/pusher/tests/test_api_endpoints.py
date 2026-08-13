"""Pusher API endpoint tests — OpenAI, Neo4j, and Nominatim all mocked."""

import base64
import io
import json

import pytest
from fastapi.testclient import TestClient

from agent.api import app
from tests.test_conversation import set_extraction


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoints:
    def test_root_endpoint(self, client):
        data = client.get("/").json()
        assert data["version"] == "0.3.0"
        assert "batch_parse" in data["endpoints"]

    def test_health(self, client, mock_neo4j):
        data = client.get("/health").json()
        assert data == {"status": "ok", "checks": {"api": "ok", "neo4j": "ok"}}

    def test_health_neo4j_down(self, client, mock_neo4j):
        mock_neo4j.verify_connectivity.side_effect = Exception("down")
        data = client.get("/health").json()
        assert data["status"] == "degraded"


class TestChatStreamLegacy:
    def test_complete_info_emits_sentinel(self, client, mock_openai):
        response = client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "full event info"}]},
        )
        assert response.status_code == 200
        body = response.text
        assert "__EVENT_EXTRACTED__" in body
        assert body.rstrip().endswith("data: [DONE]")
        first_frame = next(
            line for line in body.splitlines() if line.startswith("data: {")
        )
        content = json.loads(first_frame[len("data: ") :])["choices"][0]["delta"][
            "content"
        ]
        details = json.loads(content.split("__EVENT_EXTRACTED__")[1])
        assert details["artist"] == "Test Artist"
        assert details["venue"] == "Test Venue"

    def test_incomplete_info_streams_clarification(self, client, mock_openai):
        set_extraction(mock_openai, {"artists": ["X"], "city": "Berlin"})
        body = client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "gig by X in Berlin"}]},
        ).text
        assert "__EVENT_EXTRACTED__" not in body
        assert '"delta"' in body

    def test_empty_messages_400(self, client):
        assert client.post("/chat/stream", json={"messages": []}).status_code == 400

    def test_invalid_role_422(self, client):
        response = client.post(
            "/chat/stream", json={"messages": [{"role": "bad", "content": "x"}]}
        )
        assert response.status_code == 422


class TestChatStreamV2:
    def test_form_extracted_frame(self, client, mock_openai):
        body = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "full event info"}],
                "protocol": "v2",
            },
        ).text
        assert "event: form.extracted" in body
        assert "event: message.delta" in body
        assert "event: done" in body
        assert "__EVENT_EXTRACTED__" not in body

    def test_one_round_then_form_with_missing(self, client, mock_openai):
        set_extraction(mock_openai, {"artists": ["X"], "city": "Berlin"})
        first = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "gig by X"}],
                "protocol": "v2",
            },
        ).text
        assert "event: form.extracted" not in first  # round 1: ask naturally

        second = client.post(
            "/chat/stream",
            json={
                "messages": [
                    {"role": "user", "content": "gig by X"},
                    {"role": "assistant", "content": "when and where?"},
                    {"role": "user", "content": "dunno"},
                ],
                "protocol": "v2",
            },
        ).text
        assert "event: form.extracted" in second  # round 2: form, gaps marked
        frame_data = [line for line in second.splitlines() if line.startswith("data: ")]
        form_payload = json.loads(frame_data[1][len("data: ") :])
        assert "start_at" in form_payload["missing"]


class TestTranscribeEndpoint:
    def test_transcribe_audio(self, client):
        audio = base64.b64encode(b"fake-audio").decode()
        data = client.post("/transcribe-audio", json={"audio": audio}).json()
        assert "Test Artist" in data["text"]

    def test_transcribe_empty_audio(self, client):
        assert client.post("/transcribe-audio", json={"audio": ""}).status_code == 400

    def test_transcribe_missing_field(self, client):
        assert client.post("/transcribe-audio", json={}).status_code == 422


class TestExtractEndpoints:
    def test_extract_from_text(self, client, mock_openai):
        data = client.post(
            "/extract-event-from-text", json={"text": "Test Artist ..."}
        ).json()
        assert data["success"] is True
        assert data["eventDetails"]["venue"] == "Test Venue"
        assert data["draft"]["artists"] == ["Test Artist"]
        assert data["missing"] == []

    def test_extract_from_text_empty(self, client, mock_openai):
        set_extraction(mock_openai, "{}")
        data = client.post("/extract-event-from-text", json={"text": "hello"}).json()
        assert data["success"] is False

    def test_extract_from_image(self, client, mock_openai):
        image = base64.b64encode(b"fake-image").decode()
        data = client.post("/extract-event-details", json={"imageBase64": image}).json()
        # vision call and extraction call share the mocked client; the
        # extraction JSON is what lands in the draft
        assert data["success"] is True

    def test_extract_image_missing_field(self, client):
        assert client.post("/extract-event-details", json={}).status_code == 422


class TestValidateEvent:
    EVENT = {
        "name": "Test Event",
        "artist": "Test Artist",
        "event_date": "2026-04-01T21:00:00",
        "venue": "Test Venue",
        "city": "Berlin",
        "price": 15.0,
    }

    def test_validate_event_success(self, client, mock_neo4j):
        data = client.post("/validate-event", json={"event": self.EVENT}).json()
        assert data["success"] is True
        assert data["event_name"] == "Test Event"
        assert data["artist"] == "Test Artist"

    def test_write_carries_owner_and_provenance(self, client, mock_neo4j):
        client.post(
            "/validate-event",
            json={"event": self.EVENT},
            headers={"X-User-Id": "user-42"},
        )
        write_params = mock_neo4j.fake_session.queries[1][1]
        assert write_params["owner_id"] == "user-42"
        assert write_params["source"] == "pro_submission"
        assert write_params["country_code"] == "DE"  # geocoded
        assert write_params["venue_lat"] == 52.52

    def test_duplicate_is_409(self, client, mock_neo4j):
        mock_neo4j.fake_session.dedup_hit = {"uid": "dup-1", "name": "Test Event"}
        response = client.post("/validate-event", json={"event": self.EVENT})
        assert response.status_code == 409

    def test_free_event_price_zero(self, client, mock_neo4j):
        event = dict(self.EVENT, price=0.0)
        assert client.post("/validate-event", json={"event": event}).json()["success"]

    def test_missing_required_fields_422_from_pydantic(self, client):
        response = client.post("/validate-event", json={"event": {"name": "X"}})
        assert response.status_code == 422


class TestBatch:
    CSV = (
        "name,artist,date,venue,city,price,genre\n"
        "Jazz Night,Ana Beck Quartet,2026-09-01 20:00,Quasimodo,Berlin,22,jazz\n"
        "Techno Sunday,DJ Petra;Klangfeld,2026-09-07 22:00,Berghain,Berlin,18,techno\n"
        ",,,,,\n"
    )

    def _upload(self, client, content=None, filename="events.csv"):
        return client.post(
            "/batch/parse",
            files={
                "file": (
                    filename,
                    io.BytesIO((content or self.CSV).encode()),
                    "text/csv",
                )
            },
        )

    def test_parse_csv(self, client):
        data = self._upload(client).json()
        assert data["total"] == 2  # empty row dropped
        first = data["drafts"][0]
        assert first["draft"]["name"] == "Jazz Night"
        assert first["draft"]["artists"] == ["Ana Beck Quartet"]
        assert first["missing"] == []
        assert data["drafts"][1]["draft"]["artists"] == ["DJ Petra", "Klangfeld"]

    def test_parse_reports_missing_per_row(self, client):
        csv_text = "artist,city\nSolo Act,Berlin\n"
        data = self._upload(client, csv_text).json()
        assert set(data["drafts"][0]["missing"]) == {"start_at", "venue", "price_min"}

    def test_unsupported_extension_422(self, client):
        response = self._upload(client, filename="events.pdf")
        assert response.status_code == 422

    def test_empty_file_422(self, client):
        assert self._upload(client, "name,city\n").status_code == 422

    def test_batch_validate_writes_with_progress(self, client, mock_neo4j):
        draft = {
            "name": "Jazz Night",
            "artists": ["Ana Beck Quartet"],
            "start_at": "2026-09-01T20:00:00",
            "venue": "Quasimodo",
            "city": "Berlin",
            "price_min": 22.0,
        }
        data = client.post(
            "/batch/validate-event", json={"draft": draft, "index": 1, "total": 5}
        ).json()
        assert data["success"] is True
        assert (data["index"], data["total"]) == (1, 5)
        assert data["event_name"] == "Jazz Night"

    def test_batch_validate_invalid_draft_422(self, client, mock_neo4j):
        response = client.post(
            "/batch/validate-event",
            json={"draft": {"artists": ["X"]}, "index": 1, "total": 1},
        )
        assert response.status_code == 422
