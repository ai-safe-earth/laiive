"""LLM Cypher generation for the long tail the templates can't express.

Generated queries are read-only-validated before execution and asked to
return the executor's standard row shape so results still map to EventCards.
"""

import json

from config import settings

from ..classifier import now_in
from ..utils.llm_utils import chat_completion_with_retry, get_openai_client
from .safety_guard import SafetyGuardTool

QUERY_BUILDER_PROMPT_VERSION = "v2"

QUERY_BUILDER_PROMPT = """You are a Neo4j Cypher query generator specialized in live music events.

CORE RULES:
1. READ-ONLY: Use only MATCH, OPTIONAL MATCH, WITH, WHERE, RETURN, CALL db.index.*
2. Return at most 20 rows, sorted by relevance
3. Use exact relationship types from the schema below

GRAPH MODEL (use exactly these):
- (a:Artist)-[:PERFORMS_AT]->(e:Event)
- (e:Event)-[:HOSTED_AT]->(v:Venue)
- (v:Venue)-[:LOCATED_IN]->(c:City)
- (a:Artist)-[:BASED_IN]->(c:City)
- (e:Event)-[:HAS_GENRE]->(g:Genre)   and   (a:Artist)-[:HAS_GENRE]->(g:Genre)
- Countries are NOT nodes: filter on c.country_code (ISO-3166-1, e.g. 'ES').

IDENTITY & MATCHING:
- Event/Artist/Venue/City all carry name_norm (lowercase, no diacritics).
  ALWAYS match names via name_norm: WHERE a.name_norm CONTAINS 'klangfeld'.
- Genre nodes are keyed by slug (lowercase-hyphenated: 'indie-rock').

DATES:
- Event.start_at is a native DATETIME. Compare directly against datetime()
  literals; never wrap e.start_at in datetime().
- Unless the question asks about the past, always add:
  e.status = 'scheduled' AND e.start_at >= datetime()
- Today is {date_context}.

RETURN SHAPE — end every query with EXACTLY this (add extra aliases after it
only when the question demands them, e.g. a count or a score):
WITH DISTINCT e, v, c
OPTIONAL MATCH (art:Artist)-[:PERFORMS_AT]->(e)
RETURN e.uid AS uid, e.name AS name, e.description AS description,
       toString(e.start_at) AS start_at, e.price_min AS price_min,
       e.price_max AS price_max, e.price_currency AS price_currency,
       e.ticket_url AS ticket_url, e.source AS source,
       v.name AS venue, v.venue_type AS venue_type, c.name AS city,
       v.location.latitude AS lat, v.location.longitude AS lng,
       collect(DISTINCT art.name) AS artists

Output the Cypher only. No explanation, no markdown fences.

Live schema:
{schema}"""


class QueryBuilderTool:
    """Generates and executes read-only Cypher for long-tail questions."""

    def __init__(self, neo4j_client=None, schema: str = "", client=None):
        self.client = client or get_openai_client()
        self.neo4j = neo4j_client
        self._schema = schema
        self.safety_guard = SafetyGuardTool()

    @property
    def db_schema(self) -> str:
        if not self._schema and self.neo4j is not None:
            self._schema = self.neo4j.get_schema()
        return self._schema

    def run(self, question: str, timezone: str | None = None) -> str:
        try:
            cypher = self._generate_cypher(question, timezone)
            safety_data = json.loads(self.safety_guard.run(cypher))
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

            results = self.neo4j.execute_read(cypher)
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

    def _generate_cypher(self, question: str, timezone: str | None = None) -> str:
        # The asker's today, not the server's -- same reason as the classifier.
        today = now_in(timezone).date()
        date_context = f"{today.isoformat()} ({today.strftime('%A, %B %d, %Y')})"

        system_prompt = QUERY_BUILDER_PROMPT.format(
            schema=self.db_schema, date_context=date_context
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
