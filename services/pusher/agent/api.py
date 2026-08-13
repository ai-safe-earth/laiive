"""Pusher API — multimodal event submission via chat, voice, image, URL, and text extraction."""

import uuid
import base64
import asyncio
import json
from typing import Optional, List, Literal

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .conversation import sessions
from .converters import (
    audio_to_text,
    image_to_text,
    extract_from_url,
    extract_fields_from_text,
)
from .neo4j_writer import write_event

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="laiive pusher API", version="0.2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Pydantic Models ==============


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatStreamRequest(BaseModel):
    """SSE streaming chat request (matches frontend PromoterCreate)."""

    messages: List[Message]
    language: str = "en"


class ChatRequest(BaseModel):
    """Legacy JSON chat request."""

    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    fields: dict
    confirmed: bool
    event: Optional[dict] = None


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
    name: str
    artist: Optional[str] = None
    description: Optional[str] = None
    event_date: str
    venue: str
    city: str
    price: Optional[float] = None
    ticket_url: Optional[str] = None


class ValidateEventRequest(BaseModel):
    event: EventDetailsModel
    session_id: Optional[str] = None
    user_id: Optional[str] = None


# ============== SSE Helpers ==============


def _create_sse_message(content: str) -> str:
    message = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(message)}\n\n"


def _create_sse_done() -> str:
    return "data: [DONE]\n\n"


# ============== Helpers ==============


def _handle_message(session_id: str, text: str) -> ChatResponse:
    """Shared logic: feed text into the conversation session."""
    session = sessions.get_or_create(session_id)
    reply = session.chat(text)

    event_result = None
    if session.confirmed:
        event_data = session.to_event_data()
        try:
            event_result = write_event(event_data)
            if event_result.get("status") == "success":
                reply += (
                    f"\n\nEvent saved! **{event_result['event_name']}** "
                    f"by {event_result['artist']} at {event_result['venue']}, "
                    f"{event_result['city']}."
                )
                sessions.remove(session_id)
            else:
                logger.error(
                    f"Write failed for session {session_id}: {event_result.get('error')}"
                )
                reply += "\n\nFailed to save the event. Please try again."
                session.confirmed = False
        except Exception as e:
            logger.error(f"Write failed for session {session_id}: {e}")
            reply += "\n\nError saving event. Please try again."
            session.confirmed = False

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        fields={k: v for k, v in session.fields.items() if v},
        confirmed=session.confirmed,
        event=event_result,
    )


def _event_details_from_fields(fields: dict) -> dict:
    """Convert extracted fields dict to EventDetails format for frontend."""
    price = None
    if fields.get("price"):
        try:
            price_str = str(fields["price"]).lower().strip()
            if price_str not in ("free", "0", ""):
                price = float(price_str.replace(",", "."))
            else:
                price = 0.0
        except (ValueError, TypeError):
            pass

    return {
        "name": fields.get("description") or fields.get("artist", ""),
        "artist": fields.get("artist"),
        "description": fields.get("description"),
        "event_date": fields.get("date_time") or fields.get("event_date", ""),
        "venue": fields.get("venue", ""),
        "city": fields.get("city", ""),
        "price": price,
        "ticket_url": fields.get("ticket_url"),
    }


# ============== Health ==============


@app.get("/")
def root():
    return {
        "service": "laiive pusher API",
        "version": "0.2.0",
        "endpoints": {
            "health": "/health",
            "chat_stream": "/chat/stream (POST) - SSE streaming",
            "chat": "/chat (POST) - JSON response",
            "transcribe": "/transcribe-audio (POST)",
            "extract_text": "/extract-event-from-text (POST)",
            "extract_url": "/extract-event-from-url (POST)",
            "extract_image": "/extract-event-details (POST)",
            "validate": "/validate-event (POST)",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ============== SSE Chat Stream ==============


@app.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    """SSE streaming chat for conversational event extraction.

    When all fields are collected and confirmed, emits:
      __EVENT_EXTRACTED__{json}__EVENT_EXTRACTED__
    """
    if not request.messages:
        raise HTTPException(400, "No messages provided")

    user_message = request.messages[-1].content
    conversation_history = request.messages[:-1] if len(request.messages) > 1 else []

    # Stable session ID: hash from the first user message so it persists across turns
    first_msg = (
        conversation_history[0].content if conversation_history else user_message
    )
    session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, first_msg[:100]))

    return StreamingResponse(
        _generate_sse_response(session_id, user_message, conversation_history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_sse_response(
    session_id: str,
    user_message: str,
    conversation_history: list,
):
    """Generate SSE stream for the chat endpoint.

    Strategy:
    1. Try to extract all fields from the user message directly.
    2. If all required fields are found, emit __EVENT_EXTRACTED__ immediately
       so the frontend shows the confirmation form (no need for multi-turn chat).
    3. Otherwise, fall back to the conversational flow.
    """
    try:
        from .converters import extract_fields_from_text
        from .conversation import REQUIRED_FIELDS

        # Attempt direct extraction from the latest message
        fields = extract_fields_from_text(user_message)
        has_all_required = all(fields.get(f) for f in REQUIRED_FIELDS)

        # Always populate the session with any extracted fields so subsequent
        # turns (e.g. confirmation) have access to previously collected data.
        session = sessions.get_or_create(session_id)
        for key, value in fields.items():
            if key in session.fields and value:
                session.fields[key] = str(value)

        if has_all_required:
            event_details = _event_details_from_fields(fields)
            marker = (
                f"__EVENT_EXTRACTED__{json.dumps(event_details)}__EVENT_EXTRACTED__"
            )
            yield _create_sse_message(marker)
            yield _create_sse_done()
            return

        # Not enough info — use conversational session to ask for missing fields
        result = _handle_message(session_id, user_message)

        if (
            result.confirmed
            and result.event
            and result.event.get("status") == "success"
        ):
            event_details = {
                "name": result.event.get("event_name", ""),
                "artist": result.event.get("artist"),
                "description": result.fields.get("description"),
                "event_date": result.fields.get("date_time", ""),
                "venue": result.event.get("venue", ""),
                "city": result.event.get("city", ""),
                "price": result.fields.get("price"),
                "ticket_url": result.fields.get("ticket_url"),
            }
            marker = (
                f"__EVENT_EXTRACTED__{json.dumps(event_details)}__EVENT_EXTRACTED__"
            )
            yield _create_sse_message(marker)
        else:
            # Check if session now has all required fields — emit extraction
            session = sessions.get_or_create(session_id)
            if session.all_required_collected():
                event_details = _event_details_from_fields(session.fields)
                marker = (
                    f"__EVENT_EXTRACTED__{json.dumps(event_details)}__EVENT_EXTRACTED__"
                )
                yield _create_sse_message(marker)
            else:
                # Stream the reply word by word
                import re

                tokens = re.findall(r"\S+|\s+", result.reply)
                for token in tokens:
                    yield _create_sse_message(token)
                    if token.strip():
                        await asyncio.sleep(0.01)

        yield _create_sse_done()

    except Exception as e:
        logger.error(f"SSE stream error: {e}", exc_info=True)
        yield _create_sse_message("An unexpected error occurred. Please try again.")
        yield _create_sse_done()


# ============== Legacy JSON Chat ==============


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
def chat(body: ChatRequest, request: Request):
    """Text chat — conversational event submission (JSON response)."""
    session_id = body.session_id or str(uuid.uuid4())
    return _handle_message(session_id, body.message)


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
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(500, f"Transcription failed: {str(e)}")


# ============== Event Extraction ==============


@app.post("/extract-event-from-text")
async def extract_event_from_text(request: ExtractFromTextRequest):
    """Extract event details from plain text."""
    try:
        fields = extract_fields_from_text(request.text)
        if not fields:
            return {
                "success": False,
                "error": "Could not extract event details from text",
            }

        event_details = _event_details_from_fields(fields)
        return {"success": True, "eventDetails": event_details}
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/extract-event-from-url")
async def extract_event_from_url(request: ExtractFromUrlRequest):
    """Extract event details from a URL."""
    try:
        fields = extract_from_url(request.url, language=request.language)
        if not fields:
            return {
                "success": False,
                "error": "Could not extract event details from URL",
            }

        event_details = _event_details_from_fields(fields)
        return {"success": True, "eventData": event_details}
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
        fields = extract_fields_from_text(text)
        if not fields:
            return {
                "success": False,
                "error": "Could not extract event details from image",
            }

        event_details = _event_details_from_fields(fields)
        return {"success": True, "eventDetails": event_details}
    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        return {"success": False, "error": str(e)}


# ============== Event Validation / Push to DB ==============


@app.post("/validate-event")
async def validate_event(request: ValidateEventRequest):
    """Validate and write a confirmed event to the database."""
    try:
        event = request.event
        price_amount = event.price if event.price is not None else 0.0

        # Build the data dict that neo4j_writer.write_event expects
        event_data = {
            "artist": event.artist or event.name,
            "event_name": event.name,
            "date_time": event.event_date,
            "venue": event.venue,
            "city": event.city,
            "price_amount": price_amount,
            "price_currency": _detect_currency(event.city),
            "description": event.description or "",
            "genre": "",
            "ticket_url": event.ticket_url or "",
        }

        result = write_event(event_data)

        if result.get("status") == "success":
            return {
                "success": True,
                "event_id": result["event_id"],
                "event_name": result["event_name"],
                "artist": result["artist"],
                "venue": result["venue"],
                "city": result["city"],
            }
        else:
            raise HTTPException(500, result.get("error", "Failed to write event"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Event validation/write failed: {e}")
        raise HTTPException(500, f"Failed to save event: {str(e)}")


def _detect_currency(city: str) -> str:
    """Simple city→currency detection. Reuses the session logic."""
    from .conversation import CITY_CURRENCY

    return CITY_CURRENCY.get((city or "").lower().strip(), "EUR")
