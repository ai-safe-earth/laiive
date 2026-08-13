# embeddings.py
import sys
import os

# Allow running as: python -m agent.scripts.embeddings  (from services/retriever/)
# or directly:      python agent/scripts/embeddings.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from neo4j import GraphDatabase
from openai import OpenAI
from config import settings


openai_client = OpenAI(api_key=settings.openai_api_key)
driver = GraphDatabase.driver(
    settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
)
DATABASE = settings.neo4j_database


# ── Embedding call ─────────────────────────────────────────
def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=text, model=settings.embeddings_model
    )
    return response.data[0].embedding


# ── Composite text builders ────────────────────────────────
def build_artist_text(r) -> str:
    parts = [
        r.get("name"),
        r.get("description"),
        ", ".join(r.get("genres") or []),
        r.get("city"),
        r.get("country"),
    ]
    return " | ".join(p for p in parts if p)


def build_event_text(r) -> str:
    parts = [
        r.get("name"),
        r.get("description"),
        ", ".join(r.get("artists") or []),
        r.get("venue"),
        r.get("city"),
        ", ".join(r.get("genres") or []),
    ]
    return " | ".join(p for p in parts if p)


def build_venue_text(r) -> str:
    parts = [
        r.get("name"),
        r.get("description"),
        r.get("city"),
        r.get("country"),
        ", ".join(r.get("genres") or []),
    ]
    return " | ".join(p for p in parts if p)


# ── Embedders ──────────────────────────────────────────────
def embed_artists():
    with driver.session(database=DATABASE) as session:
        records = session.run(
            """
            MATCH (a:Artist)
            OPTIONAL MATCH (a)-[:HAS_GENRE]->(g:Genre)
            OPTIONAL MATCH (a)-[:BASED_IN]->(c:City)-[:PART_OF]->(co:Country)
            RETURN a.ra_id AS id,
                   a.name AS name,
                   a.description AS description,
                   collect(DISTINCT g.name) AS genres,
                   c.name AS city,
                   co.name AS country
        """
        ).data()

        for r in records:
            text = build_artist_text(r)
            embedding = get_embedding(text)
            session.run(
                """
                MATCH (a:Artist {ra_id: $id})
                SET a.embedding = $embedding,
                    a.embedding_text = $text
            """,
                id=r["id"],
                embedding=embedding,
                text=text,
            )
            print(f"  Artist: {r['name']}")


def embed_events():
    with driver.session(database=DATABASE) as session:
        records = session.run(
            """
            MATCH (e:Event)
            OPTIONAL MATCH (a:Artist)-[:PERFORMS_AT]->(e)
            WITH e, collect(DISTINCT a.name) AS artists
            OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)
            OPTIONAL MATCH (e)-[:HAS_GENRE]->(g:Genre)
            RETURN e.ra_id AS id,
                   e.name AS name,
                   e.description AS description,
                   artists,
                   v.name AS venue,
                   c.name AS city,
                   collect(DISTINCT g.name) AS genres
        """
        ).data()

        for r in records:
            text = build_event_text(r)
            embedding = get_embedding(text)
            session.run(
                """
                MATCH (e:Event {ra_id: $id})
                SET e.embedding = $embedding,
                    e.embedding_text = $text
            """,
                id=r["id"],
                embedding=embedding,
                text=text,
            )
            print(f"  Event: {r['name']}")


def embed_venues():
    with driver.session(database=DATABASE) as session:
        records = session.run(
            """
            MATCH (v:Venue)
            OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)-[:PART_OF]->(co:Country)
            OPTIONAL MATCH (e:Event)-[:HOSTED_AT]->(v)
            OPTIONAL MATCH (e)-[:HAS_GENRE]->(g:Genre)
            RETURN v.ra_id AS id,
                   v.name AS name,
                   v.description AS description,
                   c.name AS city,
                   co.name AS country,
                   collect(DISTINCT g.name) AS genres
        """
        ).data()

        for r in records:
            text = build_venue_text(r)
            embedding = get_embedding(text)
            session.run(
                """
                MATCH (v:Venue {ra_id: $id})
                SET v.embedding = $embedding,
                    v.embedding_text = $text
            """,
                id=r["id"],
                embedding=embedding,
                text=text,
            )
            print(f"  Venue: {r['name']}")


# ── Run all ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Embedding artists...")
    embed_artists()
    print("Embedding events...")
    embed_events()
    print("Embedding venues...")
    embed_venues()
    print("\nDone")
    driver.close()
