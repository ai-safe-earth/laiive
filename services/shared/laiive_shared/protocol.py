"""Typed SSE protocol shared by retriever, pusher, and the frontend.

Named SSE events (02-architecture §2):

    event: message.delta   data: {"text": "…"}
    event: events.result   data: {"events": [EventCard…]}
    event: form.extracted  data: {"event": EventDraft, "missing": []}
    event: batch.progress  data: {"index": 1, "total": 5}
    event: status          data: {"state": "searching"}
    event: error           data: {"code": "…", "message": "…"}
    event: done            data: {"request_id": "…"}

Emit frames with `sse_frame(payload)`; the event name comes from the payload
type, so a frame can never carry the wrong name.
"""

from typing import ClassVar

from pydantic import BaseModel

from .cards import EventCard, EventDraft


class MessageDelta(BaseModel):
    event: ClassVar[str] = "message.delta"
    text: str


class EventsResult(BaseModel):
    event: ClassVar[str] = "events.result"
    events: list[EventCard]


class FormExtracted(BaseModel):
    event: ClassVar[str] = "form.extracted"
    draft: EventDraft
    missing: list[str] = []


class BatchProgress(BaseModel):
    event: ClassVar[str] = "batch.progress"
    index: int
    total: int


class Status(BaseModel):
    event: ClassVar[str] = "status"
    state: str  # e.g. classifying | searching | composing | extracting | writing


class Error(BaseModel):
    event: ClassVar[str] = "error"
    code: str
    message: str


class Done(BaseModel):
    event: ClassVar[str] = "done"
    request_id: str


Frame = (
    MessageDelta | EventsResult | FormExtracted | BatchProgress | Status | Error | Done
)


def sse_frame(payload: Frame) -> str:
    """Serialize a payload model into a named SSE frame."""
    data = payload.model_dump_json(exclude_none=True)
    return f"event: {payload.event}\ndata: {data}\n\n"
