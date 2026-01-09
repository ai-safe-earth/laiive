from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .clients.neo4j_client import neo4j_client
from .orchestrator import Orchestrator

app = FastAPI(title="laiive retriever API")

schema = neo4j_client.get_schema()
manager = Orchestrator(schema)

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    question: str
    cypher: str
    results: list[dict]

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
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
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "schema": "/schema",
            "chat": "/chat (POST)",
            "query": "/query (POST)",
            "docs": "/docs",
        },
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/schema")
def schema():
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

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
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

        return ChatResponse(
            response=response_text,
            cypher=cypher,
            results=results,
            used_query=used_query,
            needs_more_info=needs_more_info,
        )
    except Exception as e:
        raise HTTPException(500, f"Error generating response: {str(e)}")

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    # Strip whitespace from question
    question = request.question.strip()

    try:
        cypher, results = manager.execute_query(question)
    except Exception as e:
        raise HTTPException(400, f"Query failed: {str(e)}")

    return QueryResponse(
        question=question,
        cypher=cypher,
        results=results,
    )
