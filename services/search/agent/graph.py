"""The search service's graph access — owns the clients, delegates writes.

Writes go only through laiive_shared.neo4j_writer (04-plan Phase 5 risk note:
same writer code path, never bespoke Cypher). Reads here are the dry-run dedup
probes and the backfill selects. Tests patch _openai / _driver / _geocoder
(see tests/conftest.py).
"""

from laiive_shared import EventDraft
from laiive_shared.embedding_text import event_text
from laiive_shared.geocode import NominatimGeocoder
from laiive_shared.geocode_store import RedisGeocodeStore
from laiive_shared.neo4j_writer import (
    WriteResult,
    backfill_embeddings,
    parse_start_at,
)
from laiive_shared.neo4j_writer import write_event as _shared_write_event
from laiive_shared.normalize import norm
from neo4j import GraphDatabase
from openai import OpenAI
from pydantic import BaseModel

from config import settings

_openai = OpenAI(api_key=settings.openai_api_key)
_driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password),
    connection_timeout=10,
    # Single replica, sequential per-candidate probes and writes — a small pool
    # keeps a sweep or an approve from crowding the retriever out of Aura.
    max_connection_pool_size=settings.neo4j_max_pool_size,
)
_geocoder = NominatimGeocoder(
    cache_path=settings.geocode_cache_path,
    store=RedisGeocodeStore(settings.redis_url) if settings.redis_url else None,
)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    response = _openai.embeddings.create(model=settings.embedding_model, input=texts)
    return [d.embedding for d in response.data]


def write_event(draft: EventDraft) -> WriteResult:
    with _driver.session(database=settings.neo4j_database) as session:
        return _shared_write_event(
            session,
            draft,
            source="admin_search",
            owner_id=None,
            embed_texts=_embed_texts,
            embedding_model=settings.embedding_model,
            geocoder=_geocoder,
        )


class GraphMatch(BaseModel):
    uid: str
    name: str
    score: float | None = None  # None for an exact identity hit


def probe_duplicate(draft: EventDraft) -> GraphMatch | None:
    """Read-only version of the writer's dedup probe (name+day+venue)."""
    start_at = parse_start_at(draft.start_at or "")
    if start_at is None or not draft.venue:
        return None
    name = draft.name or (
        f"{draft.artists[0]} live at {draft.venue}" if draft.artists else ""
    )
    if not name:
        return None
    with _driver.session(database=settings.neo4j_database) as session:
        record = session.run(
            """
            MATCH (e:Event {name_norm: $name_norm})-[:HOSTED_AT]->(v:Venue {name_norm: $venue_norm})
            WHERE date(e.start_at) = date(datetime($start_at))
            RETURN e.uid AS uid, e.name AS name LIMIT 1
            """,
            name_norm=norm(name),
            venue_norm=norm(draft.venue),
            start_at=start_at.isoformat(),
        ).single()
    if record is None:
        return None
    return GraphMatch(uid=record["uid"], name=record["name"])


def similar_event(draft: EventDraft) -> GraphMatch | None:
    """Nearest existing event by embedding; advisory dedup for the report."""
    text = event_text(
        draft.name or "",
        artists=draft.artists,
        venue=draft.venue,
        city=draft.city,
        genres=[draft.genre] if draft.genre else [],
        start_at=draft.start_at,
        description=draft.description,
    )
    embedding = _embed_texts([text])[0]
    with _driver.session(database=settings.neo4j_database) as session:
        record = session.run(
            """
            CALL db.index.vector.queryNodes('event_embedding', 1, $embedding)
            YIELD node, score
            WHERE score >= $threshold
            RETURN node.uid AS uid, node.name AS name, score
            """,
            embedding=embedding,
            threshold=settings.dedup_similarity,
        ).single()
    if record is None:
        return None
    return GraphMatch(uid=record["uid"], name=record["name"], score=record["score"])


class BackfillResult(BaseModel):
    embedded: int = 0
    venues_geocoded: int = 0
    warnings: list[str] = []


def run_backfill(max_venues: int = 25) -> BackfillResult:
    """Fill missing embeddings and venue locations. Bounded and idempotent.

    Geocoding is Nominatim at 1 req/s (D12), so the venue pass is capped per
    run — the nightly schedule drains any backlog a few venues at a time.
    """
    result = BackfillResult()
    with _driver.session(database=settings.neo4j_database) as session:
        result.embedded = backfill_embeddings(
            session, _embed_texts, settings.embedding_model
        )

        rows = list(
            session.run(
                """
                MATCH (v:Venue)-[:LOCATED_IN]->(c:City)
                WHERE v.location IS NULL
                RETURN v.uid AS uid, v.name AS name, v.address AS address,
                       c.name AS city
                LIMIT $limit
                """,
                limit=max_venues,
            )
        )
        for row in rows:
            query = ", ".join(
                p for p in (row["name"], row["address"], row["city"]) if p
            )
            geo = _geocoder.geocode(query)
            if geo is None:
                result.warnings.append(f"Could not geocode venue {row['name']!r}")
                continue
            session.run(
                """
                MATCH (v:Venue {uid: $uid})
                SET v.location = point({latitude: $lat, longitude: $lng})
                """,
                uid=row["uid"],
                lat=geo.lat,
                lng=geo.lng,
            )
            result.venues_geocoded += 1
    return result


def check_neo4j() -> bool:
    try:
        with _driver.session(database=settings.neo4j_database) as session:
            session.run("RETURN 1").single()
        return True
    except Exception:
        return False
