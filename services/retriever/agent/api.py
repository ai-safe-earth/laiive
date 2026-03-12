from typing import Optional, List, Literal
from datetime import datetime
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
import uuid
import time

# TODO from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
# TODO add slowapi or similar rate limits
from pydantic import BaseModel
import asyncio
from loguru import logger
from config import settings
from .clients.neo4j_client import neo4j_client
from .orchestrator import Orchestrator
from .utils.formatters import (
    format_events_as_markdown,
    create_sse_message,
    create_sse_done,
)
import json
from pathlib import Path


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


app = FastAPI(title="laiive retriever API", version="0.2.0")
schema = neo4j_client.get_schema()
manager = Orchestrator(schema)


# ============== Pydantic Models ==============


class UserLocation(BaseModel):
    latitude: float
    longitude: float
    city: Optional[str] = None


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequestSSE(BaseModel):
    """SSE streaming request format (frontend)."""

    messages: List[Message]
    location: Optional[UserLocation] = None
    language: str = "en"


class ChatRequest(BaseModel):
    """Legacy JSON request format."""

    message: str
    conversation_history: Optional[List[Message]] = None


class ChatResponse(BaseModel):
    request_id: str
    response: str
    cypher: Optional[str] = None
    results: Optional[list[dict]] = None
    used_query: bool = False
    needs_more_info: bool = False


# ============== Logic ==============


def _process_chat(
    user_message: str,
    conversation_history: Optional[List[Message]] = None,
    user_location: Optional[UserLocation] = None,
) -> tuple:
    try:
        location_dict = None
        if user_location:
            location_dict = {
                "latitude": user_location.latitude,
                "longitude": user_location.longitude,
                "city": user_location.city,
            }

        response_text, cypher, results, used_query, needs_more_info = manager.run_react(
            user_message, conversation_history, user_location=location_dict
        )
        log_request(user_message, "react", cypher, results, None)
        return (response_text, cypher, results, used_query, needs_more_info, False)
    except Exception as e:
        logger.error(f"ReAct agent failed: {e}", exc_info=True)
        error = "I had trouble processing your request. Could you try rephrasing?"
        log_request(user_message, "react", None, None, str(e))
        return (error, None, None, False, False, True)


# ============== Health & Info Endpoints ==============


@app.get("/")
def root():
    return {
        "service": "Live Music Events Search Assistant",
        "version": "0.2.0",
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
    checks = {
        "api": "ok",
        "neo4j": "unknown",
        "openai": "unknown",
    }

    try:
        neo4j_client._driver.verify_connectivity()
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = f"error: {str(e)}"

    try:
        import openai

        openai.models.list(limit=1)
        checks["openai"] = "ok"
    except Exception as e:
        checks["openai"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=status_code,
    )


@app.get("/schema")
def get_schema():
    try:
        schema_text = neo4j_client.get_schema(force_refresh=True)
        return {"schema": schema_text, "status": "ok"}
    except Exception as e:
        return {"schema": None, "status": "error", "error": str(e)}


# ============== Chat Endpoints ==============


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """JSON response endpoint."""
    request_id = str(uuid.uuid4())
    try:
        response_text, cypher, results, used_query, needs_more_info, is_error = (
            _process_chat(request.message, request.conversation_history)
        )

        if results and used_query and not is_error:
            events_markdown = format_events_as_markdown(results)
            response_text = f"{response_text}\n\n{events_markdown}"

        return ChatResponse(
            request_id=request_id,
            response=response_text,
            cypher=cypher,
            results=results,
            used_query=used_query,
            needs_more_info=needs_more_info,
        )
    except Exception as e:
        raise HTTPException(500, f"[{request_id}] Error: {str(e)}")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequestSSE):
    """SSE streaming endpoint."""
    request_id = str(uuid.uuid4())
    if not request.messages:
        raise HTTPException(400, "No messages provided")

    user_message = request.messages[-1].content
    conversation_history = request.messages[:-1] if len(request.messages) > 1 else None

    return StreamingResponse(
        _generate_sse_response(user_message, conversation_history, user_location=request.location),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


async def _generate_sse_response(
    user_message: str,
    conversation_history: Optional[List[Message]] = None,
    request_id: str = None,
    user_location: Optional[UserLocation] = None,
):
    """Generate SSE stream."""
    yield f'event: metadata\ndata: {{"request_id": "{request_id}"}}\n\n'
    try:
        response_text, cypher, results, used_query, needs_more_info, is_error = (
            _process_chat(user_message, conversation_history, user_location=user_location)
        )

        # Build full response
        if results and used_query and not is_error:
            events_markdown = format_events_as_markdown(results)
            full_response = f"{response_text}\n\n{events_markdown}"
        else:
            full_response = response_text

        # Stream character by character
        for char in full_response:
            yield create_sse_message(char)
            await asyncio.sleep(settings.sse_stream_delay)

        yield create_sse_done()

    except Exception as e:
        yield create_sse_message(f"An unexpected error occurred: {str(e)}")
        yield create_sse_done()


# ============== Metrics and Observability ==============


@app.get("/metrics")
def get_metrics():
    """Simple metrics endpoint. For detailed observability, use Langfuse."""
    return {
        "status": "operational",
        "langfuse_enabled": settings.langfuse_enabled,
        "note": "Detailed metrics and traces available in Langfuse dashboard"
    }


# TODO when using prometheus and graphana
# EQUEST_COUNT = Counter('retriever_requests_total', 'Total requests', ['action', 'status'])
# REQUEST_LATENCY = Histogram('retriever_request_latency_seconds', 'Request latency')
# TOKEN_USAGE = Counter('retriever_tokens_total', 'Token usage', ['direction'])  # input/output

# @app.get("/metrics")
# def prometheus_metrics():
#    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
