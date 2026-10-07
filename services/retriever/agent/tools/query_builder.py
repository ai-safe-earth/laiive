"""LLM Cypher generation for the long tail the templates can't express.

Generated queries are read-only-validated before execution and asked to
return the executor's standard row shape so results still map to EventCards.
"""

from dataclasses import dataclass, field

from laiive_shared.drafts import strip_fences

from config import settings

from ..classifier import now_in
from ..utils.llm_utils import get_openai_client
from .safety_guard import SafetyGuardTool

QUERY_BUILDER_PROMPT_VERSION = "v3"

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
- DIRECTION IS PART OF THE PATTERN. Every arrow above points the only way it
  exists. `(v:Venue)-[:HOSTED_AT]->(e:Event)` is backwards; it raises no error
  and returns zero rows, which reads as "there is nothing on" to the person
  asking. When in doubt, write the relationship undirected: (e)-[:HOSTED_AT]-(v).

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

- That RETURN aggregates, so `e`, `v` and `c` are out of scope after it: any
  ORDER BY must name a RETURNED ALIAS. Write `ORDER BY start_at`, never
  `ORDER BY e.start_at` — the second is a syntax error Neo4j refuses to run.

Output the Cypher only. No explanation, no markdown fences.

Live schema:
{schema}"""


@dataclass
class GeneratedQuery:
    """What the long-tail leg answers with: rows, or the reason there are none.

    `violations` is only ever filled when the guard refused the query, and the
    eval corpus asserts on it — it is the difference between "the model wrote a
    DELETE" and "Neo4j was down".
    """

    cypher: str = ""
    rows: list[dict] = field(default_factory=list)
    error: str = ""
    violations: list[str] = field(default_factory=list)


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

    def run(self, question: str, timezone: str | None = None) -> GeneratedQuery:
        """Generate a query, validate it, run it. Never raises.

        This used to answer with a JSON *string* that the executor parsed back
        two lines later, and to call a safety-guard method that serialized its
        verdict for this function to parse in turn — two round-trips inside one
        process. Both ends now speak the dataclass below.
        """
        try:
            cypher = self._generate_cypher(question, timezone)
            is_safe, violations = self.safety_guard.validate_read_only(cypher)
            if not is_safe:
                return GeneratedQuery(
                    cypher=cypher,
                    error=(
                        "Query failed safety validation: forbidden operations "
                        f"({', '.join(violations)})"
                    ),
                    violations=violations,
                )

            rows = self.neo4j.execute_read(cypher)
            return GeneratedQuery(
                cypher=cypher, rows=rows[: settings.max_results_limit]
            )
        except Exception as e:
            return GeneratedQuery(error=str(e))

    def _generate_cypher(self, question: str, timezone: str | None = None) -> str:
        # The asker's today, not the server's -- same reason as the classifier.
        today = now_in(timezone).date()
        date_context = f"{today.isoformat()} ({today.strftime('%A, %B %d, %Y')})"

        system_prompt = QUERY_BUILDER_PROMPT.format(
            schema=self.db_schema, date_context=date_context
        )
        response = self.client.chat.completions.create(
            model=settings.query_builder_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,
        )
        return strip_fences(response.choices[0].message.content.strip()).strip()
