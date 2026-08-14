"""Pusher API — multimodal event submission via chat, voice, image and URL."""

import asyncio
import uuid
from typing import List, Literal, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from laiive_shared import (
    ALLOWED_AUDIO_SUFFIXES,
    AudioTooLarge,
    Done,
    Error,
    EventDraft,
    FormExtracted,
    MessageDelta,
    Status,
    UnsupportedAudioFormat,
    WalkState,
    sse_frame,
)
from loguru import logger
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import graph
from .conversation import WalkInput, process_turn
from .converters import (
    UnreadableDocument,
    audio_to_text,
    document_to_text,
    image_to_text,
    url_to_text,
)

app = FastAPI(title="laiive pusher API", version="0.3.0")

# No CORS middleware on purpose: browser traffic terminates at the gateway, and
# the service is only reachable through it (compose `expose`s it, `make start-*`
# binds 127.0.0.1). The SERVICE_CORS_ALLOW_ORIGINS escape hatch existed for the
# Phase 3 frontend that still called 8002/8003 directly; that frontend is gone.


# ============== Pydantic Models ==============


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class WalkModel(BaseModel):
    """The client-carried walk state: the draft set walk.state handed the
    browser, echoed back with the cursor so the server stays stateless."""

    drafts: List[EventDraft]
    cursor: int = 0


class ChatStreamRequest(BaseModel):
    messages: List[Message]
    walk: Optional[WalkModel] = None


class ValidateEventRequest(BaseModel):
    """The full draft the review form approved.

    A draft carries genre, venue_type, address, price ranges and a real
    timestamp. The flat `event` payload that flattened all of that away went
    with the old frontend.
    """

    draft: EventDraft
    # owner identity is the gateway's X-User-Id header; a body user_id is ignored


# ============== Helpers ==============


def _write_or_raise(draft: EventDraft, owner_id: str | None):
    result = graph.write_event(draft, owner_id=owner_id)
    if result.status == "invalid":
        raise HTTPException(422, result.message)
    if result.status == "duplicate":
        raise HTTPException(409, result.message)
    if result.status == "error":
        raise HTTPException(500, result.message)
    return result


# ============== Health ==============


@app.get("/")
def root():
    return {
        "service": "laiive pusher API",
        "version": "0.3.0",
        "endpoints": {
            "health": "/health",
            "chat_stream": "/chat/stream (POST) - SSE streaming",
            "ingest": "/ingest (POST, multipart) - audio/image/document/url → text",
            "validate": "/validate-event (POST)",
        },
    }


@app.get("/health")
def health():
    checks = {"api": "ok", "neo4j": "unknown"}
    try:
        graph._driver.verify_connectivity()
        checks["neo4j"] = "ok"
    except Exception as e:
        logger.warning(f"Neo4j health check failed: {e}")
        checks["neo4j"] = "error"
    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}


# ============== SSE Chat ==============


@app.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    """Submission chat. One clarification round, then the form — always."""
    if not request.messages:
        raise HTTPException(400, "No messages provided")
    request_id = str(uuid.uuid4())
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    walk = (
        WalkInput(drafts=request.walk.drafts, cursor=request.walk.cursor)
        if request.walk
        else None
    )
    return StreamingResponse(
        _generate(request_id, messages, walk),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


async def _generate(request_id: str, messages: list[dict], walk: WalkInput | None):
    """Named-event frames: form.extracted replaces the sentinel.

    A conversation that carries several events (a spreadsheet, a line-up)
    walks them one per turn: walk.state carries the whole set for the client
    to persist and echo back, form.extracted only the event under the cursor.
    A single event stays one form.extracted, index 0 of 1.
    """
    try:
        yield sse_frame(Status(state="extracting"))
        turn = await asyncio.to_thread(process_turn, messages, walk)
        if turn.walk:
            total = len(turn.drafts)
            yield sse_frame(
                WalkState(
                    drafts=turn.drafts,
                    missing=turn.missing,
                    cursor=turn.cursor,
                    total=total,
                )
            )
            yield sse_frame(
                FormExtracted(
                    draft=turn.drafts[turn.cursor],
                    missing=turn.missing[turn.cursor],
                    index=turn.cursor,
                    total=total,
                )
            )
        elif turn.show_form:
            yield sse_frame(
                FormExtracted(
                    draft=turn.drafts[0], missing=turn.missing[0], index=0, total=1
                )
            )
        yield sse_frame(MessageDelta(text=turn.reply))
    except Exception as e:
        logger.error(f"[{request_id}] SSE stream error: {e}", exc_info=True)
        yield sse_frame(Error(code="internal_error", message="Something went wrong."))
    yield sse_frame(Done(request_id=request_id))


# ============== Multimodal ingestion ==============


@app.post("/ingest")
async def ingest(
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
):
    """Turn any input modality into plain text.

    Voice, flyer photo, PDF/DOCX and links all reduce to text here; the client
    then appends that text to the conversation as an ordinary user message and
    the normal turn extracts the fields. That is the whole point of this
    endpoint: **one** extraction path over the whole conversation, so a photo
    that supplies the venue and a follow-up sentence that supplies the price
    merge into one draft without any client-side merge rules.

    Returns `{kind, source, text}`. Extraction deliberately does not happen
    here — /chat/stream owns it.
    """
    if url:
        text = await run_in_threadpool(url_to_text, url)
        return {"kind": "url", "source": url, "text": text}

    if file is None:
        raise HTTPException(400, "Send a file or a url")

    payload = await file.read()
    filename = file.filename or "upload"
    content_type = file.content_type or ""

    try:
        if content_type.startswith("audio/") or filename.lower().endswith(
            ALLOWED_AUDIO_SUFFIXES
        ):
            text = await run_in_threadpool(audio_to_text, payload, filename)
            kind = "audio"
        elif content_type.startswith("image/"):
            text = await run_in_threadpool(image_to_text, payload, content_type)
            kind = "image"
        else:
            text = await run_in_threadpool(document_to_text, payload, filename)
            kind = "document"
    except AudioTooLarge as e:
        raise HTTPException(413, str(e)) from e
    except (UnsupportedAudioFormat, UnreadableDocument, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.error(f"Ingestion of {filename} ({content_type}) failed: {e}")
        raise HTTPException(502, "Could not read that file") from e

    if not text.strip():
        raise HTTPException(422, f"No readable event information in {filename}")

    return {"kind": kind, "source": filename, "text": text}


# ============== Validation / Publication ==============


@app.post("/validate-event")
async def validate_event(
    request: ValidateEventRequest,
    x_user_id: Optional[str] = Header(None),
):
    """Publish a form-approved event — the only write trigger."""
    draft = request.draft
    # owner identity comes only from the gateway-verified header, never the body
    result = _write_or_raise(draft, owner_id=x_user_id)
    return {
        "success": True,
        "event_id": result.uid,
        "event_name": result.name,
        "artist": draft.artists[0] if draft.artists else None,
        "venue": result.venue,
        "city": result.city,
        "warnings": result.warnings,
    }
