"""Typed SSE protocol shared by retriever, pusher, and the frontend.

Named SSE events (02-architecture §2):

    event: message.delta   data: {"text": "…"}
    event: events.result   data: {"events": [EventCard…]}
    event: form.extracted  data: {"draft": EventDraft, "missing": [], "index": 0, "total": 1}
    event: status          data: {"state": "searching"}
    event: error           data: {"code": "…", "message": "…"}
    event: done            data: {"request_id": "…"}

A submission turn that recognizes several events at once (a spreadsheet, a
festival line-up) starts a *walk*: the promoter is taken through the set one
event per turn. `walk.state` carries the whole set — the client persists it
and echoes it back with each message, so the server stays stateless — while
`form.extracted` carries only the event under the cursor. A single event
never enters a walk: it is one `form.extracted` with index 0 of 1.

    event: walk.state      data: {"drafts": [EventDraft…], "missing": [[]…], "cursor": 0, "total": 5}

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
    index: int = 0
    total: int = 1


class WalkState(BaseModel):
    event: ClassVar[str] = "walk.state"
    drafts: list[EventDraft]
    missing: list[list[str]]  # parallel to drafts
    cursor: int
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


Frame = MessageDelta | EventsResult | FormExtracted | WalkState | Status | Error | Done


def sse_frame(payload: Frame) -> str:
    """Serialize a payload model into a named SSE frame."""
    data = payload.model_dump_json(exclude_none=True)
    return f"event: {payload.event}\ndata: {data}\n\n"
