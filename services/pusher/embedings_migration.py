import os
import time
from typing import List, Dict, Callable
from openai import OpenAI
from neo4j import GraphDatabase
from config import settings

OPENAI_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100

client = OpenAI(api_key=settings.openai_api_key)

def embed(texts: List[str]) -> List[List[float]]:
    # Batch embedding call
    resp = client.embeddings.create(model=OPENAI_MODEL, input=texts)
    # Preserve order
    return [d.embedding for d in resp.data]

def event_to_text(e: Dict) -> str:
    if not isinstance(e, dict):
        return ""

    parts = []
    if name := e.get('name'):
        parts.append(f"Event: {name}")
    if desc := e.get('description'):
        parts.append(f"Description: {desc}")
    if start := e.get('start_at'):
        parts.append(f"Start: {start}")

    price_amount = e.get('price_amount')
    price_currency = e.get('price_currency')
    if price_amount:
        price_str = f"{price_amount} {price_currency or ''}".strip()
        parts.append(f"Price: {price_str}")

    return "\n".join(parts)

def venue_to_text(v: Dict) -> str:
    if not isinstance(v, dict):
        return ""

    parts = []
    if name := v.get('name'):
        parts.append(f"Venue: {name}")
    if desc := v.get('description'):
        parts.append(f"Description: {desc}")
    if address := v.get('address'):
        parts.append(f"Address: {address}")
    if city := v.get('city'):
        parts.append(f"City: {city}")
    if country := v.get('country'):
        parts.append(f"Country: {country}")
    if capacity := v.get('capacity'):
        parts.append(f"Capacity: {capacity}")

    return "\n".join(parts)

def artist_to_text(a: Dict) -> str:
    if not isinstance(a, dict):
        return ""

    parts = []
    if name := a.get('name'):
        parts.append(f"Artist: {name}")
    if desc := a.get('description'):
        parts.append(f"Description: {desc}")
    if summary := a.get('summary'):
        parts.append(f"Summary: {summary}")
    if city := a.get('city'):
        parts.append(f"City: {city}")
    if country := a.get('country'):
        parts.append(f"Country: {country}")
    if genres := a.get('genres'):
        if isinstance(genres, list):
            parts.append(f"Genres: {', '.join(genres)}")
        else:
            parts.append(f"Genres: {genres}")

    return "\n".join(parts)

def migrate_node_type(
    session,
    node_label: str,
    to_text_fn: Callable[[Dict], str],
    fields: List[str],
    entity_name: str
):
    """Generic migration function for any node type"""
    # Count nodes to migrate
    total = session.run(f"""
        MATCH (n:{node_label})
        WHERE n.embedding IS NULL OR size(n.embedding) <> 1536
        RETURN count(n) AS n
    """).single()["n"]

    print(f"{entity_name}s to re-embed: {total}")

    if total == 0:
        print(f"No {entity_name}s need re-embedding.")
        return

    skip = 0
    while True:
        print(f"Fetching {entity_name} batch starting at skip={skip}...")

        # Build RETURN clause dynamically
        return_fields = ", ".join([f"n.{field} AS {field}" for field in fields])

        rows = session.run(f"""
            MATCH (n:{node_label})
            WHERE n.embedding IS NULL OR size(n.embedding) <> 1536
            RETURN n.id AS id, {return_fields}
            ORDER BY n.id
            SKIP $skip LIMIT $limit
        """, skip=skip, limit=BATCH_SIZE).data()

        print(f"Fetched {len(rows)} rows")

        if not rows:
            break

        print(f"Converting {entity_name}s to text...")
        texts = [to_text_fn(r) for r in rows]
        print("Calling OpenAI API for embeddings...")
        vectors = embed(texts)
        print(f"Got {len(vectors)} embeddings")

        # Write back in one query using UNWIND
        payload = [{"id": rows[i]["id"], "embedding": vectors[i]} for i in range(len(rows))]
        print(f"Writing {entity_name} embeddings to Neo4j...")
        session.run(f"""
            UNWIND $payload AS row
            MATCH (n:{node_label} {{id: row.id}})
            SET n.embedding = row.embedding,
                n.embedding_model = $model,
                n.embedding_updated_at = datetime()
        """, payload=payload, model=OPENAI_MODEL)
        print("Write completed")

        skip += len(rows)
        print(f"Updated {skip}/{total} {entity_name}s")

        # gentle pacing (optional)
        time.sleep(0.2)

    print(f"{entity_name} migration completed successfully!")

def migrate_events(uri: str, user: str, password: str, database: str = "neo4j"):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            migrate_node_type(
                session=session,
                node_label="Event",
                to_text_fn=event_to_text,
                fields=["name", "description", "start_at", "price_amount", "price_currency"],
                entity_name="Event"
            )
    finally:
        driver.close()

def migrate_venues(uri: str, user: str, password: str, database: str = "neo4j"):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            migrate_node_type(
                session=session,
                node_label="Venue",
                to_text_fn=venue_to_text,
                fields=["name", "description", "address", "city", "country", "capacity"],
                entity_name="Venue"
            )
    finally:
        driver.close()

def migrate_artists(uri: str, user: str, password: str, database: str = "neo4j"):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            migrate_node_type(
                session=session,
                node_label="Artist",
                to_text_fn=artist_to_text,
                fields=["name", "description", "summary", "city", "country", "genres"],
                entity_name="Artist"
            )
    finally:
        driver.close()

def migrate_all(uri: str, user: str, password: str, database: str = "neo4j"):
    """Migrate all node types in sequence"""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            print("=" * 50)
            print("Starting migration for Events...")
            print("=" * 50)
            migrate_node_type(
                session=session,
                node_label="Event",
                to_text_fn=event_to_text,
                fields=["name", "description", "start_at", "price_amount", "price_currency"],
                entity_name="Event"
            )

            print("\n" + "=" * 50)
            print("Starting migration for Venues...")
            print("=" * 50)
            migrate_node_type(
                session=session,
                node_label="Venue",
                to_text_fn=venue_to_text,
                fields=["name", "description", "address", "city", "country", "capacity"],
                entity_name="Venue"
            )

            print("\n" + "=" * 50)
            print("Starting migration for Artists...")
            print("=" * 50)
            migrate_node_type(
                session=session,
                node_label="Artist",
                to_text_fn=artist_to_text,
                fields=["name", "description", "summary", "city", "country", "genres"],
                entity_name="Artist"
            )

            print("\n" + "=" * 50)
            print("All migrations completed successfully!")
            print("=" * 50)
    finally:
        driver.close()

if __name__ == "__main__":
    migrate_all(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
