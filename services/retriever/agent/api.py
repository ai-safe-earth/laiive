import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from laiive_shared import Done, Error, MessageDelta, sse_frame
from loguru import logger
from pydantic import BaseModel

from config import settings

from .clients.neo4j_client import neo4j_client
from .pipeline import Pipeline, TurnResult
from .utils.formatters import cards_to_markdown, create_sse_done, create_sse_message

LOG_FILE = Path("logs/requests.jsonl")


def log_request(
    user_message: str,
    action: str,
    cypher: str = None,
    results: list = None,
    error: str = None,
):
    """Log request/response for evals."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "action": action,
            "cypher": cypher,
            "result_count": len(results) if results else 0,
            "error": error,
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log request: {e}")


app = FastAPI(title="laiive retriever API", version="0.3.0")

# CORS stays wide open until the gateway terminates browser traffic (Phase 3).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # 'legacy' = OpenAI-shaped data-only frames (current frontend);
    # 'v2' = the named-event shared protocol (new frontend, Phase 4).
    protocol: Literal["legacy", "v2"] = "legacy"


class ChatRequest(BaseModel):
    """JSON request format."""

    message: str
    conversation_history: Optional[List[Message]] = None
    location: Optional[UserLocation] = None


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
        )
        log_request(
            request.message,
            "pipeline",
            result.cyphers[0] if result.cyphers else None,
            [c.model_dump() for c in result.cards],
            "; ".join(result.errors) or None,
        )
        response_text = result.text
        if result.cards:
            response_text += "\n\n" + cards_to_markdown(result.cards)
        return ChatResponse(
            request_id=request_id,
            response=response_text,
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

    generate = _generate_v2 if request.protocol == "v2" else _generate_legacy
    return StreamingResponse(
        generate(request_id, user_message, history, location),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


async def _generate_v2(
    request_id: str,
    user_message: str,
    history: list[dict] | None,
    location: dict | None,
):
    """Named-event frames from the shared protocol."""
    result = TurnResult()
    try:
        for payload in get_pipeline().run_turn(
            user_message, history, location, result=result
        ):
            yield sse_frame(payload)
    except Exception as e:
        logger.error(f"[{request_id}] SSE stream error: {e}", exc_info=True)
        yield sse_frame(Error(code="internal_error", message="Something went wrong."))
    finally:
        log_request(
            user_message,
            "pipeline",
            result.cyphers[0] if result.cyphers else None,
            [c.model_dump() for c in result.cards],
            "; ".join(result.errors) or None,
        )
    yield sse_frame(Done(request_id=request_id))


async def _generate_legacy(
    request_id: str,
    user_message: str,
    history: list[dict] | None,
    location: dict | None,
):
    """OpenAI-shaped data-only frames for the current frontend (delete with Phase 4)."""
    yield f'event: metadata\ndata: {{"request_id": "{request_id}"}}\n\n'
    result = TurnResult()
    try:
        for payload in get_pipeline().run_turn(
            user_message, history, location, result=result
        ):
            if isinstance(payload, MessageDelta):
                yield create_sse_message(payload.text)
            # EventsResult/Status frames have no legacy equivalent mid-stream;
            # cards are appended as markdown below.
        if result.cards:
            yield create_sse_message("\n\n" + cards_to_markdown(result.cards))
    except Exception as e:
        logger.error(f"[{request_id}] SSE stream error: {e}", exc_info=True)
        yield create_sse_message("An unexpected error occurred. Please try again.")
    finally:
        log_request(
            user_message,
            "pipeline",
            result.cyphers[0] if result.cyphers else None,
            [c.model_dump() for c in result.cards],
            "; ".join(result.errors) or None,
        )
    yield create_sse_done()


# ============== Metrics and Observability ==============


@app.get("/metrics")
def get_metrics():
    """Simple metrics endpoint. For detailed observability, use Langfuse."""
    return {
        "status": "operational",
        "langfuse_enabled": settings.langfuse_enabled,
        "note": "Detailed metrics and traces available in Langfuse dashboard",
    }
