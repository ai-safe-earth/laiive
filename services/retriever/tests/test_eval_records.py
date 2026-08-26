"""eval_records: the PostgREST insert, its no-op guard, and its swallow-all.

Telemetry must never break a turn, so the failure tests assert silence.
`_http` is the patch seam, like search's tests.
"""

from unittest.mock import MagicMock, patch

from laiive_shared import EventCard

from agent import eval_records
from agent.classifier import Classification
from agent.pipeline import TurnResult
from config import settings

CARD = EventCard(
    uid="e1",
    name="Noche de Jazz",
    artists=["Marta Sánchez Trio"],
    venue="Café Central",
    city="Madrid",
    start_at="2026-08-20T21:00:00+00:00",
    source="seed",
)


def _result() -> TurnResult:
    result = TurnResult()
    result.text = "Jazz on the way."
    result.cards = [CARD]
    result.cyphers = ["MATCH (e:Event) RETURN e"]
    result.notes = ["widened radius"]
    result.errors = []
    result.classification = Classification(
        query_type="event_search", moment="first_query"
    )
    return result


def test_write_posts_the_turn():
    with (
        patch.object(settings, "supabase_url", "https://sb.test"),
        patch.object(settings, "supabase_service_role_key", "sk"),
        patch.object(eval_records, "_http") as http,
    ):
        http.post.return_value = MagicMock(status_code=201)
        eval_records.write("gw-123", _result(), 840)

    (url,), kwargs = http.post.call_args
    assert url == "https://sb.test/rest/v1/eval_records"
    assert kwargs["headers"]["Authorization"] == "Bearer sk"
    assert kwargs["json"] == {
        "request_id": "gw-123",
        "final_text": "Jazz on the way.",
        "card_uids": ["e1"],
        "cyphers": ["MATCH (e:Event) RETURN e"],
        "query_type": "event_search",
        "moment": "first_query",
        "retrieval_notes": ["widened radius"],
        "row_count": 1,
        "latency_ms": 840,
        "errors": [],
    }


def test_no_classification_writes_nulls():
    """A turn that died before the classifier still leaves a record."""
    with (
        patch.object(settings, "supabase_url", "https://sb.test"),
        patch.object(eval_records, "_http") as http,
    ):
        http.post.return_value = MagicMock(status_code=201)
        eval_records.write("gw-123", TurnResult(), 12)

    body = http.post.call_args.kwargs["json"]
    assert body["query_type"] is None
    assert body["moment"] is None


def test_empty_url_is_a_no_op():
    with patch.object(eval_records, "_http") as http:
        eval_records.write("gw-123", _result(), 840)  # conftest blanks SUPABASE_URL
    http.post.assert_not_called()


def test_failures_are_swallowed():
    with (
        patch.object(settings, "supabase_url", "https://sb.test"),
        patch.object(eval_records, "_http") as http,
    ):
        http.post.return_value = MagicMock(status_code=500, text="boom")
        eval_records.write("gw-123", _result(), 840)  # no raise
        http.post.side_effect = RuntimeError("connection refused")
        eval_records.write("gw-123", _result(), 840)  # no raise
