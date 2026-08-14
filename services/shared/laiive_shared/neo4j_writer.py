"""MERGE-by-identity graph write path (03-ontology §3, 04-plan Phase 2).

The only code allowed to write domain nodes. Identity keys:
Event (name_norm, start_at) · Artist name_norm · Venue name_norm within its
city · City (name_norm, country_code) · Genre slug. Every node gets `source`
provenance and, for pro submissions, the submitting user's `owner_id`.

Clients (services) inject their own OpenAI embedding call and geocoder so this
module owns no API clients — that keeps test patching in one place per service.
"""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .cards import EventDraft, missing_required
from .embedding_text import artist_text, event_text, venue_text
from .geocode import NominatimGeocoder
from .normalize import genre_slug, norm

logger = logging.getLogger(__name__)

EmbedFn = Callable[[list[str]], list[list[float]]]

_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M",
]


class WriteResult(BaseModel):
    status: Literal["created", "duplicate", "invalid", "error"]
    uid: str | None = None
    name: str | None = None
    venue: str | None = None
    city: str | None = None
    missing: list[str] = []
    warnings: list[str] = []
    message: str = ""


def parse_start_at(raw: str) -> datetime | None:
    """Parse the draft's start_at into a datetime; None when unparseable."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass
    cleaned = " ".join(raw.replace(" at ", " ").split())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def write_event(
    session,
    draft: EventDraft,
    *,
    source: str,
    owner_id: str | None = None,
    embed_texts: EmbedFn | None = None,
    embedding_model: str = "",
    geocoder: NominatimGeocoder | None = None,
) -> WriteResult:
    """Write one event (plus its artists/venue/city/genre) to the graph.

    Args:
        session: neo4j write session bound to the target database.
        draft: the confirmed event draft; required fields must be present.
        source: 'pro_submission' | 'admin_search' | 'seed'.
        owner_id: Supabase user id for pro submissions.
        embed_texts: batch embedding call; embeddings are skipped when None.
        embedding_model: recorded on nodes alongside the vectors.
        geocoder: venue/city geocoding; skipped (with a warning) when None.
    """
    missing = missing_required(draft, source)
    if missing:
        return WriteResult(
            status="invalid",
            missing=missing,
            message=f"Draft is missing required fields: {', '.join(missing)}",
        )

    start_at = parse_start_at(draft.start_at or "")
    if start_at is None:
        return WriteResult(
            status="invalid",
            missing=["start_at"],
            message=f"Could not parse start_at: {draft.start_at!r}",
        )

    name = draft.name or f"{draft.artists[0]} live at {draft.venue}"
    warnings: list[str] = []

    # ── Dedup probe: same name + calendar day + venue → refuse to duplicate ──
    existing = session.run(
        """
        MATCH (e:Event {name_norm: $name_norm})-[:HOSTED_AT]->(v:Venue {name_norm: $venue_norm})
        WHERE date(e.start_at) = date(datetime($start_at))
        RETURN e.uid AS uid, e.name AS name LIMIT 1
        """,
        name_norm=norm(name),
        venue_norm=norm(draft.venue),
        start_at=start_at.isoformat(),
    ).single()
    if existing:
        return WriteResult(
            status="duplicate",
            uid=existing["uid"],
            name=existing["name"],
            venue=draft.venue,
            city=draft.city,
            message="An event with the same name, date, and venue already exists.",
        )

    # ── Geocode venue and city (D12) ─────────────────────────────────────────
    venue_geo = city_geo = None
    if geocoder is not None:
        venue_query = ", ".join(
            p for p in (draft.venue, draft.address, draft.city) if p
        )
        venue_geo = geocoder.geocode(venue_query)
        city_geo = geocoder.geocode(draft.city)
        if venue_geo is None and city_geo is not None:
            venue_geo = city_geo  # fall back to the city centroid
            warnings.append("Venue could not be geocoded; using city centroid.")
    if venue_geo is None:
        warnings.append(
            "No venue location — this event will not appear in nearby search."
        )
    country_code = (city_geo.country_code if city_geo else "") or (
        venue_geo.country_code if venue_geo else ""
    )
    if not country_code:
        warnings.append("Could not resolve the city's country code.")

    event_uid = str(uuid.uuid4())
    genre = genre_slug(draft.genre) if draft.genre else ""
    try:
        record = session.run(
            """
            MERGE (c:City {name_norm: $city_norm, country_code: $country_code})
            ON CREATE SET c.name = $city,
                          c.location = CASE WHEN $city_lat IS NULL THEN NULL
                              ELSE point({latitude: $city_lat, longitude: $city_lng}) END

            MERGE (v:Venue {name_norm: $venue_norm})-[:LOCATED_IN]->(c)
            ON CREATE SET v.uid = $venue_uid, v.name = $venue,
                          v.venue_type = $venue_type, v.address = $address,
                          v.location = CASE WHEN $venue_lat IS NULL THEN NULL
                              ELSE point({latitude: $venue_lat, longitude: $venue_lng}) END,
                          v.source = $source, v.owner_id = $owner_id,
                          v.created_at = datetime()

            CREATE (e:Event {
                uid: $event_uid, name: $name, name_norm: $name_norm,
                description: $description, start_at: datetime($start_at),
                price_min: $price_min, price_max: $price_max,
                price_currency: $price_currency, ticket_url: $ticket_url,
                status: 'scheduled', source: $source, owner_id: $owner_id,
                created_at: datetime(), updated_at: datetime()
            })
            MERGE (e)-[:HOSTED_AT]->(v)

            FOREACH (_ IN CASE WHEN $genre <> '' THEN [1] ELSE [] END |
                MERGE (g:Genre {slug: $genre})
                ON CREATE SET g.name = $genre_name
                MERGE (e)-[:HAS_GENRE]->(g)
            )

            WITH e, v, c
            UNWIND $artists AS artist
            MERGE (a:Artist {name_norm: artist.name_norm})
            ON CREATE SET a.uid = artist.uid, a.name = artist.name,
                          a.source = $source, a.owner_id = $owner_id,
                          a.created_at = datetime()
            MERGE (a)-[:PERFORMS_AT]->(e)
            FOREACH (_ IN CASE WHEN $genre <> '' THEN [1] ELSE [] END |
                MERGE (g:Genre {slug: $genre})
                MERGE (a)-[:HAS_GENRE]->(g)
            )

            RETURN e.uid AS uid, e.name AS name, v.name AS venue, c.name AS city
            """,
            city=draft.city,
            city_norm=norm(draft.city),
            country_code=country_code,
            city_lat=city_geo.lat if city_geo else None,
            city_lng=city_geo.lng if city_geo else None,
            venue=draft.venue,
            venue_norm=norm(draft.venue),
            venue_uid=str(uuid.uuid4()),
            venue_type=draft.venue_type,
            address=draft.address,
            venue_lat=venue_geo.lat if venue_geo else None,
            venue_lng=venue_geo.lng if venue_geo else None,
            event_uid=event_uid,
            name=name,
            name_norm=norm(name),
            description=draft.description or "",
            start_at=start_at.isoformat(),
            price_min=draft.price_min,
            price_max=draft.price_max
            if draft.price_max is not None
            else draft.price_min,
            price_currency=draft.price_currency or "EUR",
            ticket_url=draft.ticket_url or "",
            genre=genre,
            genre_name=(draft.genre or "").strip().title(),
            artists=[
                {"name": a, "name_norm": norm(a), "uid": str(uuid.uuid4())}
                for a in draft.artists
            ],
            source=source,
            owner_id=owner_id,
        ).single()
    except Exception as e:  # neo4j errors surface as a typed result, not a 500
        logger.error("Event write failed: %s", e)
        return WriteResult(status="error", message=str(e))

    if record is None:
        return WriteResult(status="error", message="No record returned from Neo4j")

    if embed_texts is not None:
        try:
            backfill_embeddings(session, embed_texts, embedding_model)
        except Exception as e:
            logger.error("Embedding backfill failed: %s", e)
            warnings.append(f"Embeddings not written: {e}")

    return WriteResult(
        status="created",
        uid=record["uid"],
        name=record["name"],
        venue=record["venue"],
        city=record["city"],
        warnings=warnings,
        message="Event created.",
    )


def backfill_embeddings(session, embed_texts: EmbedFn, embedding_model: str) -> int:
    """Embed every Event/Artist/Venue node that has no embedding yet.

    Builds the composite texts with the shared recipes, embeds them in one
    batch call per label, and stores vector + text + model. Returns the number
    of nodes embedded.
    """
    jobs: list[tuple[str, str, str]] = []  # (label, uid, text)

    for row in session.run(
        """
        MATCH (e:Event) WHERE e.embedding IS NULL
        OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
        OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)
        OPTIONAL MATCH (a:Artist)-[:PERFORMS_AT]->(e)
        OPTIONAL MATCH (e)-[:HAS_GENRE]->(g:Genre)
        RETURN e.uid AS uid, e.name AS name, e.description AS description,
               toString(e.start_at) AS start_at, v.name AS venue, c.name AS city,
               collect(DISTINCT a.name) AS artists, collect(DISTINCT g.name) AS genres
        """
    ):
        jobs.append(
            (
                "Event",
                row["uid"],
                event_text(
                    row["name"],
                    artists=row["artists"],
                    venue=row["venue"],
                    city=row["city"],
                    genres=[g for g in row["genres"] if g],
                    start_at=row["start_at"],
                    description=row["description"],
                ),
            )
        )

    for row in session.run(
        """
        MATCH (a:Artist) WHERE a.embedding IS NULL
        OPTIONAL MATCH (a)-[:BASED_IN]->(c:City)
        OPTIONAL MATCH (a)-[:HAS_GENRE]->(g:Genre)
        RETURN a.uid AS uid, a.name AS name, a.description AS description,
               c.name AS city, collect(DISTINCT g.name) AS genres
        """
    ):
        jobs.append(
            (
                "Artist",
                row["uid"],
                artist_text(
                    row["name"],
                    genres=[g for g in row["genres"] if g],
                    city=row["city"],
                    description=row["description"],
                ),
            )
        )

    for row in session.run(
        """
        MATCH (v:Venue) WHERE v.embedding IS NULL
        OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)
        RETURN v.uid AS uid, v.name AS name, v.venue_type AS venue_type,
               v.address AS address, c.name AS city, v.description AS description
        """
    ):
        jobs.append(
            (
                "Venue",
                row["uid"],
                venue_text(
                    row["name"],
                    venue_type=row["venue_type"],
                    city=row["city"],
                    address=row["address"],
                    description=row["description"],
                ),
            )
        )

    if not jobs:
        return 0

    vectors = embed_texts([text for _, _, text in jobs])
    for (label, uid, text), vector in zip(jobs, vectors):
        session.run(
            f"""
            MATCH (n:{label} {{uid: $uid}})
            SET n.embedding = $vector, n.embedding_text = $text,
                n.embedding_model = $model, n.embedding_updated_at = datetime()
            """,
            uid=uid,
            vector=vector,
            text=text,
            model=embedding_model,
        )
    return len(jobs)
