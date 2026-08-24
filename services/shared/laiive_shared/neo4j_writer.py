"""MERGE-by-identity graph write path (03-ontology §3, 04-plan Phase 2).

The only code allowed to write domain nodes. Identity keys:
Event (name_norm, start_at) · Artist name_norm · Venue name_norm within its
city · City (name_norm, country_code) · Genre slug. Every node gets `source`
provenance and, for pro submissions, the submitting user's `owner_id`.

Clients (services) inject their own OpenAI embedding call and geocoder so this
module owns no API clients — that keeps test patching in one place per service.
"""

import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from timezonefinder import TimezoneFinder

from .cards import EventDraft, missing_required
from .embedding_text import artist_text, event_text, venue_text
from .geocode import AddressResolver, NominatimGeocoder
from .normalize import (
    canonical_city_name,
    clean_city_name,
    genre_slug,
    norm,
    source_domain,
)

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


def has_explicit_time(raw: str) -> bool:
    """Whether the listing actually stated a time, or only a date.

    A page that says "29 August" and nothing else parses to midnight, and
    midnight then reads as a fact: 30 of 57 discovered events display a 00:00
    start they never claimed. Rather than guess, the caller records this and
    the card shows a date with no time.

    Detected from the text, not from the parsed value, because a real midnight
    gig ("2026-08-29T00:00") is indistinguishable from a defaulted one once it
    is a datetime.
    """
    return bool(raw) and bool(re.search(r"\d{1,2}[:.]\d{2}", raw))


# Building the finder reads its boundary tables off disk, so it is built once
# per process and shared. It is documented as thread-safe for lookups.
_timezone_finder: TimezoneFinder | None = None


def resolve_timezone(lat: float | None, lng: float | None) -> str | None:
    """IANA zone for a coordinate, or None when there is no coordinate.

    A listing says "21:00" and means 21:00 at the door. Without the venue's own
    zone that wall-clock reading has to be assumed to be something, and
    assuming UTC silently moved every event in the graph by its offset — a
    22:00 gig in Bergamo was stored as 00:00 the next day.

    The country code is not a substitute: Spain spans Europe/Madrid and
    Atlantic/Canary, and the graph already holds Spanish events.
    """
    if lat is None or lng is None:
        return None
    global _timezone_finder
    if _timezone_finder is None:
        _timezone_finder = TimezoneFinder()
    # Returns None over open water, which for a venue means a bad pin.
    return _timezone_finder.timezone_at(lat=lat, lng=lng)


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
    address_resolver: AddressResolver | None = None,
    source_url: str = "",
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
        address_resolver: last-resort (venue, city) -> street address, for the
            venues OSM has no named POI for. Skipped when None.
        source_url: the page this event was read off, for a discovered event.
            Deliberately an argument rather than an EventDraft field: it is
            what the caller knows, not something extracted from the page, and
            a field on the draft is a field the model can invent.
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
    # Resolved once and used for the node, the MERGE key and the geocoder
    # alike: a promoter typing "Ponteranica, BG" must not create a second City
    # beside the one every search actually reaches.
    city = clean_city_name(draft.city or "")
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
            city=city,
            message="An event with the same name, date, and venue already exists.",
        )

    # ── Geocode city, then venue (D12) ───────────────────────────────────────
    # City first: it doubles as the plausibility reference for the venue, so a
    # same-name venue in another province is rejected rather than written.
    venue_geo = city_geo = None
    # Recorded on the node so the nightly repair sweep can find the pins that
    # are only approximately right. A centroid fallback is not NULL, so without
    # this flag it is indistinguishable from a real venue location.
    precision = None
    if geocoder is not None:
        city_geo = geocoder.geocode(city)
        if city_geo is not None:
            # The geocoder answers in the local language, so this collapses the
            # exonym split before the name becomes a MERGE key: one Torino
            # sweep returned eight candidates saying Torino and seven saying
            # Turin, which is two City nodes and a search that finds half its
            # events. Done before the venue lookup so both ask for one place.
            city = canonical_city_name(city_geo.display_name) or city
        venue_geo = geocoder.geocode_venue(
            draft.venue,
            draft.address,
            city,
            near=city_geo,
            address_resolver=address_resolver,
        )
        if venue_geo is not None:
            precision = "venue"
        elif city_geo is not None:
            venue_geo = city_geo  # fall back to the city centroid
            precision = "city_centroid"
            warnings.append("Venue could not be geocoded; using city centroid.")
    if venue_geo is None:
        warnings.append(
            "No venue location — this event will not appear in nearby search."
        )

    # ── Localise the start time to the venue (D-tz) ──────────────────────────
    # The draft carries a wall-clock reading with no zone: "21:00" off a poster,
    # or whatever the promoter typed into the form. It only becomes an instant
    # once it is read in the venue's zone, so that happens here, after geocoding
    # has produced a coordinate and before the write.
    timezone = resolve_timezone(
        venue_geo.lat if venue_geo else None,
        venue_geo.lng if venue_geo else None,
    )
    if timezone is not None:
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=ZoneInfo(timezone))
        else:
            # fromisoformat keeps an explicit offset ("...+02:00", "...Z"), and
            # replace() on an aware value would relabel the digits into the
            # venue zone and shift the stored instant. The draft already stated
            # an instant; keep it, and only re-express it on the venue's clock.
            start_at = start_at.astimezone(ZoneInfo(timezone))
    else:
        # Storing it as UTC is what this did for every event written before
        # this existed. Keep that rather than refuse the write, but say so and
        # flag the row so the backfill can find it if a pin arrives later.
        warnings.append(
            "Could not resolve the venue's timezone; the start time is stored as UTC."
        )
    country_code = (city_geo.country_code if city_geo else "") or (
        venue_geo.country_code if venue_geo else ""
    )
    if not country_code:
        warnings.append("Could not resolve the city's country code.")

    event_uid = str(uuid.uuid4())
    genre = genre_slug(draft.genre) if draft.genre else ""
    # Hoisted so the embedding backfill below can be scoped to what this write
    # touched. MERGE means a pre-existing artist keeps its own uid and these are
    # never used — which is fine, it already has an embedding or the nightly
    # backfill will reach it.
    artist_rows = [
        {"name": a, "name_norm": norm(a), "uid": str(uuid.uuid4())}
        for a in draft.artists
    ]
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
                          v.geocode_precision = $geocode_precision,
                          v.source = $source, v.owner_id = $owner_id,
                          v.created_at = datetime()

            CREATE (e:Event {
                uid: $event_uid, name: $name, name_norm: $name_norm,
                description: $description, start_at: datetime($start_at),
                start_time_known: $start_time_known, timezone: $timezone,
                price_min: $price_min, price_max: $price_max,
                price_currency: $price_currency, ticket_url: $ticket_url,
                status: 'scheduled', source: $source, owner_id: $owner_id,
                source_url: $source_url, source_domain: $source_domain,
                created_at: datetime(), updated_at: datetime()
            })
            MERGE (e)-[:HOSTED_AT]->(v)

            FOREACH (_ IN CASE WHEN $genre <> '' THEN [1] ELSE [] END |
                MERGE (g:Genre {slug: $genre})
                ON CREATE SET g.name = $genre_name
                MERGE (e)-[:HAS_GENRE]->(g)
            )

            // FOREACH, not UNWIND: an empty artist list must not consume the
            // row and turn the RETURN below into "no record" after the CREATE
            // has already committed.
            FOREACH (artist IN $artists |
                MERGE (a:Artist {name_norm: artist.name_norm})
                ON CREATE SET a.uid = artist.uid, a.name = artist.name,
                              a.source = $source, a.owner_id = $owner_id,
                              a.created_at = datetime()
                MERGE (a)-[:PERFORMS_AT]->(e)
                FOREACH (_ IN CASE WHEN $genre <> '' THEN [1] ELSE [] END |
                    MERGE (g:Genre {slug: $genre})
                    MERGE (a)-[:HAS_GENRE]->(g)
                )
            )

            RETURN e.uid AS uid, e.name AS name, v.name AS venue, c.name AS city,
                   v.uid AS venue_uid
            """,
            city=city,
            city_norm=norm(city),
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
            geocode_precision=precision,
            event_uid=event_uid,
            name=name,
            name_norm=norm(name),
            description=draft.description or "",
            start_at=start_at.isoformat(),
            # Empty rather than NULL so the property always exists and a card
            # can distinguish "we do not know" from a zone we simply did not
            # return. An empty zone means the instant above is UTC by default.
            timezone=timezone or "",
            # A listing that gave only a date parses to midnight, and midnight
            # then reads as a stated fact on the card. Record which it was.
            start_time_known=has_explicit_time(draft.start_at or ""),
            price_min=draft.price_min,
            price_max=draft.price_max
            if draft.price_max is not None
            else draft.price_min,
            price_currency=draft.price_currency or "EUR",
            ticket_url=draft.ticket_url or "",
            genre=genre,
            genre_name=(draft.genre or "").strip().title(),
            artists=artist_rows,
            source=source,
            owner_id=owner_id,
            source_url=source_url,
            # Stored beside the URL rather than derived on read: it is the key
            # every "which sites are worth sweeping" question groups by, and
            # parsing a URL inside a Cypher aggregation is not a thing.
            source_domain=source_domain(source_url),
        ).single()
    except Exception as e:  # neo4j errors surface as a typed result, not a 500
        logger.error("Event write failed: %s", e)
        return WriteResult(status="error", message=str(e))

    if record is None:
        return WriteResult(status="error", message="No record returned from Neo4j")

    if embed_texts is not None:
        # Scoped to the nodes this write created. Unscoped, this was a full-graph
        # scan for un-embedded nodes inside every single submission — the cost
        # grew with the graph, two writers duplicated each other's work and each
        # paid OpenAI for it. The unbounded sweep has exactly one owner now: the
        # nightly backfill flow.
        written = [record["uid"], record["venue_uid"]] + [a["uid"] for a in artist_rows]
        try:
            backfill_embeddings(
                session,
                embed_texts,
                embedding_model,
                uids=[u for u in written if u],
            )
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


def tag_artist_genres(session, tags: dict[str, str]) -> int:
    """Attach a genre to artists that have none. Returns how many were tagged.

    Lives here rather than in a script because this module is the only path
    that writes to the graph, and because the Genre MERGE has to agree with the
    one in write_event -- same slug key, same title-cased name on create, or a
    second node appears for the genre that already exists.

    Only ever adds: an artist that already carries a genre is left alone, so a
    re-run is a no-op and a human correction is never overwritten by a model.
    """
    if not tags:
        return 0
    rows = [
        {
            "name_norm": norm(name),
            "genre": genre_slug(genre),
            "name": genre.strip().title(),
        }
        for name, genre in tags.items()
        if name and genre
    ]
    record = session.run(
        """
        UNWIND $rows AS row
        MATCH (a:Artist {name_norm: row.name_norm})
        WHERE NOT EXISTS { (a)-[:HAS_GENRE]->(:Genre) }
        MERGE (g:Genre {slug: row.genre})
          ON CREATE SET g.name = row.name
        MERGE (a)-[:HAS_GENRE]->(g)
        RETURN count(DISTINCT a) AS tagged
        """,
        rows=rows,
    ).single()
    return record["tagged"] if record else 0


def backfill_embeddings(
    session,
    embed_texts: EmbedFn,
    embedding_model: str,
    uids: list[str] | None = None,
) -> int:
    """Embed Event/Artist/Venue nodes that have no embedding yet.

    Builds the composite texts with the shared recipes, embeds them in one
    batch call per label, and stores vector + text + model. Returns the number
    of nodes embedded.

    `uids` narrows the scan to specific nodes — that is the per-write path, where
    the cost must be proportional to the event being written, not to the size of
    the graph. Omit it for the nightly sweep that catches everything else
    (`services/search/flows/backfill.py`); it is the only caller that should.
    """
    jobs: list[tuple[str, str, str]] = []  # (label, uid, text)

    def scope(var: str) -> str:
        """The uid predicate for one query variable, or nothing when unscoped."""
        return f"AND {var}.uid IN $uids" if uids is not None else ""

    for row in session.run(
        f"""
        MATCH (e:Event) WHERE e.embedding IS NULL {scope("e")}
        OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
        OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)
        OPTIONAL MATCH (a:Artist)-[:PERFORMS_AT]->(e)
        OPTIONAL MATCH (e)-[:HAS_GENRE]->(g:Genre)
        RETURN e.uid AS uid, e.name AS name, e.description AS description,
               toString(e.start_at) AS start_at, v.name AS venue, c.name AS city,
               collect(DISTINCT a.name) AS artists, collect(DISTINCT g.name) AS genres
        """,
        uids=uids,
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
        f"""
        MATCH (a:Artist) WHERE a.embedding IS NULL {scope("a")}
        OPTIONAL MATCH (a)-[:BASED_IN]->(c:City)
        OPTIONAL MATCH (a)-[:HAS_GENRE]->(g:Genre)
        RETURN a.uid AS uid, a.name AS name, a.description AS description,
               c.name AS city, collect(DISTINCT g.name) AS genres
        """,
        uids=uids,
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
        f"""
        MATCH (v:Venue) WHERE v.embedding IS NULL {scope("v")}
        OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)
        RETURN v.uid AS uid, v.name AS name, v.venue_type AS venue_type,
               v.address AS address, c.name AS city, v.description AS description
        """,
        uids=uids,
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
