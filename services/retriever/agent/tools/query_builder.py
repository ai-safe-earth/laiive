from datetime import date
from typing import Optional, List, Dict, Any
import httpx
from agent.utils.llm_utils import get_openai_client
import numpy as np
import json
from config import settings
from ..clients.neo4j_client import neo4j_client
from .safety_guard import SafetyGuardTool
from ..utils.llm_utils import chat_completion_with_retry, embedding_with_retry
QUERY_BUILDER_PROMPT = """You are a Neo4j Cypher query generator specialized in live music events.

CORE RULES:
1. READ-ONLY: Use only MATCH, OPTIONAL MATCH, WITH, RETURN, WHERE
2. Always wrap datetime conversions: datetime(e.start_at) >= datetime("...")
3. Return 10-20 results max, sorted by relevance
4. Exclude 'embedding' properties from RETURN statements
5. Use exact relationship types from schema

DATE HANDLING:
- Event.start_at format: "2026-01-15T20:00:00Z" (ISO-8601 with Z suffix)
- Always check: WHERE e.start_at IS NOT NULL before datetime conversions
- For date ranges: Use >= start AND <= end patterns
- Correct example:
  WHERE e.start_at IS NOT NULL
    AND datetime(e.start_at) >= datetime("2026-01-15T00:00:00Z")
    AND datetime(e.start_at) <= datetime("2026-01-15T23:59:59Z")

EMBEDDINGS (for semantic ranking):
- Always include these OPTIONAL MATCH patterns:
  OPTIONAL MATCH (artist:Artist)-[:PERFORMS_AT]->(e)
  OPTIONAL MATCH (e)-[:HOSTED_AT]->(venue:Venue)
- Return embeddings separately: event.embedding AS event_embedding, artist.embedding AS artist_embedding, venue.embedding AS venue_embedding
- Do NOT include embedding properties in main entity returns (e.g., "e" should not expose e.embedding)

Current date: {date_context}

Schema:
{schema}"""


class QueryBuilderTool:
    """Generates and executes Cypher queries for live music event search."""

    def __init__(
        self,
        schema: str = "",
        embeddings_model: str = "text-embedding-3-small",
    ):
        self.client = get_openai_client(
            http_client=httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)),
        )
        self.db_schema = schema
        self.embeddings_model = embeddings_model
        self.safety_guard = SafetyGuardTool()

    # Old SYSTEM_PROMPT kept as reference/fallback
    SYSTEM_PROMPT = """You are a Neo4j Cypher query generator. Generate ONLY the Cypher query—no explanations, no markdown.

RULES:
- READ-ONLY queries only (MATCH, OPTIONAL MATCH, WITH, RETURN). Never CREATE/DELETE/MERGE/SET.
- Return complete node properties. Limit to 10-20 results.
- Never include 'embedding' properties in output.
- Use ONLY relationship types from the schema. Never use generic names like "rel" or "relationship".

DATE HANDLING (CRITICAL):
Event.start_at is an ISO-8601 string ending with "Z" (e.g., "2026-01-15T20:00:00Z").

✓ CORRECT pattern:
WHERE e.start_at IS NOT NULL
  AND datetime(e.start_at) >= datetime("2026-01-15T00:00:00Z")
  AND datetime(e.start_at) <= datetime("2026-01-15T23:59:59Z")

✗ WRONG patterns (will fail):
- date(e.start_at) — fails on "Z" suffix
- e.start_at >= "2026-01-15" — string comparison, wrong results
- e.start_at >= datetime(...) — must wrap e.start_at too

Today: {date_context}

Schema:
{schema}
"""

    def run(self, prompt: str, date_info: Optional[Dict[str, str]] = None) -> str:
        question = prompt
        try:
            cypher = self._generate_cypher(question, date_info=date_info)
            safety_result = self.safety_guard.run(cypher)
            safety_data = json.loads(safety_result)

            if not safety_data.get("is_safe", False):
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Query failed safety validation: {safety_data.get('message', 'Unknown violation')}",
                        "cypher": cypher,
                        "violations": safety_data.get("violations", []),
                        "results": [],
                    }
                )

            results = neo4j_client.execute_read(cypher)

            if results:
                query_embedding = self.get_embedding(question)
                results = self._order_by_similarity(results, query_embedding)

            filtered_results = self._filter_embeddings(results)

            return json.dumps(
                {
                    "status": "success",
                    "cypher": cypher,
                    "result_count": len(filtered_results),
                    "results": filtered_results[: settings.max_results_limit],
                    "message": f"Found {len(filtered_results)} event(s)",
                },
                default=str,
            )

        except Exception as e:
            return json.dumps({"status": "error", "error": str(e), "results": []})

    def _generate_cypher(
        self, question: str, date_info: Optional[Dict[str, str]] = None
    ) -> str:
        """Generate Cypher query from natural language question."""
        date_context = (
            f"{date.today().isoformat()} ({date.today().strftime('%A, %B %d, %Y')})"
        )

        # Build date info section if provided
        date_section = ""
        if date_info:
            start = date_info.get("start_date")
            end = date_info.get("end_date")
            date_section = f"""

DATE FILTER TO USE:
datetime(e.start_at) >= datetime("{start}T00:00:00Z") AND datetime(e.start_at) <= datetime("{end}T23:59:59Z")
"""

        embeddings_section = """
EMBEDDINGS: Include related entities with their embeddings:
- OPTIONAL MATCH (artist:Artist)-[:PERFORMS_AT]->(event)
- OPTIONAL MATCH (event)-[:HOSTED_AT]->(venue:Venue)
- OPTIONAL MATCH (venue)-[:LOCATED_IN]->(city:City)
- RETURN event.embedding, artist.embedding, venue.embedding
"""

        system_prompt = (
            QUERY_BUILDER_PROMPT.format(
                schema=self.db_schema, date_context=date_context
            )
            + date_section
            + embeddings_section
        )

        response = chat_completion_with_retry(
            self.client,
            model=settings.query_builder_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,
        )

        cypher = response.choices[0].message.content.strip()

        if cypher.startswith("```"):
            lines = cypher.split("\n")
            cypher = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        return cypher.strip()

    def get_embedding(self, text: str) -> List[float]:
        response = embedding_with_retry(
            self.client, model=self.embeddings_model, input=text
        )
        return response.data[0].embedding

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return 0.0
        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)
        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))

    def _calculate_combined_similarity(
        self,
        query_embedding: List[float],
        event_embedding: Optional[List[float]] = None,
        artist_embeddings: Optional[List[List[float]]] = None,
        venue_embedding: Optional[List[float]] = None,
        weights: Dict[str, float] = None,
    ) -> float:
        if weights is None:
            weights = {"event": 0.3, "artist": 0.5, "venue": 0.2}

        similarities = []
        total_weight = 0.0

        if event_embedding:
            event_sim = self._cosine_similarity(query_embedding, event_embedding)
            similarities.append((event_sim, weights["event"]))
            total_weight += weights["event"]

        if artist_embeddings:
            artist_sims = [
                self._cosine_similarity(query_embedding, artist_emb)
                for artist_emb in artist_embeddings
                if artist_emb is not None
            ]
            if artist_sims:
                avg_artist_sim = sum(artist_sims) / len(artist_sims)
                similarities.append((avg_artist_sim, weights["artist"]))
                total_weight += weights["artist"]

        if venue_embedding:
            venue_sim = self._cosine_similarity(query_embedding, venue_embedding)
            similarities.append((venue_sim, weights["venue"]))
            total_weight += weights["venue"]

        if not similarities or total_weight == 0:
            return 0.0

        weighted_sum = sum(sim * weight for sim, weight in similarities)
        return weighted_sum / total_weight

    def _order_by_similarity(
        self, results: List[dict], query_embedding: List[float]
    ) -> List[dict]:
        scored_results = []

        for result in results:
            event_embedding = result.get("event_embedding") or result.get("embedding")

            artist_embeddings = []
            artist_emb = result.get("artist_embedding")
            if artist_emb:
                if (
                    isinstance(artist_emb, list)
                    and len(artist_emb) > 0
                    and isinstance(artist_emb[0], list)
                ):
                    artist_embeddings = [emb for emb in artist_emb if emb is not None]
                elif isinstance(artist_emb, list) and len(artist_emb) > 0:
                    artist_embeddings = [artist_emb] if artist_emb else []

            venue_embedding = result.get("venue_embedding")

            if event_embedding or artist_embeddings or venue_embedding:
                similarity = self._calculate_combined_similarity(
                    query_embedding=query_embedding,
                    event_embedding=event_embedding,
                    artist_embeddings=artist_embeddings if artist_embeddings else None,
                    venue_embedding=venue_embedding,
                )
            else:
                similarity = 0.0

            result_copy = result.copy()
            result_copy["similarity_score"] = similarity
            scored_results.append((similarity, result_copy))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [result for _, result in scored_results]

    def _filter_embeddings(self, results: list[dict]) -> list[dict]:
        filtered = []
        for result in results:
            cleaned = {}
            for key, value in result.items():
                if key in [
                    "embedding",
                    "event_embedding",
                    "artist_embedding",
                    "venue_embedding",
                ]:
                    continue
                if isinstance(value, dict):
                    cleaned[key] = {
                        k: v
                        for k, v in value.items()
                        if k
                        not in [
                            "embedding",
                            "event_embedding",
                            "artist_embedding",
                            "venue_embedding",
                        ]
                    }
                else:
                    cleaned[key] = value
            filtered.append(cleaned)
        return filtered
