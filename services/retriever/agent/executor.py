"""Executor — hybrid retrieval per sub-query (02-arch §3).

Common shapes run as parameterized Cypher templates (no LLM, no injection
surface); "near me" runs point.distance with progressive radius; fuzzy/vibe
asks run vector kNN over event embeddings; the long tail falls back to
LLM-generated Cypher that still passes the read-only guard.

Every path returns the same standard row shape and is mapped to EventCards
here — the frontend never parses prose.
"""

import json
from dataclasses import dataclass, field

from laiive_shared import EventCard
from laiive_shared.normalize import norm
from loguru import logger

from config import settings

from .classifier import Constraints
from .router import ExecutionPlan, PlanKind

STANDARD_RETURN = """
WITH DISTINCT e, v, c{extra_with}
OPTIONAL MATCH (art:Artist)-[:PERFORMS_AT]->(e)
RETURN e.uid AS uid, e.name AS name, e.description AS description,
       toString(e.start_at) AS start_at, e.price_min AS price_min,
       e.price_max AS price_max, e.price_currency AS price_currency,
       e.ticket_url AS ticket_url, e.source AS source,
       v.name AS venue, v.venue_type AS venue_type, c.name AS city,
       v.location.latitude AS lat, v.location.longitude AS lng,
       collect(DISTINCT art.name) AS artists{extra_return}
"""


def _constraint_clauses(c: Constraints) -> tuple[list[str], dict]:
    """WHERE fragments + params shared by the template, nearby, and vector paths."""
    where: list[str] = []
    params: dict = {}
    if c.city:
        where.append("c.name_norm = $city_norm")
        params["city_norm"] = norm(c.city)
    if c.country_code:
        where.append("c.country_code = $country_code")
        params["country_code"] = c.country_code.upper()
    if c.venue:
        where.append("v.name_norm CONTAINS $venue_norm")
        params["venue_norm"] = norm(c.venue)
    if c.venue_type:
        where.append("v.venue_type = $venue_type")
        params["venue_type"] = c.venue_type
    if c.artist:
        where.append(
            "EXISTS { MATCH (pa:Artist)-[:PERFORMS_AT]->(e) "
            "WHERE pa.name_norm CONTAINS $artist_norm }"
        )
        params["artist_norm"] = norm(c.artist)
    if c.genre:
        where.append(
            "(EXISTS { MATCH (e)-[:HAS_GENRE]->(:Genre {slug: $genre}) } OR "
            "EXISTS { MATCH (:Genre {slug: $genre})<-[:HAS_GENRE]-(:Artist)-[:PERFORMS_AT]->(e) })"
        )
        params["genre"] = c.genre
    if c.date_from:
        where.append("e.start_at >= datetime($date_from)")
        params["date_from"] = c.date_from
    else:
        where.append("e.start_at >= datetime()")  # upcoming only by default
    if c.date_to:
        where.append("e.start_at < datetime($date_to)")
        params["date_to"] = c.date_to
    if c.price_max is not None:
        where.append("e.price_min <= $price_max")
        params["price_max"] = c.price_max
    return where, params


def build_template_query(c: Constraints) -> tuple[str, dict]:
    where, params = _constraint_clauses(c)
    where.insert(0, "e.status = 'scheduled'")
    params["limit"] = settings.max_results_limit
    cypher = (
        "MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)\n"
        "WHERE "
        + "\n  AND ".join(where)
        + "\n"
        + STANDARD_RETURN.format(extra_with="", extra_return="")
        + "ORDER BY start_at LIMIT $limit"
    )
    return cypher, params


def build_nearby_query(
    c: Constraints, lat: float, lng: float, radius_km: float
) -> tuple[str, dict]:
    where, params = _constraint_clauses(c)
    where.insert(0, "e.status = 'scheduled'")
    where.insert(0, "v.location IS NOT NULL")
    where.append(
        "point.distance(v.location, point({latitude: $lat, longitude: $lng})) <= $radius_m"
    )
    params.update(
        lat=lat, lng=lng, radius_m=radius_km * 1000, limit=settings.max_results_limit
    )
    cypher = (
        "MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)\n"
        "WHERE "
        + "\n  AND ".join(where)
        + "\n"
        + STANDARD_RETURN.format(
            extra_with=(
                ",\n     point.distance(v.location, point({latitude: $lat, longitude: $lng})) AS distance_m"
            ),
            extra_return=", distance_m",
        )
        + "ORDER BY distance_m ASC LIMIT $limit"
    )
    return cypher, params


def build_vector_query(c: Constraints) -> tuple[str, dict]:
    where, params = _constraint_clauses(c)
    where.insert(0, "e.status = 'scheduled'")
    params.update(
        k=settings.vector_k,
        threshold=settings.vector_score_threshold,
        limit=settings.max_results_limit,
    )
    cypher = (
        "CALL db.index.vector.queryNodes('event_embedding', $k, $embedding)\n"
        "YIELD node AS e, score\n"
        "WHERE score >= $threshold\n"
        "MATCH (e)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)\n"
        "WHERE " + "\n  AND ".join(where) + "\n"
        "WITH e, v, c, score ORDER BY score DESC LIMIT $limit\n"
        + STANDARD_RETURN.format(extra_with=", score", extra_return="")
    )
    return cypher, params


def rows_to_cards(rows: list[dict]) -> list[EventCard]:
    """Standard-shape rows → EventCards. Distance arrives in meters."""
    cards = []
    for row in rows:
        distance_m = row.get("distance_m")
        cards.append(
            EventCard(
                uid=row.get("uid") or "",
                name=row.get("name") or "",
                artists=[a for a in (row.get("artists") or []) if a],
                venue=row.get("venue"),
                venue_type=row.get("venue_type"),
                city=row.get("city"),
                start_at=row.get("start_at"),
                price_min=row.get("price_min"),
                price_max=row.get("price_max"),
                price_currency=row.get("price_currency"),
                description=row.get("description"),
                ticket_url=row.get("ticket_url"),
                lat=row.get("lat"),
                lng=row.get("lng"),
                source=row.get("source") or "unknown",
                distance_km=round(distance_m / 1000, 2)
                if distance_m is not None
                else None,
            )
        )
    return cards


def _get(row: dict, *keys: str):
    for key in keys:
        if (value := row.get(key)) is not None:
            return value
    return None


def flexible_rows_to_cards(rows: list[dict]) -> list[EventCard]:
    """Best-effort mapping for LLM-generated Cypher rows with arbitrary aliases."""
    cards = []
    for row in rows:
        event = row.get("event") if isinstance(row.get("event"), dict) else row.get("e")
        props = event if isinstance(event, dict) else row
        name = _get(props, "name", "event_name", "e.name")
        if not name:
            continue
        artists = (
            _get(row, "artists", "artist") or _get(props, "artists", "artist") or []
        )
        if isinstance(artists, str):
            artists = [artists]
        venue = _get(row, "venue", "venue_name", "v.name") or _get(props, "venue")
        if isinstance(venue, dict):
            venue = venue.get("name")
        city = _get(row, "city", "city_name", "c.name") or _get(props, "city")
        if isinstance(city, dict):
            city = city.get("name")
        cards.append(
            EventCard(
                uid=str(_get(props, "uid") or ""),
                name=str(name),
                artists=[str(a) for a in artists if a],
                venue=venue,
                city=city,
                venue_type=_get(row, "venue_type") or _get(props, "venue_type"),
                start_at=str(_get(props, "start_at") or "") or None,
                price_min=_get(props, "price_min", "price_amount"),
                price_max=_get(props, "price_max"),
                price_currency=_get(props, "price_currency"),
                description=_get(props, "description"),
                ticket_url=_get(props, "ticket_url", "url"),
                source=str(_get(props, "source") or "unknown"),
            )
        )
    return cards


@dataclass
class Outcome:
    cards: list[EventCard] = field(default_factory=list)
    cypher: str | None = None
    error: str | None = None


class Executor:
    def __init__(self, neo4j_client, embed_fn, query_builder):
        """
        Args:
            neo4j_client: read-access client with execute_read(cypher, params).
            embed_fn: text → embedding vector (for the vector leg).
            query_builder: LLM Cypher generator for the long tail.
        """
        self.neo4j = neo4j_client
        self.embed = embed_fn
        self.query_builder = query_builder

    def execute(self, plan: ExecutionPlan, location: dict | None = None) -> Outcome:
        try:
            if plan.kind == PlanKind.TEMPLATE:
                cypher, params = build_template_query(plan.constraints)
                return Outcome(
                    rows_to_cards(self.neo4j.execute_read(cypher, params)), cypher
                )

            if plan.kind == PlanKind.NEARBY:
                return self._execute_nearby(plan.constraints, location)

            if plan.kind == PlanKind.VECTOR:
                cypher, params = build_vector_query(plan.constraints)
                params["embedding"] = self.embed(
                    plan.constraints.free_text or plan.constraints.query_text or ""
                )
                return Outcome(
                    rows_to_cards(self.neo4j.execute_read(cypher, params)), cypher
                )

            return self._execute_llm_cypher(plan.constraints)
        except Exception as e:
            logger.error(f"Execution failed for {plan.kind}: {e}")
            return Outcome(error=str(e))

    def _execute_nearby(self, c: Constraints, location: dict | None) -> Outcome:
        if not location:
            return Outcome(error="nearby search requested without a location")
        lat, lng = location["latitude"], location["longitude"]
        if c.radius_km:
            radius_steps = [min(c.radius_km, settings.location_max_radius_km)]
        else:
            radius_steps = settings.location_radius_steps
        cypher, rows = "", []
        for radius_km in radius_steps:
            cypher, params = build_nearby_query(c, lat, lng, radius_km)
            rows = self.neo4j.execute_read(cypher, params)
            if len(rows) >= settings.location_min_events:
                break
        return Outcome(rows_to_cards(rows), cypher)

    def _execute_llm_cypher(self, c: Constraints) -> Outcome:
        raw = self.query_builder.run(c.query_text or "")
        data = json.loads(raw)
        if data.get("status") != "success":
            return Outcome(
                error=data.get("error", "query generation failed"),
                cypher=data.get("cypher"),
            )
        return Outcome(
            flexible_rows_to_cards(data.get("results", [])), data.get("cypher")
        )
