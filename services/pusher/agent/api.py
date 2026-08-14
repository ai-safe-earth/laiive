"""Pusher API — multimodal event submission via chat, voice, image, URL, batch."""

import asyncio
import base64
import json
import os
import re
import uuid
from typing import List, Literal, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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
    missing_required,
    sse_frame,
)
from loguru import logger
from pydantic import BaseModel, model_validator
from starlette.concurrency import run_in_threadpool

from . import graph
from .batch import drafts_with_missing, parse_batch
from .conversation import default_currency, process_turn
from .converters import (
    UnreadableDocument,
    audio_to_text,
    document_to_text,
    extract_draft_from_text,
    extract_from_url,
    image_to_text,
    url_to_text,
)

app = FastAPI(title="laiive pusher API", version="0.3.0")

# Browser traffic terminates at the gateway; direct browser access needs an
# explicit opt-in via SERVICE_CORS_ALLOW_ORIGINS (comma-separated).
_cors_origins = [
    o.strip()
    for o in os.environ.get("SERVICE_CORS_ALLOW_ORIGINS", "").split(",")
    if o.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============== Pydantic Models ==============


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatStreamRequest(BaseModel):
    messages: List[Message]
    # 'legacy' = OpenAI-shaped frames + __EVENT_EXTRACTED__ sentinel (current
    # frontend); 'v2' = named-event shared protocol (Phase 4 frontend).
    protocol: Literal["legacy", "v2"] = "legacy"


class TranscribeRequest(BaseModel):
    audio: str  # base64 encoded


class TranscribeResponse(BaseModel):
    text: str


class ExtractFromTextRequest(BaseModel):
    text: str


class ExtractFromUrlRequest(BaseModel):
    url: str
    language: str = "en"


class ExtractFromImageRequest(BaseModel):
    imageBase64: str


class EventDetailsModel(BaseModel):
    """Legacy form payload (current frontend). Dies with Phase 4."""

    name: str
    artist: Optional[str] = None
    description: Optional[str] = None
    event_date: str
    venue: str
    city: str
    price: Optional[float] = None
    ticket_url: Optional[str] = None


class ValidateEventRequest(BaseModel):
    """Either a full draft (new frontend) or the flat legacy form payload.

    `draft` carries genre, venue_type, address, price ranges and a real
    timestamp; `event` flattens all of that away, so the new form sends a draft
    and the legacy branch dies with the rest of the legacy paths in Phase 4c.
    """

    draft: Optional[EventDraft] = None
    event: Optional[EventDetailsModel] = None
    session_id: Optional[str] = None
    # owner identity is the gateway's X-User-Id header; a body user_id is ignored

    @model_validator(mode="after")
    def exactly_one_payload(self) -> "ValidateEventRequest":
        if (self.draft is None) == (self.event is None):
            raise ValueError("send either 'draft' (preferred) or 'event'")
        return self


class BatchValidateRequest(BaseModel):
    draft: EventDraft
    index: int
    total: int


# ============== Helpers ==============


def _create_sse_message(content: str) -> str:
    payload = json.dumps(
        {"choices": [{"delta": {"content": content}}]}, ensure_ascii=False
    )
    return f"data: {payload}\n\n"


def _create_sse_done() -> str:
    return "data: [DONE]\n\n"


def _legacy_details(draft: EventDraft) -> dict:
    """EventDraft → the legacy EventDetails shape the current frontend renders."""
    artist = draft.artists[0] if draft.artists else None
    return {
        "name": draft.name or (f"{artist} Live" if artist else ""),
        "artist": artist,
        "description": draft.description,
        "event_date": draft.start_at or "",
        "venue": draft.venue or "",
        "city": draft.city or "",
        "price": draft.price_min,
        "ticket_url": draft.ticket_url,
    }


def _details_to_draft(event: EventDetailsModel) -> EventDraft:
    return EventDraft(
        name=event.name,
        artists=[event.artist] if event.artist else [event.name],
        start_at=event.event_date,
        venue=event.venue,
        city=event.city,
        price_min=event.price if event.price is not None else 0.0,
        price_currency=default_currency(event.city),
        description=event.description,
        ticket_url=event.ticket_url,
    )


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
            "transcribe": "/transcribe-audio (POST)",
            "extract_text": "/extract-event-from-text (POST)",
            "extract_url": "/extract-event-from-url (POST)",
            "extract_image": "/extract-event-details (POST)",
            "validate": "/validate-event (POST)",
            "batch_parse": "/batch/parse (POST, multipart)",
            "batch_validate": "/batch/validate-event (POST)",
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
    generate = _generate_v2 if request.protocol == "v2" else _generate_legacy
    return StreamingResponse(
        generate(request_id, messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


async def _generate_v2(request_id: str, messages: list[dict]):
    """Named-event frames: form.extracted replaces the sentinel.

    A conversation that carries several events (a spreadsheet, a line-up)
    emits one frame per event, in source order — index/total is what lets the
    client walk them one form at a time.
    """
    try:
        yield sse_frame(Status(state="extracting"))
        turn = await asyncio.to_thread(process_turn, messages)
        if turn.show_form:
            total = len(turn.drafts)
            for index, (draft, missing) in enumerate(zip(turn.drafts, turn.missing)):
                yield sse_frame(
                    FormExtracted(
                        draft=draft, missing=missing, index=index, total=total
                    )
                )
        yield sse_frame(MessageDelta(text=turn.reply))
    except Exception as e:
        logger.error(f"[{request_id}] SSE stream error: {e}", exc_info=True)
        yield sse_frame(Error(code="internal_error", message="Something went wrong."))
    yield sse_frame(Done(request_id=request_id))


async def _generate_legacy(request_id: str, messages: list[dict]):
    """Legacy frames. The old frontend cannot render a partial form, so the
    one-round rule is off: the sentinel only fires when nothing is missing."""
    try:
        turn = await asyncio.to_thread(process_turn, messages, one_round_rule=False)
        if turn.show_form:
            details = json.dumps(_legacy_details(turn.draft))
            yield _create_sse_message(
                f"__EVENT_EXTRACTED__{details}__EVENT_EXTRACTED__"
            )
        else:
            for token in re.findall(r"\S+|\s+", turn.reply):
                yield _create_sse_message(token)
                if token.strip():
                    await asyncio.sleep(0.01)
    except Exception as e:
        logger.error(f"[{request_id}] SSE stream error: {e}", exc_info=True)
        yield _create_sse_message("An unexpected error occurred. Please try again.")
    yield _create_sse_done()


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


# ============== Transcription ==============


@app.post("/transcribe-audio", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest):
    """Transcribe base64-encoded audio to text using Whisper."""
    try:
        audio_bytes = base64.b64decode(request.audio)
        if not audio_bytes:
            raise HTTPException(400, "Empty audio data")
        text = audio_to_text(audio_bytes, filename="audio.webm")
        return TranscribeResponse(text=text)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(500, f"Transcription failed: {str(e)}")


# ============== Event Extraction ==============


@app.post("/extract-event-from-text")
async def extract_event_from_text(request: ExtractFromTextRequest):
    """Extract event details from plain text."""
    try:
        draft = extract_draft_from_text(request.text)
        if not draft.model_dump(exclude_none=True, exclude_defaults=True):
            return {
                "success": False,
                "error": "Could not extract event details from text",
            }
        return {
            "success": True,
            "eventDetails": _legacy_details(draft),
            "draft": draft.model_dump(exclude_none=True),
            "missing": missing_required(draft),
        }
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/extract-event-from-url")
async def extract_event_from_url(request: ExtractFromUrlRequest):
    """Extract event details from a URL."""
    try:
        draft = extract_from_url(request.url, language=request.language)
        if not draft.model_dump(exclude_none=True, exclude_defaults=True):
            return {
                "success": False,
                "error": "Could not extract event details from URL",
            }
        return {
            "success": True,
            "eventData": _legacy_details(draft),
            "draft": draft.model_dump(exclude_none=True),
            "missing": missing_required(draft),
        }
    except Exception as e:
        logger.error(f"URL extraction failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/extract-event-details")
async def extract_event_details(request: ExtractFromImageRequest):
    """Extract event details from a base64-encoded image."""
    try:
        image_bytes = base64.b64decode(request.imageBase64)
        if not image_bytes:
            raise HTTPException(400, "Empty image data")
        text = image_to_text(image_bytes, mime_type="image/png")
        draft = extract_draft_from_text(text)
        if not draft.model_dump(exclude_none=True, exclude_defaults=True):
            return {
                "success": False,
                "error": "Could not extract event details from image",
            }
        return {
            "success": True,
            "eventDetails": _legacy_details(draft),
            "draft": draft.model_dump(exclude_none=True),
            "missing": missing_required(draft),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        return {"success": False, "error": str(e)}


# ============== Validation / Publication ==============


@app.post("/validate-event")
async def validate_event(
    request: ValidateEventRequest,
    x_user_id: Optional[str] = Header(None),
):
    """Publish a form-approved event — the only write trigger."""
    draft = (
        request.draft if request.draft is not None else _details_to_draft(request.event)
    )
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


# ============== Batch ==============


@app.post("/batch/parse")
async def batch_parse(file: UploadFile = File(...)):
    """CSV/XLSX upload → drafts with their missing fields ("event i of N")."""
    try:
        content = await file.read()
        drafts = parse_batch(content, file.filename or "upload.csv")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.error(f"Batch parse failed: {e}")
        raise HTTPException(500, f"Could not parse file: {e}")
    if not drafts:
        raise HTTPException(422, "No event rows found in the file")
    return {"total": len(drafts), "drafts": drafts_with_missing(drafts)}


@app.post("/batch/validate-event")
async def batch_validate_event(
    request: BatchValidateRequest,
    x_user_id: Optional[str] = Header(None),
):
    """Publish draft i of N after the promoter approved its form."""
    draft = request.draft
    if draft.city and not draft.price_currency:
        draft.price_currency = default_currency(draft.city)
    result = _write_or_raise(draft, owner_id=x_user_id)
    return {
        "success": True,
        "index": request.index,
        "total": request.total,
        "event_id": result.uid,
        "event_name": result.name,
        "warnings": result.warnings,
    }
