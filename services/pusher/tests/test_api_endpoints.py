"""
Tests for pusher API endpoints.
Run with: cd services/pusher && python -m pytest tests/test_api_endpoints.py -v
"""

import pytest
import base64
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from agent.api import app

    return TestClient(app)


class TestHealthEndpoints:
    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "laiive pusher API"
        assert "endpoints" in data

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestChatEndpoint:
    def test_chat_basic(self, client):
        # slowapi rate limiter requires X-Forwarded-For or real IP
        response = client.post(
            "/chat",
            json={
                "message": "I want to add an event by Test Artist at Berghain in Berlin on April 1st for 15 euros"
            },
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "reply" in data
        assert "fields" in data
        assert isinstance(data["confirmed"], bool)

    def test_chat_with_session_id(self, client):
        response = client.post(
            "/chat",
            json={"session_id": "test-session-123", "message": "Hello"},
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
        assert response.status_code == 200
        assert response.json()["session_id"] == "test-session-123"

    def test_chat_missing_message(self, client):
        response = client.post("/chat", json={})
        assert response.status_code == 422


class TestChatStreamEndpoint:
    def test_stream_basic(self, client):
        response = client.post(
            "/chat/stream", json={"messages": [{"role": "user", "content": "Hello"}]}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE events
        content = response.text
        assert "data:" in content
        assert "[DONE]" in content

    def test_stream_empty_messages(self, client):
        response = client.post("/chat/stream", json={"messages": []})
        assert response.status_code == 400

    def test_stream_invalid_role(self, client):
        response = client.post(
            "/chat/stream", json={"messages": [{"role": "hacker", "content": "test"}]}
        )
        assert response.status_code == 422

    def test_stream_with_language(self, client):
        response = client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "Hola"}], "language": "es"},
        )
        assert response.status_code == 200


class TestTranscribeEndpoint:
    def test_transcribe_audio(self, client):
        audio_data = base64.b64encode(b"fake audio data").decode()
        response = client.post("/transcribe-audio", json={"audio": audio_data})
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert len(data["text"]) > 0

    def test_transcribe_empty_audio(self, client):
        # Empty base64 decodes to empty bytes
        response = client.post("/transcribe-audio", json={"audio": ""})
        assert response.status_code == 500  # Empty audio triggers error

    def test_transcribe_missing_field(self, client):
        response = client.post("/transcribe-audio", json={})
        assert response.status_code == 422


class TestExtractFromTextEndpoint:
    def test_extract_from_text(self, client):
        response = client.post(
            "/extract-event-from-text",
            json={
                "text": "DJ Shadow at Berghain Berlin on March 20 2026 at 23:00, tickets 15 EUR"
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "eventDetails" in data
        details = data["eventDetails"]
        assert "name" in details
        assert "venue" in details or details.get("venue") == ""

    def test_extract_from_text_empty(self, client, mock_openai):
        # Make the LLM return empty extraction
        mock_openai.chat.completions.create.return_value.choices[
            0
        ].message.content = "{}"
        response = client.post("/extract-event-from-text", json={"text": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestExtractFromUrlEndpoint:
    @patch("agent.converters.httpx")
    def test_extract_from_url(self, mock_httpx, client):
        # Mock httpx.Client context manager
        mock_response = MagicMock()
        mock_response.text = (
            "<html><body>DJ Shadow at Berghain Berlin March 20 2026</body></html>"
        )
        mock_response.raise_for_status.return_value = None

        mock_http_client = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_http_client.__enter__ = lambda self: self
        mock_http_client.__exit__ = lambda self, *a: None
        mock_httpx.Client.return_value = mock_http_client

        response = client.post(
            "/extract-event-from-url",
            json={"url": "https://example.com/event", "language": "en"},
        )
        assert response.status_code == 200
        data = response.json()
        # May succeed or fail depending on mock setup, but shouldn't crash
        assert "success" in data

    def test_extract_from_url_missing_url(self, client):
        response = client.post("/extract-event-from-url", json={})
        assert response.status_code == 422


class TestExtractFromImageEndpoint:
    def test_extract_from_image(self, client):
        # Create a fake 1x1 PNG
        fake_image = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
        response = client.post(
            "/extract-event-details", json={"imageBase64": fake_image}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_extract_from_image_missing_field(self, client):
        response = client.post("/extract-event-details", json={})
        assert response.status_code == 422


class TestValidateEventEndpoint:
    def test_validate_event_success(self, client, mock_neo4j):
        response = client.post(
            "/validate-event",
            json={
                "event": {
                    "name": "Jazz Night",
                    "artist": "Miles Davis Tribute",
                    "description": "A tribute night",
                    "event_date": "2026-04-01T21:00:00",
                    "venue": "Blue Note",
                    "city": "New York",
                    "price": 25.0,
                    "ticket_url": "https://example.com/tickets",
                },
                "session_id": "test-session",
                "user_id": "test-user",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["event_name"] == "Test Event"
        assert data["artist"] == "Test Artist"

    def test_validate_event_free(self, client, mock_neo4j):
        response = client.post(
            "/validate-event",
            json={
                "event": {
                    "name": "Free Concert",
                    "event_date": "2026-04-01T21:00:00",
                    "venue": "Park",
                    "city": "Berlin",
                    "price": 0,
                },
                "session_id": "test-session",
                "user_id": "test-user",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_validate_event_missing_required_fields(self, client):
        response = client.post(
            "/validate-event",
            json={
                "event": {
                    "name": "Incomplete Event"
                    # Missing venue, city, event_date
                }
            },
        )
        assert response.status_code == 422

    def test_validate_event_neo4j_failure(self, client):
        with patch("agent.neo4j_writer._driver") as mock_driver:
            mock_session = MagicMock()
            mock_session.run.side_effect = Exception("Connection refused")
            mock_session.__enter__ = lambda self: self
            mock_session.__exit__ = lambda self, *a: None
            mock_driver.session.return_value = mock_session

            response = client.post(
                "/validate-event",
                json={
                    "event": {
                        "name": "Test Event",
                        "event_date": "2026-04-01T21:00:00",
                        "venue": "Test Venue",
                        "city": "Berlin",
                    }
                },
            )
            assert response.status_code == 500


class TestCurrencyDetection:
    def test_usd_city(self, client, mock_neo4j):
        response = client.post(
            "/validate-event",
            json={
                "event": {
                    "name": "NYC Show",
                    "event_date": "2026-04-01T21:00:00",
                    "venue": "Madison Square Garden",
                    "city": "New York",
                    "price": 50,
                }
            },
        )
        assert response.status_code == 200

    def test_default_eur(self, client, mock_neo4j):
        response = client.post(
            "/validate-event",
            json={
                "event": {
                    "name": "Unknown City Show",
                    "event_date": "2026-04-01T21:00:00",
                    "venue": "Some Venue",
                    "city": "Bratislava",
                    "price": 10,
                }
            },
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
