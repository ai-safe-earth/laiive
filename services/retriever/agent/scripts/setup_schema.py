"""Create the laiive graph schema (docs/refactor/03-ontology.md).

Idempotent: every statement uses IF NOT EXISTS. Applied to Aura 2099d44c
on 2026-08-13; keep this file as the single source of truth for the DDL.

Run: cd services/retriever && uv run python -m agent.scripts.setup_schema
"""

from neo4j import GraphDatabase

from config import settings

EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small
EMBEDDING_SIMILARITY = "cosine"

constraints = [
    # uid is the stable external identity on every entity node
    "CREATE CONSTRAINT event_uid  IF NOT EXISTS FOR (e:Event)  REQUIRE e.uid IS UNIQUE",
    "CREATE CONSTRAINT artist_uid IF NOT EXISTS FOR (a:Artist) REQUIRE a.uid IS UNIQUE",
    "CREATE CONSTRAINT venue_uid  IF NOT EXISTS FOR (v:Venue)  REQUIRE v.uid IS UNIQUE",
    "CREATE CONSTRAINT genre_slug IF NOT EXISTS FOR (g:Genre)  REQUIRE g.slug IS UNIQUE",
    # names must exist
    "CREATE CONSTRAINT event_name_nn  IF NOT EXISTS FOR (e:Event)  REQUIRE e.name IS NOT NULL",
    "CREATE CONSTRAINT artist_name_nn IF NOT EXISTS FOR (a:Artist) REQUIRE a.name IS NOT NULL",
    "CREATE CONSTRAINT venue_name_nn  IF NOT EXISTS FOR (v:Venue)  REQUIRE v.name IS NOT NULL",
    # cities are identified by normalized name + country
    "CREATE CONSTRAINT city_key IF NOT EXISTS FOR (c:City) "
    "REQUIRE (c.name_norm, c.country_code) IS NODE KEY",
]

indexes = [
    "CREATE INDEX event_start_at   IF NOT EXISTS FOR (e:Event)  ON (e.start_at)",
    # The admin dashboard's events-per-day trend groups by this.
    "CREATE INDEX event_created_at IF NOT EXISTS FOR (e:Event)  ON (e.created_at)",
    "CREATE INDEX event_status     IF NOT EXISTS FOR (e:Event)  ON (e.status)",
    "CREATE INDEX event_source     IF NOT EXISTS FOR (e:Event)  ON (e.source)",
    "CREATE INDEX event_name_norm  IF NOT EXISTS FOR (e:Event)  ON (e.name_norm)",
    "CREATE INDEX artist_name_norm IF NOT EXISTS FOR (a:Artist) ON (a.name_norm)",
    "CREATE INDEX venue_name_norm  IF NOT EXISTS FOR (v:Venue)  ON (v.name_norm)",
    "CREATE INDEX venue_type       IF NOT EXISTS FOR (v:Venue)  ON (v.venue_type)",
    "CREATE INDEX city_country     IF NOT EXISTS FOR (c:City)   ON (c.country_code)",
    "CREATE POINT INDEX venue_location IF NOT EXISTS FOR (v:Venue) ON (v.location)",
    "CREATE POINT INDEX city_location  IF NOT EXISTS FOR (c:City)  ON (c.location)",
]

vector_indexes = [
    f"CREATE VECTOR INDEX {name} IF NOT EXISTS FOR (n:{label}) ON (n.embedding) "
    "OPTIONS {indexConfig: {`vector.dimensions`: "
    f"{EMBEDDING_DIMENSIONS}, `vector.similarity_function`: '{EMBEDDING_SIMILARITY}'}}}}"
    for name, label in [
        ("event_embedding", "Event"),
        ("artist_embedding", "Artist"),
        ("venue_embedding", "Venue"),
    ]
]


def setup(uri, user, password, database="neo4j"):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            print("Creating constraints...")
            for q in constraints:
                session.run(q)
                print(f"  ok {q[18:60]}")

            print("\nCreating indexes...")
            for q in indexes:
                session.run(q)
                print(f"  ok {q[13:60]}")

            print("\nCreating vector indexes...")
            for q in vector_indexes:
                session.run(q)
                print(f"  ok {q[20:60]}")
    finally:
        driver.close()

    print("\nSchema ready.")


if __name__ == "__main__":
    setup(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
