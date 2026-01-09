from neo4j import GraphDatabase, READ_ACCESS
from neo4j.time import DateTime, Date, Time, Duration
from config import settings


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
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._schema_cache: str | None = None

    def close(self):
        self._driver.close()

    def execute_read(self, cypher: str, params: dict | None = None) -> list[dict]:
        with self._driver.session(
            database=settings.neo4j_database, default_access_mode=READ_ACCESS
        ) as session:
            result = session.run(cypher, params or {})

            return [convert_neo4j_types(record.data()) for record in result]

    def get_schema(self, force_refresh: bool = False) -> str:
        if self._schema_cache is not None and not force_refresh:
            return self._schema_cache

        try:
            with self._driver.session(
                database=settings.neo4j_database, default_access_mode=READ_ACCESS
            ) as session:
                # Try APOC first
                try:
                    result = session.run("""
                        CALL apoc.meta.schema()
                        YIELD value
                        RETURN value
                    """)

                    record = result.single()
                    if record is None:
                        raise ValueError("APOC schema query returned no results")

                    schema_data = record["value"]

                    if not schema_data or not isinstance(schema_data, dict):
                        raise ValueError("APOC schema data is empty or invalid")

                except Exception as apoc_error:
                    # Fallback: manually query schema if APOC fails
                    print(f"APOC not available or failed: {apoc_error}. Using fallback method...")

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
                        sample = session.run(f"""
                            MATCH (n:{label})
                            RETURN n
                            LIMIT 1
                        """).single()

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
                                "properties": properties
                            }

                    # Add relationship types
                    for rel_type in rel_types:
                        schema_data[f"_{rel_type}"] = {"type": "relationship", "name": rel_type}

                formatted_schema = "# Node Labels and Properties\n"

                for node_label, node_data in schema_data.items():
                    if node_data.get("type") == "node":
                        formatted_schema += f"\n## {node_label}\n"
                        formatted_schema += "Properties:\n"

                        for prop, prop_data in node_data.get("properties", {}).items():
                            if prop != "embedding":  # Skip embedding properties
                                formatted_schema += f"- {prop}: {prop_data.get('type', 'unknown')}\n"

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

                if formatted_schema == "# Node Labels and Properties\n\n# Relationship Types\n":
                    formatted_schema = "# No schema data available. Database may be empty or APOC is not installed.\n"

                self._schema_cache = formatted_schema
                return formatted_schema

        except Exception as e:
            error_msg = f"Error retrieving schema: {str(e)}"
            print(error_msg)
            return f"# Error: {error_msg}\n"

    def refresh_schema(self) -> str:
        return self.get_schema(force_refresh=True)

neo4j_client = Neo4jClient()
