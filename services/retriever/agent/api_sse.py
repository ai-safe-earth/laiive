"""
FastAPI application with SSE streaming support for frontend compatibility.
"""
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
from .clients.neo4j_client import neo4j_client
from .orchestrator import Orchestrator
from .formatters import format_events_as_markdown, create_sse_message, create_sse_done

app = FastAPI(title="laiive retriever API")

schema = neo4j_client.get_schema()
manager = Orchestrator(schema)


# Frontend-compatible request models
class UserLocation(BaseModel):
    latitude: float
    longitude: float
    city: Optional[str] = None


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequestSSE(BaseModel):
    """Request format expected by the frontend."""
    messages: List[Message]
    location: Optional[UserLocation] = None
    language: str = "en"


# Legacy models for backward compatibility
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str
    cypher: Optional[str] = None
    results: Optional[list[dict]] = None
    used_query: bool = False
    needs_more_info: bool = False


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "service": "Live Music Events Search Assistant",
        "version": "0.2.0",
        "endpoints": {
            "health": "/health",
            "schema": "/schema",
            "chat": "/chat (POST) - Legacy JSON response",
            "chat/stream": "/chat/stream (POST) - SSE streaming",
            "query": "/query (POST)",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema")
def get_schema():
    try:
        schema_text = neo4j_client.get_schema(force_refresh=True)
        return {
            "schema": schema_text,
            "status": "ok"
        }
    except Exception as e:
        return {
            "schema": f"# Error retrieving schema: {str(e)}\n",
            "status": "error",
            "error": str(e)
        }


async def generate_sse_response(
    user_message: str,
    conversation_history: Optional[List[Message]] = None,
    location: Optional[UserLocation] = None
):
    """
    Generate SSE streaming response compatible with frontend expectations.

    Yields SSE messages in the format:
    data: {"choices":[{"delta":{"content":"chunk"}}]}
    data: [DONE]
    """
    try:
        # Convert frontend Message format to internal ChatMessage format
        internal_history = None
        if conversation_history:
            internal_history = [
                ChatMessage(role=msg.role, content=msg.content)
                for msg in conversation_history
            ]

        # Decide action
        action = manager.decide_action(user_message, internal_history)

        cypher = None
        results = None

        # Execute query if needed
        if action == "QUERY_DB":
            try:
                cypher, results = manager.execute_query(user_message)
            except Exception as e:
                error_msg = f"I encountered an error while searching: {str(e)}. Could you try rephrasing?"
                # Stream error message
                for char in error_msg:
                    yield create_sse_message(char)
                    await asyncio.sleep(0.01)  # Small delay for streaming effect
                yield create_sse_done()
                return

        # Generate response
        response_text, cypher, results, used_query, needs_more_info = manager.generate_response(
            action=action,
            user_message=user_message,
            conversation_history=internal_history,
            cypher=cypher,
            results=results
        )

        # If we have event results, format them as markdown
        if results and used_query:
            events_markdown = format_events_as_markdown(results)
            full_response = f"{response_text}\n\n{events_markdown}"
        else:
            full_response = response_text

        # Stream the response character by character
        for char in full_response:
            yield create_sse_message(char)
            await asyncio.sleep(0.01)  # Small delay for streaming effect

        # Send done signal
        yield create_sse_done()

    except Exception as e:
        error_msg = f"An unexpected error occurred: {str(e)}"
        yield create_sse_message(error_msg)
        yield create_sse_done()


@app.post("/chat/stream")
async def chat_stream(request: ChatRequestSSE):
    """
    SSE streaming endpoint compatible with frontend expectations.

    Accepts the frontend's message format and returns SSE stream.
    """
    if not request.messages:
        raise HTTPException(400, "No messages provided")

    # Get the last user message
    user_message = request.messages[-1].content

    # Get conversation history (all messages except the last one)
    conversation_history = request.messages[:-1] if len(request.messages) > 1 else None

    return StreamingResponse(
        generate_sse_response(user_message, conversation_history, request.location),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Legacy chat endpoint with JSON response.
    Kept for backward compatibility.
    """
    action = manager.decide_action(
        request.message,
        request.conversation_history
    )

    cypher = None
    results = None

    # Execute query if needed
    if action == "QUERY_DB":
        try:
            cypher, results = manager.execute_query(request.message)
        except Exception as e:
            return ChatResponse(
                response=f"I encountered an error while searching: {str(e)}. Could you try rephrasing?",
                cypher=None,
                used_query=True,
            )

    try:
        response_text, cypher, results, used_query, needs_more_info = manager.generate_response(
            action=action,
            user_message=request.message,
            conversation_history=request.conversation_history,
            cypher=cypher,
            results=results
        )

        # Format events if present
        if results and used_query:
            events_markdown = format_events_as_markdown(results)
            response_text = f"{response_text}\n\n{events_markdown}"

        return ChatResponse(
            response=response_text,
            cypher=cypher,
            results=results,
            used_query=used_query,
            needs_more_info=needs_more_info,
        )
    except Exception as e:
        raise HTTPException(500, f"Error generating response: {str(e)}")


@app.post("/query")
def query(request: ChatRequest):
    """
    Direct query endpoint for testing.
    """
    question = request.message.strip()

    try:
        cypher, results = manager.execute_query(question)

        # Format events
        events_markdown = format_events_as_markdown(results) if results else "No results"

        return {
            "question": question,
            "cypher": cypher,
            "results": results,
            "formatted": events_markdown
        }
    except Exception as e:
        raise HTTPException(400, f"Query failed: {str(e)}")
