"""
FastAPI endpoint tests — health checks, chat endpoints, both SSE protocols.
The pipeline is faked; no Neo4j or OpenAI needed.
"""

import inspect
import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from laiive_shared import EventCard, EventsResult, MessageDelta, Status

import agent.api as api_module
from agent.classifier import Classification

CARD = EventCard(
    uid="e1",
    name="Noche de Jazz",
    artists=["Marta Sánchez Trio"],
    venue="Café Central",
    city="Madrid",
    start_at="2026-08-20T21:00:00+00:00",
    price_min=15.0,
    source="seed",
)


class FakePipeline:
    """Replays a scripted turn and fills the TurnResult like the real one."""

    def __init__(
        self, cards=None, text="Jazz on the way.", cyphers=None, moment="first_query"
    ):
        self.cards = cards if cards is not None else [CARD]
        self.text = text
        self.cyphers = cyphers if cyphers is not None else ["MATCH (e:Event) RETURN e"]
        self.moment = moment

    def run_turn(self, user_message, history=None, location=None, result=None):
        result.classification = Classification(
            query_type="event_search", moment=self.moment
        )
        yield Status(state="classifying")
        if self.cyphers:
            yield Status(state="searching")
            result.cyphers = list(self.cyphers)
            result.cards = list(self.cards)
            yield EventsResult(events=result.cards)
        yield Status(state="composing")
        for token in self.text.split(" "):
            delta = token + " "
            result.text += delta
            yield MessageDelta(text=delta)

    def run_turn_collected(self, user_message, history=None, location=None):
        from agent.pipeline import TurnResult

        result = TurnResult()
        for _ in self.run_turn(user_message, history, location, result=result):
            pass
        return result


@pytest.fixture
def client():
    api_module._pipeline = FakePipeline()
    with TestClient(api_module.app) as test_client:
        yield test_client
    api_module._pipeline = None


class TestHealthEndpoints:
    def test_root_endpoint(self, client):
        data = client.get("/").json()
        assert data["version"] == "0.3.0"
        assert "chat/stream" in data["endpoints"]

    def test_health_all_ok(self, client):
        with (
            patch.object(api_module, "neo4j_client") as neo4j,
            patch("agent.utils.llm_utils.get_openai_client") as get_client,
        ):
            neo4j._driver.verify_connectivity.return_value = True
            get_client.return_value.models.list.return_value = []
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["checks"] == {
            "api": "ok",
            "neo4j": "ok",
            "openai": "ok",
        }

    def test_health_neo4j_down(self, client):
        with (
            patch.object(api_module, "neo4j_client") as neo4j,
            patch("agent.utils.llm_utils.get_openai_client") as get_client,
        ):
            neo4j._driver.verify_connectivity.side_effect = Exception("refused")
            get_client.return_value.models.list.return_value = []
            response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["checks"]["neo4j"] == "error"

    def test_health_openai_down(self, client):
        with (
            patch.object(api_module, "neo4j_client") as neo4j,
            patch("agent.utils.llm_utils.get_openai_client") as get_client,
        ):
            neo4j._driver.verify_connectivity.return_value = True
            get_client.return_value.models.list.side_effect = Exception("bad key")
            response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["checks"]["openai"] == "error"

    def test_schema_endpoint(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.get_schema.return_value = "Test Schema"
            data = client.get("/schema").json()
        assert data == {"schema": "Test Schema", "status": "ok"}

    def test_schema_endpoint_error(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.get_schema.side_effect = Exception("boom")
            data = client.get("/schema").json()
        assert data["status"] == "error"
        assert data["schema"] is None


class TestChatEndpoint:
    def test_chat_returns_cards_and_prose(self, client):
        data = client.post("/chat", json={"message": "jazz in madrid"}).json()
        assert "request_id" in data
        assert data["used_query"] is True
        assert data["results"][0]["uid"] == "e1"
        # prose and structured results, never prose *containing* the results
        assert data["response"].strip() == "Jazz on the way."
        assert data["cypher"] == "MATCH (e:Event) RETURN e"

    def test_chat_needs_more_info(self, client):
        api_module._pipeline = FakePipeline(
            cards=[],
            cyphers=[],
            text="Which city are we talking about?",
            moment="ambiguous",
        )
        data = client.post("/chat", json={"message": "find concerts"}).json()
        assert data["needs_more_info"] is True
        assert data["used_query"] is False
        assert data["results"] is None

    def test_chat_error_returns_500(self, client):
        broken = MagicMock()
        broken.run_turn_collected.side_effect = Exception("pipeline died")
        api_module._pipeline = broken
        response = client.post("/chat", json={"message": "x"})
        assert response.status_code == 500

    def test_chat_invalid_request(self, client):
        assert client.post("/chat", json={}).status_code == 422


class TestChatStreamRequests:
    def test_no_messages_is_400(self, client):
        assert client.post("/chat/stream", json={"messages": []}).status_code == 400

    def test_invalid_role_is_422(self, client):
        response = client.post(
            "/chat/stream", json={"messages": [{"role": "nope", "content": "x"}]}
        )
        assert response.status_code == 422


class TestChatStreamV2:
    def test_v2_named_events(self, client):
        response = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "jazz in madrid"}],
                "protocol": "v2",
            },
        )
        body = response.text
        assert "event: status" in body
        assert "event: events.result" in body
        assert "event: message.delta" in body
        assert "event: done" in body
        # events.result must arrive before the first prose delta
        assert body.index("event: events.result") < body.index("event: message.delta")

    def test_v2_location_accepted(self, client):
        response = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "near me"}],
                "location": {"latitude": 52.52, "longitude": 13.4, "city": "Berlin"},
                "protocol": "v2",
            },
        )
        assert response.status_code == 200

    def test_v2_pipeline_error_emits_error_frame(self, client):
        class ExplodingPipeline(FakePipeline):
            def run_turn(self, *args, **kwargs):
                yield Status(state="classifying")
                raise RuntimeError("boom")

        api_module._pipeline = ExplodingPipeline()
        body = client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "x"}], "protocol": "v2"},
        ).text
        assert "event: error" in body
        assert "event: done" in body  # stream still terminates cleanly


class TestTranscribe:
    """Voice input is public (D7): anonymous callers reach this through the
    gateway, so the size/format guards run before the metered Whisper call."""

    def _post(self, client, name="note.webm", body=b"audio-bytes"):
        return client.post(
            "/transcribe", files={"file": (name, io.BytesIO(body), "audio/webm")}
        )

    def test_returns_the_transcript(self, client):
        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = MagicMock(
            text=" jazz in madrid "
        )
        with patch.object(api_module, "get_openai_client", return_value=fake):
            response = self._post(client)
        assert response.status_code == 200
        assert response.json() == {"text": "jazz in madrid"}

    def test_oversized_recording_is_413(self, client):
        from laiive_shared.speech import MAX_AUDIO_BYTES

        fake = MagicMock()
        with patch.object(api_module, "get_openai_client", return_value=fake):
            response = self._post(client, body=b"x" * (MAX_AUDIO_BYTES + 1))
        assert response.status_code == 413
        fake.audio.transcriptions.create.assert_not_called()

    def test_unsupported_format_is_400(self, client):
        fake = MagicMock()
        with patch.object(api_module, "get_openai_client", return_value=fake):
            response = self._post(client, name="note.aiff")
        assert response.status_code == 400

    def test_upstream_failure_is_502(self, client):
        fake = MagicMock()
        fake.audio.transcriptions.create.side_effect = RuntimeError("whisper down")
        with patch.object(api_module, "get_openai_client", return_value=fake):
            response = self._post(client)
        assert response.status_code == 502


class TestStreamingIsIncremental:
    """The frame generator must stay a *sync* generator.

    `run_turn` blocks (OpenAI + Neo4j). As async generators these hold the
    event loop between yields, so uvicorn only flushes the frames once the
    turn is finished — the endpoint answers in one burst and streaming is a
    lie. Sync generators get iterated in Starlette's threadpool instead.
    """

    def test_generator_is_sync(self):
        assert not inspect.isasyncgenfunction(api_module._generate)
        assert inspect.isgeneratorfunction(api_module._generate)


class TestRequestValidation:
    def test_location_type_validation(self, client):
        response = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "x"}],
                "location": {"latitude": "not-a-float", "longitude": 13.4},
            },
        )
        assert response.status_code == 422

    def test_protocol_field_is_gone_and_ignored(self, client):
        """A stale client sending the old switch gets the only protocol there
        is, not a 422 — the field stopped being part of the contract."""
        response = client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "x"}], "protocol": "legacy"},
        )
        assert response.status_code == 200
        assert "event: done" in response.text
