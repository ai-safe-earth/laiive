# Frontend Integration Guide

This document explains how the retriever API has been adapted to work with the laiive frontend.

## Changes Made

### 1. New SSE Streaming Endpoint

**Endpoint:** `POST /chat/stream`

**Request Format (Frontend Compatible):**
```json
{
  "messages": [
    {"role": "user", "content": "Find jazz concerts in Berlin this weekend"},
    {"role": "assistant", "content": "I found some events..."},
    {"role": "user", "content": "Show me more"}
  ],
  "location": {
    "latitude": 52.5200,
    "longitude": 13.4050,
    "city": "Berlin"
  },
  "language": "en"
}
```

**Response Format (SSE Stream):**
```
data: {"choices":[{"delta":{"content":"I"}}]}

data: {"choices":[{"delta":{"content":" "}}]}

data: {"choices":[{"delta":{"content":"found"}}]}

data: [DONE]
```

### 2. Event Data Formatting

Events from Neo4j are now formatted to match frontend expectations:

**Neo4j Event Structure:**
```json
{
  "event": {
    "id": "123",
    "name": "Jazz Night",
    "description": "Amazing jazz performance",
    "start_at": "2026-01-15T20:00:00Z",
    "price_amount": 25.0,
    "price_currency": "EUR",
    "ticket_url": "https://example.com/tickets"
  },
  "artist": {
    "name": "John Coltrane Quartet"
  },
  "venue": {
    "name": "Blue Note",
    "city": "Berlin",
    "address": "123 Main St"
  }
}
```

**Frontend-Compatible Format:**
```json
{
  "artist": "John Coltrane Quartet",
  "tagline": "Jazz Night",
  "venue": "Blue Note, 123 Main St, Berlin",
  "time": "Wed, Jan 15, 2026 at 8:00 PM",
  "price": "25.00 EUR",
  "description": "Amazing jazz performance",
  "ticketUrl": "https://example.com/tickets"
}
```

### 3. Markdown Event Cards

Events are formatted as markdown that can be displayed in the chat:

```markdown
### 1. Jazz Night

**🎤 Artist:** John Coltrane Quartet

**📍 Venue:** Blue Note, 123 Main St, Berlin

**🗓️ Time:** Wed, Jan 15, 2026 at 8:00 PM

**💰 Price:** 25.00 EUR

**About:** Amazing jazz performance...

🎟️ [Get Tickets](https://example.com/tickets)

---
```

## API Endpoints

### 1. `/chat/stream` (NEW - Recommended for Frontend)

**Purpose:** SSE streaming endpoint compatible with OpenAI-style streaming

**Request:**
- `messages`: Array of conversation messages
- `location`: Optional user location
- `language`: User's language preference

**Response:** Server-Sent Events stream

### 2. `/chat` (Legacy)

**Purpose:** Standard JSON response for backward compatibility

**Request:**
- `message`: Single user message
- `conversation_history`: Optional array of previous messages

**Response:** JSON with response text and optional results

### 3. `/query` (Testing)

**Purpose:** Direct database query for testing

**Request:**
- `message`: Natural language query

**Response:** JSON with Cypher query, results, and formatted markdown

## Required Neo4j Data Structure

For proper formatting, ensure your Cypher queries return:

```cypher
MATCH (e:Event)
OPTIONAL MATCH (e)-[:PERFORMED_BY|HAS_ARTIST]->(a:Artist)
OPTIONAL MATCH (e)-[:AT_VENUE|HOSTED_AT]->(v:Venue)
RETURN
  e as event,
  a as artist,
  v as venue
```

## Formatter Functions

### `format_event_for_frontend(event)`

Converts Neo4j event to frontend-compatible format.

### `format_events_as_markdown(events)`

Converts array of events to markdown string for chat display.

### `format_events_as_json(events)`

Converts array of events to JSON array for structured responses.

## Usage Examples

### Example 1: Basic Query

**User:** "Show me concerts in Berlin this weekend"

**Backend Process:**
1. Orchestrator determines action: `QUERY_DB`
2. Query builder generates Cypher query
3. Safety guard validates query
4. Neo4j returns results
5. Formatter converts to markdown
6. Response streams via SSE

**Frontend Receives:**
```
data: {"choices":[{"delta":{"content":"I found 3 great concerts in Berlin this weekend!\n\n"}}]}
data: {"choices":[{"delta":{"content":"### 1. Jazz Night\n\n"}}]}
data: {"choices":[{"delta":{"content":"**🎤 Artist:** John Coltrane Quartet\n\n"}}]}
...
data: [DONE]
```

### Example 2: Follow-up Question

**Conversation:**
- User: "Find concerts in Berlin"
- Assistant: "I found 5 concerts..."
- User: "Show me only jazz"

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Find concerts in Berlin"},
    {"role": "assistant", "content": "I found 5 concerts..."},
    {"role": "user", "content": "Show me only jazz"}
  ],
  "language": "en"
}
```

Backend uses conversation history to maintain context.

## Migration Steps

### For Frontend Team:

1. **Update API Endpoint:**
   ```javascript
   // Old
   const response = await fetch('/chat', { method: 'POST', body: JSON.stringify({message, conversation_history}) });

   // New
   const response = await fetch('/chat/stream', {
     method: 'POST',
     body: JSON.stringify({messages, location, language})
   });
   ```

2. **Handle SSE Stream:**
   ```javascript
   const reader = response.body.getReader();
   const decoder = new TextDecoder();

   while (true) {
     const {done, value} = await reader.read();
     if (done) break;

     const chunk = decoder.decode(value);
     const lines = chunk.split('\n');

     for (const line of lines) {
       if (line.startsWith('data: ')) {
         const data = line.slice(6);
         if (data === '[DONE]') break;

         const parsed = JSON.parse(data);
         const content = parsed.choices[0].delta.content;
         // Append content to UI
       }
     }
   }
   ```

3. **Parse Event Cards:**
   Events are already formatted as markdown in the response. The frontend can:
   - Display markdown directly (recommended)
   - Parse markdown to extract structured data if needed

## Testing

### Test SSE Endpoint:

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Find jazz concerts in Berlin"}],
    "language": "en"
  }'
```

### Test Legacy Endpoint:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find jazz concerts in Berlin"
  }'
```

## Environment Variables

Ensure these are set:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
EMBEDDINGS_MODEL=text-embedding-3-small
GUARDRAIL_MODEL=meta-llama/llama-guard-3-8b
```

## Notes

- The legacy `/chat` endpoint remains functional for backward compatibility
- Event formatting handles missing fields gracefully (e.g., "Price TBA" if no price)
- Location data from frontend is currently logged but not used in queries (future enhancement)
- Language preference is logged but responses are always in English (future enhancement)
