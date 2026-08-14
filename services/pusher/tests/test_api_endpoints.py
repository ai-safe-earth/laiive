"""Pusher API endpoint tests — OpenAI, Neo4j, and Nominatim all mocked."""

import base64
import io
import json

import pytest
from fastapi.testclient import TestClient

from agent.api import app
from tests.test_conversation import COMPLETE, set_extraction


@pytest.fixture
def client():
    return TestClient(app)


def _frames(body: str) -> list[tuple[str, str]]:
    """[(event name, raw data line)] from a v2 stream, in arrival order."""
    frames = []
    for block in body.split("\n\n"):
        lines = block.strip().split("\n")
        if len(lines) == 2 and lines[0].startswith("event: "):
            frames.append((lines[0][len("event: ") :], lines[1]))
    return frames


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

    def test_many_events_emit_one_frame_each_in_order(self, client, mock_openai):
        """A spreadsheet-shaped conversation: N forms, N-1 of them for later."""
        set_extraction(
            mock_openai,
            {
                "events": [
                    {**COMPLETE, "venue": "First Venue"},
                    {**COMPLETE, "venue": "Second Venue"},
                    {**COMPLETE, "venue": "Third Venue"},
                ]
            },
        )
        body = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "three gigs in a csv"}],
                "protocol": "v2",
            },
        ).text

        forms = [
            json.loads(payload[len("data: ") :])
            for name, payload in _frames(body)
            if name == "form.extracted"
        ]
        assert [f["draft"]["venue"] for f in forms] == [
            "First Venue",
            "Second Venue",
            "Third Venue",
        ]
        assert [(f["index"], f["total"]) for f in forms] == [(0, 3), (1, 3), (2, 3)]


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


class TestIngest:
    """Every modality reduces to text here.

    /ingest deliberately does not extract fields: the client appends the text
    to the conversation and the normal turn extracts over the whole history, so
    a flyer that supplies the venue and a sentence that supplies the price
    merge into one draft with no client-side merge rules.
    """

    def _upload(self, client, name, content_type, body=b"data"):
        return client.post(
            "/ingest", files={"file": (name, io.BytesIO(body), content_type)}
        )

    def test_audio_returns_the_transcript(self, client):
        data = self._upload(client, "note.webm", "audio/webm").json()
        assert data["kind"] == "audio"
        assert data["text"] == "Test Artist at Test Venue in Berlin on April 1st"

    def test_image_returns_vision_text(self, client, mock_openai):
        mock_openai.chat.completions.create.return_value.choices[
            0
        ].message.content = "Poster: Ana Beck at Quasimodo, Berlin"
        data = self._upload(client, "flyer.png", "image/png").json()
        assert data["kind"] == "image"
        assert "Quasimodo" in data["text"]

    def test_plain_text_document(self, client):
        data = self._upload(
            client, "event.txt", "text/plain", b"Ana Beck at Quasimodo"
        ).json()
        assert data["kind"] == "document"
        assert data["text"] == "Ana Beck at Quasimodo"

    def test_no_extraction_happens_here(self, client):
        """The response is text, not a draft — extraction belongs to the turn."""
        data = self._upload(client, "event.txt", "text/plain", b"Ana Beck").json()
        assert set(data) == {"kind", "source", "text"}

    def test_pdf_with_a_text_layer_is_read(self, client):
        from pypdf import PdfWriter

        buffer = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.write(buffer)
        response = self._upload(
            client, "flyer.pdf", "application/pdf", buffer.getvalue()
        )
        # A blank page has no text layer — the scanned-flyer branch.
        assert response.status_code == 400
        assert "image" in response.json()["detail"].lower()

    def test_corrupt_pdf_is_a_client_error_not_a_502(self, client):
        pdf = b"%PDF-1.4\nnot really a pdf"
        response = self._upload(client, "flyer.pdf", "application/pdf", pdf)
        assert response.status_code == 400

    def test_unsupported_type_is_400(self, client):
        response = self._upload(client, "song.xyz", "application/octet-stream")
        assert response.status_code == 400

    def test_oversized_audio_is_413(self, client):
        from laiive_shared.speech import MAX_AUDIO_BYTES

        response = self._upload(
            client, "long.webm", "audio/webm", b"x" * (MAX_AUDIO_BYTES + 1)
        )
        assert response.status_code == 413

    def test_empty_result_is_422(self, client):
        response = self._upload(client, "blank.txt", "text/plain", b"   ")
        assert response.status_code == 422

    def test_requires_a_file_or_url(self, client):
        assert client.post("/ingest").status_code == 400


class TestValidateEventDraft:
    """The new form sends a full draft; the flat legacy payload still works
    until Phase 4c removes it, and sending both at once is a 422."""

    DRAFT = {
        "name": "Jazz Night",
        "artists": ["Ana Beck Quartet"],
        "start_at": "2026-09-01T20:00:00",
        "venue": "Quasimodo",
        "city": "Berlin",
        "price_min": 22,
        "price_max": 28,
        "price_currency": "EUR",
        "genre": "jazz",
        "venue_type": "club",
    }

    def test_draft_payload_writes(self, client, mock_neo4j):
        response = client.post("/validate-event", json={"draft": self.DRAFT})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_draft_keeps_what_the_legacy_shape_would_drop(self, client, mock_neo4j):
        client.post("/validate-event", json={"draft": self.DRAFT})
        write_params = mock_neo4j.fake_session.queries[1][1]
        assert write_params["genre"] == "jazz"
        assert write_params["price_max"] == 28
        assert write_params["venue_type"] == "club"

    def test_neither_payload_is_422(self, client):
        assert client.post("/validate-event", json={}).status_code == 422

    def test_both_payloads_is_422(self, client):
        response = client.post(
            "/validate-event",
            json={
                "draft": self.DRAFT,
                "event": {
                    "name": "Jazz Night",
                    "event_date": "2026-09-01T20:00:00",
                    "venue": "Quasimodo",
                    "city": "Berlin",
                },
            },
        )
        assert response.status_code == 422


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
