"""Write extracted event data to Neo4j with embeddings and relationships."""

import uuid
import re
from datetime import datetime
from neo4j import GraphDatabase
from openai import OpenAI
from loguru import logger
from config import settings

_openai = OpenAI(api_key=settings.openai_api_key)
_driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password),
)


def _embed(text: str) -> list[float]:
    """Generate embedding for a text string."""
    resp = _openai.embeddings.create(model=settings.embedding_model, input=text)
    return resp.data[0].embedding


def _event_text(data: dict) -> str:
    parts = [f"Event: {data.get('event_name', '')}"]
    if data.get("description"):
        parts.append(f"Description: {data['description']}")
    if data.get("date_time"):
        parts.append(f"Date: {data['date_time']}")
    if data.get("price_amount"):
        parts.append(f"Price: {data['price_amount']} {data.get('price_currency', '')}")
    return "\n".join(parts)


def _artist_text(data: dict) -> str:
    parts = [f"Artist: {data['artist']}"]
    if data.get("genre"):
        parts.append(f"Genre: {data['genre']}")
    return "\n".join(parts)


def _venue_text(data: dict) -> str:
    parts = [f"Venue: {data['venue']}"]
    if data.get("city"):
        parts.append(f"City: {data['city']}")
    return "\n".join(parts)


def _parse_date_to_iso(date_str: str) -> str:
    """Parse various date string formats into ISO format for Neo4j datetime()."""
    if not date_str:
        return datetime.now().isoformat()

    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
    ]
    # Strip natural language noise like "alle", "at", "um"
    cleaned = re.sub(r"\b(alle|at|um|à)\b", "", date_str).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            # If year looks like it's in the past, assume current year
            if dt.year < 2025:
                dt = dt.replace(year=datetime.now().year)
            return dt.isoformat()
        except ValueError:
            continue

    logger.warning(f"Could not parse date '{date_str}', using current time")
    return datetime.now().isoformat()


def write_event(data: dict) -> dict:
    """Write a complete event to Neo4j with all nodes and relationships.

    Args:
        data: Dict with keys: artist, event_name, date_time, venue, city,
              price_amount, price_currency, description, genre, ticket_url.

    Returns:
        Dict with status and created node info.
    """
    event_embedding = _embed(_event_text(data))
    artist_embedding = _embed(_artist_text(data))
    venue_embedding = _embed(_venue_text(data))

    event_id = str(uuid.uuid4())
    price = data.get("price_amount", 0.0)
    date_iso = _parse_date_to_iso(data.get("date_time", ""))

    try:
        with _driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                """
                // City
                MERGE (city:City {name: $city})

                // Venue
                MERGE (venue:Venue {name: $venue})
                ON CREATE SET venue.embedding = $venue_embedding,
                              venue.embedding_model = $embedding_model,
                              venue.embedding_updated_at = datetime()
                MERGE (venue)-[:LOCATED_IN]->(city)

                // Artist
                MERGE (artist:Artist {name: $artist})
                ON CREATE SET artist.embedding = $artist_embedding,
                              artist.embedding_model = $embedding_model,
                              artist.embedding_updated_at = datetime()

                // Genre (if provided)
                FOREACH (_ IN CASE WHEN $genre <> '' THEN [1] ELSE [] END |
                    MERGE (g:Genre {slug: $genre})
                    MERGE (artist)-[:HAS_GENRE]->(g)
                )

                // Event
                CREATE (event:Event {
                    ra_id: $event_id,
                    name: $event_name,
                    description: $description,
                    start_at: datetime($date_iso),
                    price_min: $price,
                    price_max: $price,
                    price_currency: $price_currency,
                    ticket_url: $ticket_url,
                    status: 'scheduled',
                    source: 'user_submission',
                    embedding: $event_embedding,
                    embedding_model: $embedding_model,
                    embedding_updated_at: datetime(),
                    created_at: datetime()
                })

                // Relationships
                MERGE (artist)-[:PERFORMS_AT]->(event)
                MERGE (event)-[:HOSTED_AT]->(venue)

                // Genre on event too
                FOREACH (_ IN CASE WHEN $genre <> '' THEN [1] ELSE [] END |
                    MERGE (g2:Genre {slug: $genre})
                    MERGE (event)-[:HAS_GENRE]->(g2)
                )

                RETURN event.ra_id AS event_id, event.name AS event_name,
                       artist.name AS artist, venue.name AS venue, city.name AS city
                """,
                event_id=event_id,
                event_name=data["event_name"],
                description=data.get("description", ""),
                date_iso=date_iso,
                price=price,
                price_currency=data.get("price_currency", "EUR"),
                ticket_url=data.get("ticket_url", ""),
                artist=data["artist"],
                venue=data["venue"],
                city=data["city"],
                genre=data.get("genre", ""),
                event_embedding=event_embedding,
                artist_embedding=artist_embedding,
                venue_embedding=venue_embedding,
                embedding_model=settings.embedding_model,
            )

            record = result.single()
            if record:
                logger.info(
                    f"Event written: {record['event_name']} by {record['artist']} "
                    f"at {record['venue']}, {record['city']}"
                )
                return {
                    "status": "success",
                    "event_id": record["event_id"],
                    "event_name": record["event_name"],
                    "artist": record["artist"],
                    "venue": record["venue"],
                    "city": record["city"],
                }

            return {"status": "error", "error": "No record returned from Neo4j"}

    except Exception as e:
        logger.error(f"Failed to write event: {e}")
        return {"status": "error", "error": str(e)}
