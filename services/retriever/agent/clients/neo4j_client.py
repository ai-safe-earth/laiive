from neo4j import GraphDatabase, READ_ACCESS
from neo4j.time import DateTime, Date, Time, Duration
import time
from neo4j.exceptions import ServiceUnavailable, TransientError, SessionExpired
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from config import settings
from loguru import logger

# TODO  7. No structured logging
# Current: Mix of loguru and print statements
# Recommendation: Standardize on structured logging throughout. Configure loguru with JSON formatting for production to enable proper log aggregation and monitoring.

RETRYABLE_NEO4J_ERRORS = (ServiceUnavailable, TransientError, SessionExpired)

neo4j_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RETRYABLE_NEO4J_ERRORS),
    before_sleep=before_sleep_log(logger, log_level="WARNING"),
    reraise=True,
)


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

    def close(self):
        self._driver.close()

    def ensure_schema(self) -> None:
        setup_queries = [
            # uniqueness
            "CREATE CONSTRAINT event_name_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT artist_name_unique IF NOT EXISTS FOR (a:Artist) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT venue_name_unique IF NOT EXISTS FOR (v:Venue) REQUIRE v.name IS UNIQUE",
            "CREATE CONSTRAINT city_name_unique IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT genre_slug_unique IF NOT EXISTS FOR (g:Genre) REQUIRE g.slug IS UNIQUE",
            # indexes
            "CREATE INDEX event_start_at IF NOT EXISTS FOR (e:Event) ON (e.start_at)",
            "CREATE INDEX event_status IF NOT EXISTS FOR (e:Event) ON (e.status)",
        ]
        with self._driver.session(database=settings.neo4j_database) as session:
            for q in setup_queries:
                session.run(q)

    @neo4j_retry
    def execute_read(self, cypher: str, params: dict | None = None) -> list[dict]:
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
                    # Fallback: manually query schema if APOC fails
                    logger.warning(
                        f"APOC not available or failed: {apoc_error}. Using fallback method..."
                    )

                    # Get node labels
                    labels_result = session.run("CALL db.labels()")
                    labels = [record["label"] for record in labels_result]

                    # Get relationship types
                    rels_result = session.run("CALL db.relationshipTypes()")
                    rel_types = [record["relationshipType"] for record in rels_result]

                    # Build schema manually
                    schema_data = {}
                    for label in labels:
                        # Get sample node to infer properties
                        sample = session.run(
                            f"""
                            MATCH (n:{label})
                            RETURN n
                            LIMIT 1
                        """
                        ).single()

                        if sample:
                            node = sample["n"]
                            properties = {}
                            for key in node.keys():
                                if key != "embedding":  # Skip embedding
                                    value = node[key]
                                    prop_type = type(value).__name__
                                    properties[key] = {"type": prop_type}

                            schema_data[label] = {
                                "type": "node",
                                "properties": properties,
                            }

                    # Add relationship types
                    for rel_type in rel_types:
                        schema_data[f"_{rel_type}"] = {
                            "type": "relationship",
                            "name": rel_type,
                        }

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

    def refresh_schema(self) -> str:
        return self.get_schema(force_refresh=True)


logger.debug("Creating global neo4j_client instance...")
try:
    neo4j_client = Neo4jClient()
    logger.debug("Global neo4j_client created")
except Exception as e:
    logger.error(f"Failed to create global neo4j_client: {e}")
    raise
