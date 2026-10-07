from neo4j import GraphDatabase, READ_ACCESS
from neo4j.time import DateTime, Date, Time, Duration
import time
from config import settings
from loguru import logger

# TODO  7. No structured logging
# Current: Mix of loguru and print statements
# Recommendation: Standardize on structured logging throughout. Configure loguru with JSON formatting for production to enable proper log aggregation and monitoring.


def convert_neo4j_types(value):
    if isinstance(value, DateTime):
        return value.isoformat()
    elif isinstance(value, Date):
        return value.isoformat()
    elif isinstance(value, Time):
        return value.isoformat()
    elif isinstance(value, Duration):
        return str(value)
    elif isinstance(value, dict):
        return {k: convert_neo4j_types(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [convert_neo4j_types(v) for v in value]
    return value


class Neo4jClient:
    def __init__(self):
        logger.info("Initializing Neo4j client...")
        logger.debug(f"Connecting to: {settings.neo4j_uri}")
        logger.debug(f"Database: {settings.neo4j_database}")
        logger.debug(f"User: {settings.neo4j_user}")

        try:
            logger.info("Creating Neo4j driver...")
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                connection_timeout=10,
                # Per *process*, and the retriever is the one service that runs
                # several replicas — the cap is a share of Aura's connection
                # budget, not this pod's appetite. A turn holds a session for one
                # read out of ~15 s dominated by OpenAI, so hold time is a small
                # fraction of the 40 threadpool slots. Env-tunable because Aura
                # Free's real ceiling is undocumented: lower it if load testing
                # produces ServiceUnavailable or acquisition timeouts.
                max_connection_pool_size=settings.neo4j_max_pool_size,
                connection_acquisition_timeout=60,
            )
            logger.debug("Neo4j driver created")
            self._schema_cache: str | None = None
        except Exception as e:
            logger.error(f"Failed to create Neo4j driver: {e}")
            logger.error("Check if Neo4j is running and NEO4J_URI is correct")
            raise

    def verify_connectivity(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Neo4j connectivity check failed: {e}")
            return False

    def execute_read_once(self, cypher: str, params: dict | None = None) -> list[dict]:
        """One attempt, no retry ladder — for typeahead lookups, where the next
        keystroke IS the retry and three backoff attempts would pin a
        threadpool slot answering a fragment nobody wants any more."""
        start = time.perf_counter()
        try:
            with self._driver.session(
                database=settings.neo4j_database, default_access_mode=READ_ACCESS
            ) as session:
                result = session.run(cypher, params or {}, timeout=8.0)
                return [convert_neo4j_types(r.data()) for r in result]
        finally:
            logger.debug(
                f"Neo4j read took {int((time.perf_counter() - start) * 1000)}ms"
            )

    def execute_read(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Chat reads, through a managed transaction.

        This used to be `execute_read_once` wrapped in a tenacity ladder that
        retried ServiceUnavailable, TransientError and SessionExpired with
        exponential backoff. The driver's own managed transaction retries that
        same set, which is the whole reason it exists, so the ladder was a
        second one nested inside the first — and the driver's knows about
        routing table refreshes and leader switches, which tenacity does not.
        A waking Aura is the case that matters here.
        """
        start = time.perf_counter()
        try:
            with self._driver.session(
                database=settings.neo4j_database, default_access_mode=READ_ACCESS
            ) as session:
                return session.execute_read(
                    lambda tx: [
                        convert_neo4j_types(r.data())
                        for r in tx.run(cypher, params or {}, timeout=8.0)
                    ]
                )
        finally:
            logger.debug(
                f"Neo4j read took {int((time.perf_counter() - start) * 1000)}ms"
            )

    def get_schema(self, force_refresh: bool = False) -> str:
        if self._schema_cache is not None and not force_refresh:
            return self._schema_cache

        try:
            with self._driver.session(
                database=settings.neo4j_database, default_access_mode=READ_ACCESS
            ) as session:
                # Try APOC first
                try:
                    result = session.run(
                        """
                        CALL apoc.meta.schema()
                        YIELD value
                        RETURN value
                    """
                    )

                    record = result.single()
                    if record is None:
                        raise ValueError("APOC schema query returned no results")

                    schema_data = record["value"]

                    if not schema_data or not isinstance(schema_data, dict):
                        raise ValueError("APOC schema data is empty or invalid")

                except Exception as apoc_error:
                    # A fallback used to live here: it re-derived the schema
                    # from db.labels(), db.relationshipTypes() and one sample
                    # node per label, then hand-formatted the result — sixty
                    # lines inferring what QUERY_BUILDER_PROMPT, the only
                    # consumer of this string, already spells out in full
                    # (every node, every property, every relationship
                    # direction). Aura has APOC; if this ever fires the prompt
                    # still carries the model.
                    logger.warning(f"APOC schema unavailable: {apoc_error}")
                    return "# Schema unavailable; the prompt carries the graph model.\n"

                formatted_schema = "# Node Labels and Properties\n"

                for node_label, node_data in schema_data.items():
                    if node_data.get("type") == "node":
                        formatted_schema += f"\n## {node_label}\n"
                        formatted_schema += "Properties:\n"

                        for prop, prop_data in node_data.get("properties", {}).items():
                            if prop != "embedding":  # Skip embedding properties
                                formatted_schema += (
                                    f"- {prop}: {prop_data.get('type', 'unknown')}\n"
                                )

                formatted_schema += "\n# Relationship Types\n"
                rels = set()

                for node_data in schema_data.values():
                    if node_data.get("type") == "node":
                        for rel in node_data.get("relationships", {}).values():
                            rel_type = rel.get("type")
                            if rel_type:
                                rels.add(rel_type)

                # Also add relationship types from manual query
                for node_data in schema_data.values():
                    if node_data.get("type") == "relationship":
                        rel_name = node_data.get("name")
                        if rel_name:
                            rels.add(rel_name)

                for rel in sorted(rels):
                    if rel:  # Skip empty strings
                        formatted_schema += f"- {rel}\n"

                if (
                    formatted_schema
                    == "# Node Labels and Properties\n\n# Relationship Types\n"
                ):
                    formatted_schema = "# No schema data available. Database may be empty or APOC is not installed.\n"

                self._schema_cache = formatted_schema
                return formatted_schema

        except Exception as e:
            error_msg = f"Error retrieving schema: {str(e)}"
            logger.error(error_msg)
            return f"# Error: {error_msg}\n"


logger.debug("Creating global neo4j_client instance...")
try:
    neo4j_client = Neo4jClient()
    logger.debug("Global neo4j_client created")
except Exception as e:
    logger.error(f"Failed to create global neo4j_client: {e}")
    raise
