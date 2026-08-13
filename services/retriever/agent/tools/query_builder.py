from datetime import date
from typing import Optional, Dict
import json
from config import settings
from ..clients.neo4j_client import neo4j_client
from .safety_guard import SafetyGuardTool
from ..utils.llm_utils import get_openai_client, chat_completion_with_retry

QUERY_BUILDER_PROMPT = """You are a Neo4j Cypher query generator specialized in live music events.

CORE RULES:
1. READ-ONLY: Use only MATCH, OPTIONAL MATCH, WITH, RETURN, WHERE
2. Return 10-20 results max, sorted by relevance
3. Use exact relationship types from schema
4. Always collect related entities (artists, genres) using collect(DISTINCT ...)

DATE HANDLING:
- Event.start_at is a native Neo4j DATE_TIME property (not a string).
- Always check: WHERE e.start_at IS NOT NULL before comparisons.
- Compare directly against datetime() literals — do NOT wrap e.start_at in datetime():
  WHERE e.start_at IS NOT NULL
    AND e.start_at >= datetime("2026-01-15T00:00:00Z")
    AND e.start_at <= datetime("2026-01-15T23:59:59Z")
- When the user says a month without a specific day, use the FULL month range:
  e.g. "March" → >= datetime("2026-03-01T00:00:00Z") AND <= datetime("2026-03-31T23:59:59Z")
- When the user says "today", use today's date: {date_context}

FILTERING — MATCH vs OPTIONAL MATCH:
- When the user specifies a city, venue, or artist as a SEARCH FILTER, use MATCH (not OPTIONAL MATCH)
  so that only matching events are returned.
  Example — events in Berlin:
    MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)
    WHERE toLower(c.name) = toLower("Berlin")
  Example — events at a specific venue:
    MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)
    WHERE toLower(v.name) CONTAINS toLower("berghain")
- Use OPTIONAL MATCH only for enriching results with extra data (genres, additional artists).
- NEVER place a WHERE clause for a required filter on an OPTIONAL MATCH — it won't filter results.

STRING MATCHING:
- ALWAYS use case-insensitive matching for names: toLower(x.name) = toLower("value")
- For venue names, prefer CONTAINS over exact match since users often use partial/approximate names:
  WHERE toLower(v.name) CONTAINS toLower("finestre")

RELATIONSHIPS (use exactly these):
- (artist:Artist)-[:PERFORMS_AT]->(event:Event)
- (event:Event)-[:HOSTED_AT]->(venue:Venue)
- (event:Event)-[:HAS_GENRE]->(genre:Genre)
- (artist:Artist)-[:HAS_GENRE]->(genre:Genre)
- (artist:Artist)-[:BASED_IN]->(city:City)
- (venue:Venue)-[:LOCATED_IN]->(city:City)
- (city:City)-[:PART_OF]->(country:Country)

RETURN PATTERNS:
- Use OPTIONAL MATCH + collect() for related entities that enrich results (genres, artists):
  OPTIONAL MATCH (a:Artist)-[:PERFORMS_AT]->(e)
  OPTIONAL MATCH (e)-[:HAS_GENRE]->(g:Genre)
- Return useful fields: event name, start_at, end_at, venue name, city name, artists, genres, ticket_url, price info, status
- When collecting multiple related entities (e.g. artists AND genres), use WITH to separate aggregations and avoid cartesian products.

Current date: {date_context}

Schema:
{schema}"""


class QueryBuilderTool:
    """Generates and executes Cypher queries for live music event search."""

    def __init__(
        self,
        schema: str = "",
    ):
        self.client = get_openai_client()
        self.db_schema = schema
        self.safety_guard = SafetyGuardTool()

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

            return json.dumps(
                {
                    "status": "success",
                    "cypher": cypher,
                    "result_count": len(results),
                    "results": results[: settings.max_results_limit],
                    "message": f"Found {len(results)} event(s)",
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
e.start_at >= datetime("{start}T00:00:00Z") AND e.start_at <= datetime("{end}T23:59:59Z")
"""

        system_prompt = (
            QUERY_BUILDER_PROMPT.format(
                schema=self.db_schema, date_context=date_context
            )
            + date_section
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
