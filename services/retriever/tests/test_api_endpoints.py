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

    def run_turn(
        self, user_message, history=None, location=None, result=None, timezone=None
    ):
        self.seen_timezone = timezone
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

    def run_turn_collected(
        self, user_message, history=None, location=None, timezone=None
    ):
        from agent.pipeline import TurnResult

        result = TurnResult()
        for _ in self.run_turn(
            user_message, history, location, result=result, timezone=timezone
        ):
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
    def test_the_askers_timezone_reaches_the_pipeline(self, client):
        """It decides what "today" means, so a silent drop is an off-by-one-day
        bug that only shows up for users east or west of the server."""
        pipeline = FakePipeline()
        api_module._pipeline = pipeline
        client.post("/chat", json={"message": "tonight", "timezone": "Europe/Rome"})
        assert pipeline.seen_timezone == "Europe/Rome"

    def test_a_request_without_a_timezone_still_answers(self, client):
        """Every client sent none before this existed, and the JSON endpoint is
        callable by things that are not the browser."""
        pipeline = FakePipeline()
        api_module._pipeline = pipeline
        data = client.post("/chat", json={"message": "jazz"}).json()
        assert pipeline.seen_timezone is None
        assert "request_id" in data

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


class TestRequestId:
    """The gateway's x-request-id is the join key with conversation_logs —
    minting a local uuid instead makes the eval record unjoinable."""

    def test_stream_adopts_the_gateway_id(self, client):
        response = client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "jazz"}]},
            headers={"x-request-id": "gw-123"},
        )
        assert response.headers["x-request-id"] == "gw-123"
        assert '"request_id":"gw-123"' in response.text  # the done frame

    def test_chat_adopts_the_gateway_id(self, client):
        data = client.post(
            "/chat", json={"message": "jazz"}, headers={"x-request-id": "gw-123"}
        ).json()
        assert data["request_id"] == "gw-123"

    def test_direct_calls_still_get_an_id(self, client):
        data = client.post("/chat", json={"message": "jazz"}).json()
        assert data["request_id"]

    def test_both_paths_write_an_eval_record(self, client):
        with patch.object(api_module, "_write_eval_record") as write:
            client.post(
                "/chat/stream",
                json={"messages": [{"role": "user", "content": "jazz"}]},
                headers={"x-request-id": "gw-123"},
            )
            client.post(
                "/chat", json={"message": "jazz"}, headers={"x-request-id": "gw-456"}
            )
        ids = [call.args[0] for call in write.call_args_list]
        assert ids == ["gw-123", "gw-456"]


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


class TestEntityLookup:
    """/venues and /artists: lookups for a picker (the pro form, the org
    screen), not a search — and the first non-Event read paths."""

    def test_venues_by_fragment_with_the_city_scope_intact(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = [
                {
                    "uid": "v1",
                    "name": "Razzmatazz",
                    "venue_type": "club",
                    "address": "Carrer dels Almogavers 122",
                    "city": "Barcelona",
                }
            ]
            response = client.get("/venues?q=razz&city=Barcelona")
        assert response.status_code == 200
        assert response.json()["venues"][0]["uid"] == "v1"
        cypher, params = neo4j.execute_read_once.call_args[0]
        assert params == {"q_norm": "razz", "city_norm": "barcelona"}
        assert "c.name_norm = $city_norm" in cypher

    def test_venues_by_uid_ask_the_graph_by_uid_not_by_name(self, client):
        """The claim path: a uid in, the graph's own name out.

        The gateway records who an organization speaks for, so the stored
        display name has to come from here rather than from whatever the
        client typed alongside the uid.
        """
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = [
                {
                    "uid": "v1",
                    "name": "Razzmatazz",
                    "venue_type": "club",
                    "address": "Carrer dels Almogavers 122",
                    "city": "Barcelona",
                }
            ]
            response = client.get("/venues?uids=v1,v2,v1")
        assert response.status_code == 200
        assert response.json()["venues"][0]["name"] == "Razzmatazz"
        cypher, params = neo4j.execute_read_once.call_args[0]
        # De-duplicated, order preserved, and asked by uid rather than fragment.
        assert params == {"uids": ["v1", "v2"]}
        assert "v.uid IN $uids" in cypher
        assert "name_norm" not in cypher

    def test_uids_win_over_q_and_skip_the_fragment_floor(self, client):
        """`uids` is the mode selector: a one-character q must not 400 here."""
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = []
            response = client.get("/venues?q=r&uids=v1")
        assert response.status_code == 200
        _, params = neo4j.execute_read_once.call_args[0]
        assert params == {"uids": ["v1"]}

    def test_an_unknown_uid_is_nothing_not_an_error(self, client):
        """Same contract as /events: a stale pointer is not a bad request."""
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = []
            response = client.get("/artists?uids=gone")
        assert response.status_code == 200
        assert response.json()["artists"] == []

    def test_too_many_uids_are_refused_before_the_graph(self, client):
        from agent.executor import EVENT_LOOKUP_MAX_UIDS

        too_many = ",".join(f"v{i}" for i in range(EVENT_LOOKUP_MAX_UIDS + 1))
        with patch.object(api_module, "neo4j_client") as neo4j:
            response = client.get(f"/venues?uids={too_many}")
        assert response.status_code == 400
        neo4j.execute_read_once.assert_not_called()

    def test_artists_by_uid_still_carry_their_genres(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = [
                {"uid": "a1", "name": "Ana Trio", "genres": ["Jazz"]}
            ]
            response = client.get("/artists?uids=a1")
        assert response.json()["artists"][0]["genres"] == ["Jazz"]
        cypher, _ = neo4j.execute_read_once.call_args[0]
        assert "a.uid IN $uids" in cypher

    def test_a_one_character_fragment_is_refused_before_the_graph(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            response = client.get("/venues?q=r")
        assert response.status_code == 400
        neo4j.execute_read_once.assert_not_called()

    def test_a_row_without_a_uid_is_dropped_not_returned(self, client):
        """A hit the client cannot reference is not a hit."""
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = [
                {
                    "uid": None,
                    "name": "Old Seed",
                    "venue_type": None,
                    "address": None,
                    "city": "Berlin",
                },
            ]
            response = client.get("/venues?q=old")
        assert response.json()["venues"] == []

    def test_a_driver_failure_is_a_502(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.side_effect = Exception("paused")
            assert client.get("/venues?q=razz").status_code == 502

    def test_lookups_take_the_unretried_read_path(self, client):
        """The retry ladder is for answers worth waiting on; a typeahead
        fragment is not one — the next keystroke is the retry."""
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = []
            client.get("/venues?q=razz")
            client.get("/artists?q=ana")
        neo4j.execute_read.assert_not_called()

    def test_artists_by_fragment_carry_their_genres(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = [
                {"uid": "a1", "name": "Ana Beck Quartet", "genres": ["Jazz"]},
            ]
            response = client.get("/artists?q=ana")
        assert response.status_code == 200
        assert response.json()["artists"][0]["genres"] == ["Jazz"]

    def test_lookups_never_build_the_pipeline(self, client):
        api_module._pipeline = None
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read_once.return_value = []
            client.get("/venues?q=razz")
            client.get("/artists?q=ana")
        assert api_module._pipeline is None


class TestEventsByUid:
    """The saved list's read path: uids in, fresh cards out."""

    @staticmethod
    def _row(uid: str, name: str) -> dict:
        return {"uid": uid, "name": name, "artists": [], "source": "pro_submission"}

    def test_returns_cards_in_the_order_they_were_asked_for(self, client):
        """The list is ordered by when each event was saved, and only the
        caller knows that — the graph returns rows in its own order."""
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read.return_value = [
                self._row("e2", "second"),
                self._row("e1", "first"),
            ]
            response = client.get("/events?uids=e1,e2")
        assert response.status_code == 200
        assert [c["uid"] for c in response.json()["events"]] == ["e1", "e2"]

    def test_trims_blanks_and_asks_once_per_uid(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read.return_value = []
            client.get("/events?uids= e1 ,,e1,e2")
        assert neo4j.execute_read.call_args[0][1] == {"uids": ["e1", "e2"]}

    def test_an_empty_list_never_reaches_the_graph(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            response = client.get("/events?uids=")
        assert response.status_code == 200
        assert response.json()["events"] == []
        neo4j.execute_read.assert_not_called()

    def test_too_many_uids_is_refused_not_truncated(self, client):
        uids = ",".join(f"e{i}" for i in range(api_module.EVENT_LOOKUP_MAX_UIDS + 1))
        with patch.object(api_module, "neo4j_client") as neo4j:
            response = client.get(f"/events?uids={uids}")
        assert response.status_code == 400
        neo4j.execute_read.assert_not_called()

    def test_a_uid_the_graph_no_longer_has_is_simply_absent(self, client):
        """A deleted event is a stale pointer in somebody's list, not a 404."""
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read.return_value = [self._row("e1", "still here")]
            response = client.get("/events?uids=e1,gone")
        assert response.status_code == 200
        assert [c["uid"] for c in response.json()["events"]] == ["e1"]

    def test_a_driver_failure_is_a_502(self, client):
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read.side_effect = Exception("no write service")
            response = client.get("/events?uids=e1")
        assert response.status_code == 502

    def test_it_never_builds_the_pipeline(self, client):
        """The executable form of "importing agent.api needs no Neo4j": a
        saved list must not be what constructs an OpenAI client."""
        api_module._pipeline = None
        with patch.object(api_module, "neo4j_client") as neo4j:
            neo4j.execute_read.return_value = []
            client.get("/events?uids=e1")
        assert api_module._pipeline is None
