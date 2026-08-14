"""Pusher API endpoint tests — OpenAI, Neo4j, and Nominatim all mocked."""

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


class TestChatStreamRequests:
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


class TestSupersededEndpointsAreGone:
    """`/ingest` + `/chat/stream` replaced all of these: every modality becomes
    text, and extraction happens once over the whole conversation."""

    @pytest.mark.parametrize(
        "path",
        [
            "/transcribe-audio",
            "/extract-event-from-text",
            "/extract-event-from-url",
            "/extract-event-details",
        ],
    )
    def test_gone(self, client, path):
        assert client.post(path, json={}).status_code == 404


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
    """The form sends the whole draft — genre, venue_type, address and price
    ranges included. The flat payload that dropped all of that is gone."""

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

    def test_draft_keeps_the_fields_a_flat_form_would_drop(self, client, mock_neo4j):
        client.post("/validate-event", json={"draft": self.DRAFT})
        write_params = mock_neo4j.fake_session.queries[1][1]
        assert write_params["genre"] == "jazz"
        assert write_params["price_max"] == 28
        assert write_params["venue_type"] == "club"

    def test_no_draft_is_422(self, client):
        assert client.post("/validate-event", json={}).status_code == 422

    def test_response_names_the_event(self, client, mock_neo4j):
        data = client.post("/validate-event", json={"draft": self.DRAFT}).json()
        assert data["event_name"] == "Jazz Night"
        assert data["artist"] == "Ana Beck Quartet"

    def test_write_carries_owner_and_provenance(self, client, mock_neo4j):
        client.post(
            "/validate-event",
            json={"draft": self.DRAFT},
            headers={"X-User-Id": "user-42"},
        )
        write_params = mock_neo4j.fake_session.queries[1][1]
        assert write_params["owner_id"] == "user-42"
        assert write_params["source"] == "pro_submission"
        assert write_params["country_code"] == "DE"  # geocoded
        assert write_params["venue_lat"] == 52.52

    def test_duplicate_is_409(self, client, mock_neo4j):
        mock_neo4j.fake_session.dedup_hit = {"uid": "dup-1", "name": "Jazz Night"}
        response = client.post("/validate-event", json={"draft": self.DRAFT})
        assert response.status_code == 409

    def test_free_event_price_zero(self, client, mock_neo4j):
        draft = dict(self.DRAFT, price_min=0.0, price_max=None)
        assert client.post("/validate-event", json={"draft": draft}).json()["success"]

    def test_unknown_payload_shape_is_422(self, client):
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
