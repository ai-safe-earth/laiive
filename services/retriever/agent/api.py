import uuid
from typing import List, Literal, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from laiive_shared import (
    AudioTooLarge,
    Done,
    Error,
    UnsupportedAudioFormat,
    install_internal_auth,
    register_health,
    sse_frame,
    transcribe,
)
from loguru import logger
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from config import settings

from .clients.neo4j_client import neo4j_client
from .pipeline import Pipeline, TurnResult
from .utils.llm_utils import get_openai_client


def log_turn(
    request_id: str,
    user_message: str,
    cypher: str | None = None,
    card_count: int = 0,
    error: str | None = None,
):
    """One structured line per turn, to stdout.

    This used to append to `logs/requests.jsonl`, which is per-replica ephemeral
    storage and the last thing keeping the container from a read-only root
    filesystem. The eval-ready request record lives gateway-side in Supabase
    `conversation_logs` instead.
    """
    logger.bind(
        request_id=request_id,
        cypher=cypher,
        card_count=card_count,
        error=error,
    ).info("turn: {}", user_message)


app = FastAPI(title="laiive retriever API", version="0.3.0")

# No CORS middleware on purpose: browser traffic terminates at the gateway, and
# the service is only reachable through it (compose `expose`s it, `make start-*`
# binds 127.0.0.1). The SERVICE_CORS_ALLOW_ORIGINS escape hatch existed for the
# Phase 3 frontend that still called 8002/8003 directly; that frontend is gone.

# /livez and /readyz for the kubelet. Neo4j is the only thing this service cannot
# serve without; OpenAI deliberately is not checked — see laiive_shared.health.
register_health(
    app,
    service="retriever",
    ready_check=neo4j_client.verify_connectivity,
)

# Defence in depth behind the NetworkPolicy: the gateway injects the key, the
# probes are exempt, and an unset key is a no-op (local runs, compose, tests).
install_internal_auth(app, expected=settings.internal_api_key)

_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    """Build the pipeline on first use — imports must not require Neo4j."""
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline(neo4j_client)
    return _pipeline


# ============== Pydantic Models ==============


class UserLocation(BaseModel):
    latitude: float
    longitude: float
    city: Optional[str] = None


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequestSSE(BaseModel):
    """SSE streaming request format."""

    messages: List[Message]
    location: Optional[UserLocation] = None
    # The asker's IANA zone, for resolving "today" and "tonight". Optional
    # because a client that sends none is not broken -- it falls back to UTC,
    # which is what every client did before this existed.
    timezone: Optional[str] = None


class ChatRequest(BaseModel):
    """JSON request format."""

    message: str
    conversation_history: Optional[List[Message]] = None
    location: Optional[UserLocation] = None
    timezone: Optional[str] = None


class ChatResponse(BaseModel):
    request_id: str
    response: str
    cypher: Optional[str] = None
    results: Optional[list[dict]] = None
    used_query: bool = False
    needs_more_info: bool = False


def _history_dicts(messages: Optional[List[Message]]) -> list[dict] | None:
    if not messages:
        return None
    return [{"role": m.role, "content": m.content} for m in messages]


def _location_dict(location: Optional[UserLocation]) -> dict | None:
    if location is None:
        return None
    return {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "city": location.city,
    }


# ============== Health & Info Endpoints ==============


@app.get("/")
def root():
    return {
        "service": "Live Music Events Search Assistant",
        "version": "0.3.0",
        "endpoints": {
            "health": "/health",
            "schema": "/schema",
            "chat": "/chat (POST) - JSON response",
            "chat/stream": "/chat/stream (POST) - SSE streaming",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health():
    checks = {"api": "ok", "neo4j": "unknown", "openai": "unknown"}

    try:
        neo4j_client._driver.verify_connectivity()
        checks["neo4j"] = "ok"
    except Exception as e:
        logger.warning(f"Neo4j health check failed: {e}")
        checks["neo4j"] = "error"

    try:
        from .utils.llm_utils import get_openai_client

        get_openai_client().models.list()
        checks["openai"] = "ok"
    except Exception as e:
        logger.warning(f"OpenAI health check failed: {e}")
        checks["openai"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )


@app.get("/schema")
def get_schema():
    try:
        schema_text = neo4j_client.get_schema(force_refresh=True)
        return {"schema": schema_text, "status": "ok"}
    except Exception as e:
        logger.error(f"Schema fetch failed: {e}")
        return {"schema": None, "status": "error", "error": str(e)}


# ============== Voice input ==============


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Speech to text for the chat composer.

    Public on purpose: anonymous users get voice too (D7), so the gateway's
    anonymous per-IP quota is the only thing standing between this and a metered
    Whisper bill — hence the size cap in laiive_shared.speech, checked before
    the API call. The transcript goes back to the client, which sends it as an
    ordinary chat message; there is no separate voice path through the pipeline.
    """
    audio_bytes = await file.read()
    filename = file.filename or "audio.webm"
    try:
        text = await run_in_threadpool(
            transcribe,
            get_openai_client(),
            audio_bytes,
            filename,
            settings.whisper_model,
        )
    except AudioTooLarge as e:
        raise HTTPException(413, str(e)) from e
    except (UnsupportedAudioFormat, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(502, "Transcription failed") from e

    return {"text": text}


# ============== Chat Endpoints ==============


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """JSON response endpoint."""
    request_id = str(uuid.uuid4())
    try:
        result = get_pipeline().run_turn_collected(
            request.message,
            _history_dicts(request.conversation_history),
            _location_dict(request.location),
            timezone=request.timezone,
        )
        log_turn(
            request_id,
            request.message,
            cypher=result.cyphers[0] if result.cyphers else None,
            card_count=len(result.cards),
            error="; ".join(result.errors) or None,
        )
        return ChatResponse(
            request_id=request_id,
            response=result.text,
            cypher=result.cyphers[0] if result.cyphers else None,
            results=[c.model_dump() for c in result.cards] or None,
            used_query=result.used_query,
            needs_more_info=result.needs_more_info,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Chat error: {e}", exc_info=True)
        raise HTTPException(500, "An internal error occurred. Please try again.")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequestSSE):
    """SSE streaming endpoint — real streaming from the composer."""
    request_id = str(uuid.uuid4())
    if not request.messages:
        raise HTTPException(400, "No messages provided")

    user_message = request.messages[-1].content
    history = _history_dicts(request.messages[:-1])
    location = _location_dict(request.location)

    return StreamingResponse(
        _generate(request_id, user_message, history, location, request.timezone),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


def _generate(
    request_id: str,
    user_message: str,
    history: list[dict] | None,
    location: dict | None,
    timezone: str | None = None,
):
    """Named-event frames from the shared protocol.

    Deliberately a *sync* generator: `run_turn` is blocking (OpenAI + Neo4j
    calls), so as an async generator it would hold the event loop between
    yields and the frames only reach the socket once the turn is over — no
    streaming at all. Starlette runs sync iterators in a threadpool, which
    leaves the loop free to flush each frame as it is produced.
    """
    result = TurnResult()
    try:
        for payload in get_pipeline().run_turn(
            user_message, history, location, result=result, timezone=timezone
        ):
            yield sse_frame(payload)
    except Exception as e:
        logger.error(f"[{request_id}] SSE stream error: {e}", exc_info=True)
        yield sse_frame(Error(code="internal_error", message="Something went wrong."))
    finally:
        log_turn(
            request_id,
            user_message,
            cypher=result.cyphers[0] if result.cyphers else None,
            card_count=len(result.cards),
            error="; ".join(result.errors) or None,
        )
    yield sse_frame(Done(request_id=request_id))


# ============== Metrics and Observability ==============


@app.get("/metrics")
def get_metrics():
    """Simple metrics endpoint. For detailed observability, use Langfuse."""
    return {
        "status": "operational",
        "langfuse_enabled": settings.langfuse_enabled,
        "note": "Detailed metrics and traces available in Langfuse dashboard",
    }
