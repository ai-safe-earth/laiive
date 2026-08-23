"""Executor — hybrid retrieval per sub-query (02-arch §3).

Common shapes run as parameterized Cypher templates (no LLM, no injection
surface); "near me" runs point.distance with progressive radius; fuzzy/vibe
asks run vector kNN over event embeddings; the long tail falls back to
LLM-generated Cypher that still passes the read-only guard.

Every path returns the same standard row shape and is mapped to EventCards
here — the frontend never parses prose.
"""

import json
import math
from dataclasses import dataclass, field

from laiive_shared import EventCard
from laiive_shared.geocode import CENTROID_COLLAPSE_M
from laiive_shared.normalize import genre_family, norm
from loguru import logger

from config import settings

from .classifier import Constraints
from .router import ExecutionPlan, PlanKind

STANDARD_RETURN = """
WITH DISTINCT e, v, c{extra_with}
OPTIONAL MATCH (art:Artist)-[:PERFORMS_AT]->(e)
RETURN e.uid AS uid, e.name AS name, e.description AS description,
       toString(e.start_at) AS start_at, e.start_time_known AS start_time_known,
       e.timezone AS timezone,
       e.price_min AS price_min,
       e.price_max AS price_max, e.price_currency AS price_currency,
       e.ticket_url AS ticket_url, e.source AS source,
       e.source_url AS source_url, e.source_domain AS source_domain,
       v.name AS venue, v.venue_type AS venue_type, c.name AS city,
       v.location.latitude AS lat, v.location.longitude AS lng,
       v.geocode_precision AS geocode_precision,
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
    # An empty family means the word was not a genre ("various", "live"). The
    # clause is dropped rather than left to match nothing: a junk constraint
    # should stop filtering, not empty the answer.
    if c.genre and (genres := genre_family(c.genre)):
        # Extraction emits a composite slug whenever the page names more than
        # one style, and an exact match makes those invisible: 'pop-rock' is on
        # four artists and four events, and answers neither "rock" nor "pop".
        # A slug's hyphen-separated parts are genres in their own right, so the
        # asked genre matches a slug that is it or contains it as a whole part.
        # The family covers the spellings already in the graph: collapsing
        # aliases on write only ever helps rows written after it, and
        # 'electronica' is on two artists today.
        #
        # Matching on hyphen boundaries rather than on split() parts, because a
        # variant can itself be several parts: 'r-b' has to reach
        # 'r-b-pop-new-wave', which split() never offers as one element. The
        # boundaries are what keep it honest — "rap" must not match 'trap'.
        genre_match = (
            "ANY(asked IN $genres WHERE g.slug = asked "
            "OR g.slug STARTS WITH asked + '-' "
            "OR g.slug ENDS WITH '-' + asked "
            "OR g.slug CONTAINS '-' + asked + '-')"
        )
        where.append(
            f"(EXISTS {{ MATCH (e)-[:HAS_GENRE]->(g:Genre) WHERE {genre_match} }} OR "
            f"EXISTS {{ MATCH (g:Genre)<-[:HAS_GENRE]-(:Artist)-[:PERFORMS_AT]->(e) "
            f"WHERE {genre_match} }})"
        )
        params["genres"] = genres
    # A date window is a wall-clock question: "tonight in Bergamo" means the
    # hours the door is open there, whatever clock the asker is on. The
    # classifier emits a naive window, and datetime() would read it as UTC and
    # compare it against a zoned instant -- shifting every window by the
    # venue's offset, cutting a 19:00 Madrid gig out of "tonight" and pulling
    # the next local morning in. localdatetime() drops back to the wall clock
    # the offset was stored for, so both sides are read at the venue.
    if c.date_from:
        where.append("localdatetime(e.start_at) >= localdatetime($date_from)")
        params["date_from"] = c.date_from
    else:
        # Not a window but an instant -- "still to come" is the same moment
        # everywhere, so this one stays a zoned comparison.
        where.append("e.start_at >= datetime()")  # upcoming only by default
    if c.date_to:
        where.append("localdatetime(e.start_at) < localdatetime($date_to)")
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
    # A pin the repair sweep flagged as being in the wrong metro area is worse
    # than no pin: it would place the event confidently somewhere it is not.
    # Rows written before the flag existed are NULL and stay trusted.
    where.insert(1, "coalesce(v.geocode_precision, 'venue') <> 'suspect'")
    where.append(
        "point.distance(v.location, point({latitude: $lat, longitude: $lng})) <= $radius_m"
    )
    params.update(
        lat=lat,
        lng=lng,
        radius_m=radius_km * 1000,
        centroid_penalty_m=settings.location_centroid_penalty_km * 1000,
        limit=settings.max_results_limit,
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
        + "ORDER BY distance_m + CASE WHEN v.geocode_precision = 'city_centroid'\n"
        "                             THEN $centroid_penalty_m ELSE 0 END ASC,\n"
        "         distance_m ASC\n"
        "LIMIT $limit"
    )
    return cypher, params


# Nominatim answers a place with whatever object carries the name, and for a
# third of the neighbourhoods measured that is the central square rather than
# the district: Lavapiés, Poblenou and Barceloneta all come back as a 10 m box,
# and every landmark (Sagrada Família, Puerta del Sol, Alexanderplatz, Parc
# Güell) is a building or a plaza. Unpadded, those queries can only ever match
# a venue at the exact same coordinate. The floor is the median real
# neighbourhood in the same measurement — 2.8 km diagonal, i.e. a 2 km square —
# so a point-shaped answer is treated as the smallest plausible place.
NAMED_PLACE_MIN_SPAN_KM = 2.0
KM_PER_DEGREE_LAT = 111.32


def pad_bbox(
    bbox: tuple[float, float, float, float],
    min_span_km: float = NAMED_PLACE_MIN_SPAN_KM,
) -> tuple[float, float, float, float]:
    """Grow a box that is smaller than min_span_km on either axis, around its centre."""
    south, north, west, east = bbox
    km_per_degree_lng = KM_PER_DEGREE_LAT * math.cos(math.radians((south + north) / 2))
    if (north - south) * KM_PER_DEGREE_LAT < min_span_km:
        pad = (min_span_km / KM_PER_DEGREE_LAT - (north - south)) / 2
        south, north = south - pad, north + pad
    if km_per_degree_lng > 0 and (east - west) * km_per_degree_lng < min_span_km:
        pad = (min_span_km / km_per_degree_lng - (east - west)) / 2
        west, east = west - pad, east + pad
    return (south, north, west, east)


def build_bbox_query(
    c: Constraints, bbox: tuple[float, float, float, float]
) -> tuple[str, dict]:
    """Events inside a geographic box — the named-place leg.

    The city predicate is dropped because the box replaces it: "Kreuzberg" is
    not a City node and never will be, so matching it by name is what returned
    nothing in the first place.

    City-centroid pins are excluded rather than merely ranked down (as NEARBY
    does). A centroid sits inside the bbox of whichever central district
    contains it, so keeping them would put every un-located venue in Berlin
    inside Mitte — a confident wrong answer, not an imprecise one.

    That exclusion cannot rely on the flag alone. Measured against the live
    graph, all six venues sitting on Madrid's centroid are unstamped, and
    trusting NULL the way nearby does put the Metropolitano stadium in
    Malasaña. So the geometry is checked twice, neither test needing the flag:

    - a pin on its own city's stored centre is a fallback; and
    - a pin shared with another venue in the same city is a fallback too,
      whatever it happens to coincide with. This is the one that generalises:
      eight Barcelona venues sat on Nominatim's answer for "barcelona", which
      is 888 m from the City node's own location, so the centre test alone did
      not see them. Two venues cannot share a doorway.
    """
    south, north, west, east = bbox
    where, params = _constraint_clauses(c.model_copy(update={"city": None}))
    where.insert(0, "e.status = 'scheduled'")
    where.insert(0, "v.location IS NOT NULL")
    where.insert(1, "coalesce(v.geocode_precision, 'venue') = 'venue'")
    where.append(
        "(c.location IS NULL OR "
        "point.distance(v.location, c.location) > $centroid_collapse_m)"
    )
    # Scoped to the bound city, so this reads one city's venues rather than
    # scanning the label.
    where.append(
        "NOT EXISTS { MATCH (other:Venue)-[:LOCATED_IN]->(c) "
        "WHERE other.location = v.location AND other.uid <> v.uid }"
    )
    where.append("v.location.latitude >= $south AND v.location.latitude <= $north")
    where.append("v.location.longitude >= $west AND v.location.longitude <= $east")
    params.update(
        south=south,
        north=north,
        west=west,
        east=east,
        centroid_collapse_m=CENTROID_COLLAPSE_M,
        limit=settings.max_results_limit,
    )
    cypher = (
        "MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)\n"
        "WHERE "
        + "\n  AND ".join(where)
        + "\n"
        + STANDARD_RETURN.format(extra_with="", extra_return="")
        + "ORDER BY start_at LIMIT $limit"
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


# A saved list is fetched by uid in one call. The cap is protocol, not tuning:
# it bounds the query string the gateway forwards and the rows one request can
# pull. Anything longer is the client's to page through.
EVENT_LOOKUP_MAX_UIDS = 50


def build_uid_query(uids: list[str]) -> tuple[str, dict]:
    """Cards for a known set of event uids — a lookup, not a search.

    No status, no date and no location predicate, unlike every other builder
    here. Those answer "what is on"; this answers "what did I put aside", and a
    saved event that was cancelled or has already happened is still the thing
    somebody saved. Filtering it out would make a card vanish from the list
    with no explanation, which is worse than a card showing a past date.

    `e.uid` is backed by the event_uid uniqueness constraint, so the IN is an
    index seek rather than a label scan.
    """
    cypher = (
        "MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)-[:LOCATED_IN]->(c:City)\n"
        "WHERE e.uid IN $uids\n"
        + STANDARD_RETURN.format(extra_with="", extra_return="")
        + "ORDER BY start_at"
    )
    return cypher, {"uids": uids}


def rows_to_cards(rows: list[dict]) -> list[EventCard]:
    """Standard-shape rows → EventCards. Distance arrives in meters."""
    cards = []
    for row in rows:
        distance_m = row.get("distance_m")
        # A pin the repair sweep flagged as being in the wrong metro area is
        # not sent at all. Nearby already refuses to match on one, but the
        # template and vector legs have no location predicate, so this is where
        # the guarantee has to hold: the card keeps its event and loses its map.
        precision = row.get("geocode_precision")
        suspect = precision == "suspect"
        cards.append(
            EventCard(
                uid=row.get("uid") or "",
                name=row.get("name") or "",
                artists=[a for a in (row.get("artists") or []) if a],
                venue=row.get("venue"),
                venue_type=row.get("venue_type"),
                city=row.get("city"),
                start_at=row.get("start_at"),
                timezone=row.get("timezone"),
                start_time_known=row.get("start_time_known"),
                price_min=row.get("price_min"),
                price_max=row.get("price_max"),
                price_currency=row.get("price_currency"),
                description=row.get("description"),
                ticket_url=row.get("ticket_url"),
                lat=None if suspect else row.get("lat"),
                lng=None if suspect else row.get("lng"),
                geocode_precision=precision,
                source=row.get("source") or "unknown",
                source_url=row.get("source_url"),
                source_domain=row.get("source_domain"),
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
                timezone=_get(row, "timezone") or _get(props, "timezone"),
                price_min=_get(props, "price_min", "price_amount"),
                price_max=_get(props, "price_max"),
                price_currency=_get(props, "price_currency"),
                description=_get(props, "description"),
                ticket_url=_get(props, "ticket_url", "url"),
                source=str(_get(props, "source") or "unknown"),
                source_url=_get(props, "source_url"),
                source_domain=_get(props, "source_domain"),
            )
        )
    return cards


@dataclass
class Outcome:
    cards: list[EventCard] = field(default_factory=list)
    cypher: str | None = None
    error: str | None = None
    # How the rows were found, when that is not what the user literally asked
    # for. Reaches the composer so it does not overstate the match.
    note: str | None = None


class Executor:
    def __init__(self, neo4j_client, embed_fn, query_builder, geocoder=None):
        """
        Args:
            neo4j_client: read-access client with execute_read(cypher, params).
            embed_fn: text → embedding vector (for the vector leg).
            query_builder: LLM Cypher generator for the long tail.
            geocoder: resolves a named place to a bounding box when the city
                template finds nothing. Omitted → the fallback never runs.
        """
        self.neo4j = neo4j_client
        self.embed = embed_fn
        self.query_builder = query_builder
        self.geocoder = geocoder

    def execute(
        self,
        plan: ExecutionPlan,
        location: dict | None = None,
        timezone: str | None = None,
    ) -> Outcome:
        try:
            if plan.kind == PlanKind.TEMPLATE:
                cypher, params = build_template_query(plan.constraints)
                rows = self.neo4j.execute_read(cypher, params)
                if not rows and (found := self._execute_named_place(plan.constraints)):
                    return found
                return Outcome(rows_to_cards(rows), cypher)

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

            return self._execute_llm_cypher(plan.constraints, timezone)
        except Exception as e:
            logger.error(f"Execution failed for {plan.kind}: {e}")
            return Outcome(error=str(e))

    def _execute_named_place(self, c: Constraints) -> Outcome | None:
        """Second chance for a place that is not a City node.

        The classifier puts every named place in `city`, so "techno in
        Kreuzberg" asks for a City whose name is Kreuzberg and gets nothing.
        Geocoding it yields a bounding box, and the box is a filter the graph
        can answer. This runs only after the template returned zero rows, so
        the common case — a real city with events — pays nothing for it.

        Returns None when the fallback does not apply or finds nothing, leaving
        the caller's empty result (and its cypher) as the answer.
        """
        if self.geocoder is None or not c.city:
            return None
        place = self.geocoder.geocode(c.city)
        if place is None or place.bbox is None:
            return None
        diagonal = place.bbox_diagonal_km()
        if diagonal is None or diagonal > settings.named_place_max_diagonal_km:
            # A region or a country resolves to a box big enough to contain the
            # whole graph, at which point "in X" has stopped filtering anything.
            logger.info(
                f"Named-place fallback skipped for {c.city!r}: "
                f"{place.display_name!r} spans {diagonal:.0f} km"
            )
            return None
        cypher, params = build_bbox_query(c, pad_bbox(place.bbox))
        rows = self.neo4j.execute_read(cypher, params)
        if not rows:
            return None
        logger.info(
            f"Named-place fallback matched {c.city!r} to {place.display_name!r} "
            f"({diagonal:.1f} km across): {len(rows)} events"
        )
        # The box is padded to a minimum span and a neighbourhood has no hard
        # edge anyway, so some of these are near the place rather than in it.
        # The composer is told, because "events in Barceloneta" is a claim the
        # retrieval cannot actually make.
        return Outcome(
            rows_to_cards(rows),
            cypher,
            note=(
                f"{c.city!r} is not a city in the graph; these were found in the "
                f"area around it, so some may be just outside it"
            ),
        )

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

    def _execute_llm_cypher(
        self, c: Constraints, timezone: str | None = None
    ) -> Outcome:
        raw = self.query_builder.run(c.query_text or "", timezone)
        data = json.loads(raw)
        if data.get("status") != "success":
            return Outcome(
                error=data.get("error", "query generation failed"),
                cypher=data.get("cypher"),
            )
        return Outcome(
            flexible_rows_to_cards(data.get("results", [])), data.get("cypher")
        )
