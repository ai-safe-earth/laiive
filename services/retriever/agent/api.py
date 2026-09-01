import threading
import time
import uuid
from typing import List, Literal, Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from laiive_shared import (
    ArtistHit,
    ArtistLookupResult,
    AudioTooLarge,
    Done,
    Error,
    EventsResult,
    UnsupportedAudioFormat,
    VenueHit,
    VenueLookupResult,
    install_internal_auth,
    register_health,
    sse_frame,
    transcribe,
)
from loguru import logger
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from config import settings

from . import eval_records
from .clients.neo4j_client import neo4j_client
from .executor import (
    EVENT_LOOKUP_MAX_UIDS,
    build_artist_search,
    build_uid_query,
    build_venue_search,
    rows_to_cards,
)
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


def _request_id(raw: Request) -> str:
    """The gateway's id, so the record joins conversation_logs; the gateway
    strips client-sent copies, so the header is trustworthy. Minted locally
    only for direct calls (tests, curl against 8002)."""
    return raw.headers.get("x-request-id") or str(uuid.uuid4())


def _write_eval_record(request_id: str, result: TurnResult, start: float) -> None:
    """Fire-and-forget on a daemon thread: in the SSE path the finally: runs
    before the done frame is yielded, so a blocking POST there would delay it.

    ponytail: one unbounded thread per turn, fine at current volume and wrong
    under load - a burst spawns a thread each, and a daemon thread mid-POST
    dies silently on shutdown, losing that record. Upgrade path when turns/sec
    justifies it: a bounded queue plus a single writer thread, dropping oldest
    on overflow so the corpus degrades instead of the turn.
    """
    threading.Thread(
        target=eval_records.write,
        args=(request_id, result, int((time.perf_counter() - start) * 1000)),
        daemon=True,
    ).start()


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
            "events": "/events?uids=… (GET) - cards by uid",
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


# ============== Events by uid ==============


@app.get("/events", response_model=EventsResult)
def events_by_uid(uids: str = Query(..., description="comma-separated event uids")):
    """Fresh cards for a set of uids — the saved list's read path.

    Deliberately off the pipeline: there is no question to classify, no plan
    to route and nothing to compose, so this reaches the driver directly and
    never calls get_pipeline(). That is also what keeps importing this module
    free of an OpenAI client — the pipeline is still built by the first chat
    turn, not by a saved list.

    Unknown uids come back as nothing rather than an error: an event deleted
    from the graph is a stale pointer in somebody's list, not a bad request.
    """
    wanted: list[str] = []
    for raw in uids.split(","):
        uid = raw.strip()
        if uid and uid not in wanted:
            wanted.append(uid)
    if not wanted:
        return EventsResult(events=[])
    if len(wanted) > EVENT_LOOKUP_MAX_UIDS:
        # A truncated saved list is cards vanishing with no message, so the
        # cap is refused rather than silently applied.
        raise HTTPException(400, f"at most {EVENT_LOOKUP_MAX_UIDS} uids per request")

    cypher, params = build_uid_query(wanted)
    try:
        rows = neo4j_client.execute_read(cypher, params)
    except Exception as e:
        logger.error(f"uid lookup failed: {e}")
        raise HTTPException(502, "Could not read the events.") from e

    # Back in the order asked for, so the client's own ordering survives.
    by_uid = {card.uid: card for card in rows_to_cards(rows)}
    return EventsResult(events=[by_uid[uid] for uid in wanted if uid in by_uid])


# ============== Entity lookup (venues, artists) ==============
#
# The first read paths in the product that answer with something other than an
# Event. They exist for a picker: the pro form's venue combobox and the coming
# org screen's claim search, which is why the gateway gates them on the pro
# role. Off the pipeline for the same reason /events is.


@app.get("/venues", response_model=VenueLookupResult)
def venues_lookup(
    q: str = Query(..., description="name fragment, at least 2 characters"),
    city: str = Query("", description="optional city to scope the answer to"),
):
    """Venues by name fragment — a lookup for a picker, not a search."""
    fragment = q.strip()
    if len(fragment) < 2:
        # One character matches half the base; refusing beats a churning list.
        raise HTTPException(400, "q must be at least 2 characters")
    cypher, params = build_venue_search(fragment, city.strip() or None)
    try:
        rows = neo4j_client.execute_read_once(cypher, params)
    except Exception as e:
        logger.error(f"venue lookup failed: {e}")
        raise HTTPException(502, "Could not read the venues.") from e
    return VenueLookupResult(venues=[VenueHit(**row) for row in rows if row.get("uid")])


@app.get("/artists", response_model=ArtistLookupResult)
def artists_lookup(
    q: str = Query(..., description="name fragment, at least 2 characters"),
):
    """Artists by name fragment — same contract as /venues."""
    fragment = q.strip()
    if len(fragment) < 2:
        raise HTTPException(400, "q must be at least 2 characters")
    cypher, params = build_artist_search(fragment)
    try:
        rows = neo4j_client.execute_read_once(cypher, params)
    except Exception as e:
        logger.error(f"artist lookup failed: {e}")
        raise HTTPException(502, "Could not read the artists.") from e
    return ArtistLookupResult(
        artists=[ArtistHit(**row) for row in rows if row.get("uid")]
    )


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
def chat(request: ChatRequest, raw: Request):
    """JSON response endpoint."""
    request_id = _request_id(raw)
    result = TurnResult()
    start = time.perf_counter()
    try:
        get_pipeline().run_turn_collected(
            request.message,
            _history_dicts(request.conversation_history),
            _location_dict(request.location),
            timezone=request.timezone,
            result=result,
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
        logger.opt(exception=True).error("[{}] Chat error: {}", request_id, e)
        raise HTTPException(500, "An internal error occurred. Please try again.")
    finally:
        log_turn(
            request_id,
            request.message,
            cypher=result.cyphers[0] if result.cyphers else None,
            card_count=len(result.cards),
            error="; ".join(result.errors) or None,
        )
        _write_eval_record(request_id, result, start)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequestSSE, raw: Request):
    """SSE streaming endpoint — real streaming from the composer."""
    request_id = _request_id(raw)
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
    start = time.perf_counter()
    try:
        for payload in get_pipeline().run_turn(
            user_message, history, location, result=result, timezone=timezone
        ):
            yield sse_frame(payload)
    except Exception as e:
        logger.opt(exception=True).error("[{}] SSE stream error: {}", request_id, e)
        yield sse_frame(Error(code="internal_error", message="Something went wrong."))
    finally:
        log_turn(
            request_id,
            user_message,
            cypher=result.cyphers[0] if result.cyphers else None,
            card_count=len(result.cards),
            error="; ".join(result.errors) or None,
        )
        _write_eval_record(request_id, result, start)
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
