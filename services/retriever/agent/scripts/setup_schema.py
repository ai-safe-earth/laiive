from neo4j import GraphDatabase
from config import settings

constraints = [
    # Events — ra_id is the identity
    "CREATE CONSTRAINT event_ra_id IF NOT EXISTS FOR (e:Event) REQUIRE e.ra_id IS UNIQUE",
    "CREATE CONSTRAINT event_name  IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS NOT NULL",
    # Artists
    "CREATE CONSTRAINT artist_ra_id IF NOT EXISTS FOR (a:Artist) REQUIRE a.ra_id IS UNIQUE",
    "CREATE CONSTRAINT artist_name  IF NOT EXISTS FOR (a:Artist) REQUIRE a.name IS NOT NULL",
    # Venues
    "CREATE CONSTRAINT venue_ra_id IF NOT EXISTS FOR (v:Venue) REQUIRE v.ra_id IS UNIQUE",
    "CREATE CONSTRAINT venue_name  IF NOT EXISTS FOR (v:Venue) REQUIRE v.name IS NOT NULL",
    # City + Genre
    "CREATE CONSTRAINT city_name  IF NOT EXISTS FOR (c:City)  REQUIRE c.name IS NOT NULL",
    "CREATE CONSTRAINT genre_slug IF NOT EXISTS FOR (g:Genre) REQUIRE g.slug IS UNIQUE",
]

indexes = [
    "CREATE INDEX event_start_at   IF NOT EXISTS FOR (e:Event)  ON (e.start_at)",
    "CREATE INDEX event_status     IF NOT EXISTS FOR (e:Event)  ON (e.status)",
    "CREATE INDEX artist_spotify   IF NOT EXISTS FOR (a:Artist) ON (a.spotify_id)",
    "CREATE INDEX genre_slug_idx   IF NOT EXISTS FOR (g:Genre)  ON (g.slug)",
    "CREATE INDEX venue_name_idx   IF NOT EXISTS FOR (v:Venue)  ON (v.name)",
    "CREATE INDEX artist_name_idx  IF NOT EXISTS FOR (a:Artist) ON (a.name)",
    "CREATE POINT INDEX venue_location IF NOT EXISTS FOR (v:Venue) ON (v.location)",
]


def setup(uri, user, password, database="neo4j"):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            print("Creating constraints...")
            for q in constraints:
                session.run(q)
                print(f"  ✓ {q[17:50]}...")

            print("\nCreating indexes...")
            for q in indexes:
                session.run(q)
                print(f"  ✓ {q[13:50]}...")

    finally:
        driver.close()

    print("\n✅ Schema ready.")


if __name__ == "__main__":
    setup(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
