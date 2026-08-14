import json

from laiive_shared import (
    Done,
    Error,
    EventCard,
    EventDraft,
    EventsResult,
    FormExtracted,
    MessageDelta,
    Status,
    sse_frame,
)


def parse_frame(frame: str) -> tuple[str, dict]:
    lines = frame.strip().split("\n")
    assert lines[0].startswith("event: ")
    assert lines[1].startswith("data: ")
    return lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])


def test_message_delta_frame():
    event, data = parse_frame(sse_frame(MessageDelta(text="hola ")))
    assert event == "message.delta"
    assert data == {"text": "hola "}


def test_events_result_frame_drops_nones():
    card = EventCard(uid="u1", name="Jazz Night", artists=["Trio X"], source="seed")
    event, data = parse_frame(sse_frame(EventsResult(events=[card])))
    assert event == "events.result"
    assert data["events"][0]["uid"] == "u1"
    assert "venue" not in data["events"][0]  # exclude_none on the wire


def test_form_extracted_frame():
    draft = EventDraft(artists=["A"], venue="V", city="Madrid")
    event, data = parse_frame(
        sse_frame(FormExtracted(draft=draft, missing=["start_at"]))
    )
    assert event == "form.extracted"
    assert data["missing"] == ["start_at"]
    assert data["draft"]["city"] == "Madrid"
    assert (data["index"], data["total"]) == (0, 1)  # a lone event is 0 of 1


def test_form_extracted_carries_its_position_in_the_set():
    draft = EventDraft(artists=["A"])
    _, data = parse_frame(sse_frame(FormExtracted(draft=draft, index=2, total=12)))
    assert (data["index"], data["total"]) == (2, 12)


def test_scalar_frames():
    assert parse_frame(sse_frame(Status(state="searching")))[0] == "status"
    assert parse_frame(sse_frame(Error(code="bad_request", message="x")))[0] == "error"
    event, data = parse_frame(sse_frame(Done(request_id="r1")))
    assert (event, data) == ("done", {"request_id": "r1"})


def test_frames_are_double_newline_terminated():
    assert sse_frame(Status(state="composing")).endswith("\n\n")
