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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _VenueIdentity:
    """The venue as this write will treat it — read off the node when the
    caller picked one, off the draft otherwise. One value, resolved once, so
    the dedup probe, the geocoder gate, the timezone and the write clause
    cannot disagree about which venue they are talking about."""

    uid: str | None  # the graph uid when picked, else None
    name: str
    name_norm: str
    city: str
    country_code: str  # "" when nothing has resolved it yet
    address: str | None
    lat: float | None
    lng: float | None


class WriteResult(BaseModel):
    status: Literal["created", "adopted", "duplicate", "invalid", "error"]
    uid: str | None = None
    name: str | None = None
    venue: str | None = None
    city: str | None = None
    missing: list[str] = []
    warnings: list[str] = []
    message: str = ""
    # What this write brought into existence, as opposed to what it linked to.
    # Ownership is recorded on creation - you made the thing - and a venue this
    # event merely names is somebody else's room, so the gateway needs the
    # difference rather than the list of everything the event touches.
    #
    # Detected by uid identity, which costs no extra query: every MERGE below
    # assigns its proposed uuid ON CREATE only, so a node that came back
    # carrying the uuid this call generated is one this call created, and a
    # pre-existing node kept its own.
    venue_uid: str | None = None
    venue_created: bool = False
    artist_uids_created: list[str] = []


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
    venue_uid: str | None = None,
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
        venue_uid: an existing graph venue the client picked from a lookup.
            An argument for the same reason source_url is one — mid-walk
            refinement round-trips drafts through an LLM, and a uid a model
            invented dies on the MATCH below rather than forking a venue.
    """
    missing = missing_required(draft, source, venue_known=bool(venue_uid))
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

    # ── A picked venue: resolve the node first, and let the graph win ────────
    # The node is the truth when a uid was picked: the draft's spelling of the
    # venue or its city must not fork a second identity beside it.
    if venue_uid:
        # Guarded like the write below: these reads run before the big try,
        # and an Aura routing flap here used to escape as a raw exception and
        # a bare 500, instead of the typed error this module promises.
        try:
            picked = session.run(
                """
                MATCH (v:Venue {uid: $uid})-[:LOCATED_IN]->(c:City)
                RETURN v.name AS name, v.name_norm AS name_norm,
                       v.address AS address,
                       v.location.latitude AS lat, v.location.longitude AS lng,
                       c.name AS city, c.country_code AS country_code
                LIMIT 1
                """,
                uid=venue_uid,
            ).single()
        except Exception as e:
            logger.error("Venue resolve failed: %s", e)
            return WriteResult(status="error", message=str(e))
        if picked is None:
            return WriteResult(
                status="invalid",
                missing=["venue_uid"],
                message="No venue with that uid — pick it again or type the venue.",
            )
        if not picked["address"] and not draft.address:
            return WriteResult(
                status="invalid",
                missing=["address"],
                message="This venue has no address on file yet — please add one.",
            )
        ident = _VenueIdentity(
            uid=venue_uid,
            name=picked["name"],
            name_norm=picked["name_norm"],
            city=picked["city"],
            country_code=picked["country_code"] or "",
            address=picked["address"],
            lat=picked["lat"],
            lng=picked["lng"],
        )
    else:
        # Resolved once and used for the node, the MERGE key and the geocoder
        # alike: a promoter typing "Ponteranica, BG" must not create a second
        # City beside the one every search actually reaches.
        ident = _VenueIdentity(
            uid=None,
            name=draft.venue,
            name_norm=norm(draft.venue),
            city=clean_city_name(draft.city or ""),
            country_code="",
            address=draft.address,
            lat=None,
            lng=None,
        )

    # Generated once and kept: the write proposes it, and comparing it against
    # what comes back is how "this call created the venue" is known.
    proposed_venue_uid = str(uuid.uuid4())
    name = draft.name or f"{draft.artists[0]} live at {ident.name}"
    city = ident.city
    warnings: list[str] = []

    # ── Dedup probe: same name + calendar day + venue ────────────────────────
    #
    # A hit is not automatically a refusal. The sweep writes events nobody has
    # confirmed, and the card says so in as many words ("The promoter has not
    # confirmed it"); refusing the promoter who then comes to publish that very
    # night contradicts the promise, and leaves the guess standing as the only
    # version. So an unowned listing is *adopted* by the promoter rather than
    # duplicated beside it or replaced under it.
    try:
        existing = session.run(
            """
            MATCH (e:Event {name_norm: $name_norm})-[:HOSTED_AT]->(v:Venue {name_norm: $venue_norm})
            WHERE date(e.start_at) = date(datetime($start_at))
            RETURN e.uid AS uid, e.name AS name, e.owner_id AS owner_id LIMIT 1
            """,
            name_norm=norm(name),
            venue_norm=ident.name_norm,
            start_at=start_at.isoformat(),
        ).single()
    except Exception as e:
        logger.error("Dedup probe failed: %s", e)
        return WriteResult(status="error", message=str(e))

    # Adoption keeps the uid. Saved lists, entity_ownership rows, embeddings and
    # the search report that discovered it all point at it; deleting the node
    # and writing a fresh one turns every one of those into a dangling pointer,
    # and someone's saved card silently disappears. Archiving does the same.
    adopting = False
    if existing:
        unowned = existing["owner_id"] is None
        if source == "pro_submission" and unowned:
            adopting = True
        else:
            return WriteResult(
                status="duplicate",
                uid=existing["uid"],
                name=existing["name"],
                venue=draft.venue,
                city=city,
                message=(
                    "That event is already published by its promoter."
                    if not unowned
                    else "An event with the same name, date, and venue already exists."
                ),
            )

    # ── Geocode city, then venue (D12) ───────────────────────────────────────
    # City first: it doubles as the plausibility reference for the venue, so a
    # same-name venue in another province is rejected rather than written.
    venue_geo = city_geo = None
    # Recorded on the node so the nightly repair sweep can find the pins that
    # are only approximately right. A centroid fallback is not NULL, so without
    # this flag it is indistinguishable from a real venue location.
    precision = None
    already_pinned = ident.lat is not None
    if geocoder is not None and not already_pinned:
        city_geo = geocoder.geocode(city)
        if city_geo is not None and ident.uid is None:
            # The geocoder answers in the local language, so this collapses the
            # exonym split before the name becomes a MERGE key: one Torino
            # sweep returned eight candidates saying Torino and seven saying
            # Turin, which is two City nodes and a search that finds half its
            # events. Done before the venue lookup so both ask for one place.
            # A picked venue keeps its node's city — that identity is settled.
            city = canonical_city_name(city_geo.display_name) or city
        venue_geo = geocoder.geocode_venue(
            ident.name,
            # A picked venue may carry its street while the draft does not
            # (the form shows the on-file address rather than re-asking): the
            # node's address must reach the geocoder, or a name-only miss
            # coalesces a city centroid onto a venue whose street we knew.
            draft.address or ident.address,
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
    if venue_geo is None and not already_pinned:
        warnings.append(
            "No venue location — this event will not appear in nearby search."
        )

    # ── Localise the start time to the venue (D-tz) ──────────────────────────
    # The draft carries a wall-clock reading with no zone: "21:00" off a poster,
    # or whatever the promoter typed into the form. It only becomes an instant
    # once it is read in the venue's zone, so that happens here, after geocoding
    # has produced a coordinate and before the write.
    timezone = resolve_timezone(
        ident.lat if already_pinned else (venue_geo.lat if venue_geo else None),
        ident.lng if already_pinned else (venue_geo.lng if venue_geo else None),
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
    country_code = ident.country_code or (
        (city_geo.country_code if city_geo else "")
        or (venue_geo.country_code if venue_geo else "")
    )
    if not country_code:
        warnings.append("Could not resolve the city's country code.")

    # On adoption this is the node being taken over, not a new one.
    event_uid = existing["uid"] if adopting else str(uuid.uuid4())
    genre = genre_slug(draft.genre) if draft.genre else ""
    # Hoisted so the embedding backfill below can be scoped to what this write
    # touched. MERGE means a pre-existing artist keeps its own uid and these are
    # never used — which is fine, it already has an embedding or the nightly
    # backfill will reach it.
    artist_rows = [
        {"name": a, "name_norm": norm(a), "uid": str(uuid.uuid4())}
        for a in draft.artists
    ]
    # A picked venue is matched by uid and only ever completed, never
    # overwritten: filling an empty address (and the pin that follows it) is
    # finishing the record, while changing a stated one is an owner's edit and
    # goes through a different door entirely.
    venue_clause = (
        """
            MATCH (v:Venue {uid: $picked_uid})-[:LOCATED_IN]->(c:City)
            // One row however many LOCATED_IN edges the node has grown (the
            // seed can attach a second city): without this, the CREATE below
            // runs once per row and dies on the event_uid constraint.
            WITH v, c LIMIT 1
            SET v.address = coalesce(v.address, $address),
                v.location = coalesce(v.location,
                    CASE WHEN $venue_lat IS NULL THEN NULL
                         ELSE point({latitude: $venue_lat, longitude: $venue_lng}) END),
                v.geocode_precision = coalesce(v.geocode_precision, $geocode_precision)
        """
        if ident.uid is not None
        else """
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
        """
    )
    # Only the head differs between creating and adopting: the genre, the
    # artists and the read-back below are the same work either way, and a second
    # copy of them is a second place for the two to drift apart.
    #
    # What adoption does NOT set: `uid` (the match key), `created_at` (the node
    # was created when it was created) and `status` — re-publishing must not
    # quietly un-cancel a night that was called off.
    #
    # The promoter wins on every fact the card promises them for ("the times,
    # the price and the door are as they entered them"). Where empty means "not
    # provided" rather than "delete this", the existing value survives: a
    # promoter who omits the ticket link should not wipe the one the sweep
    # found, and keeping source_url is also what lets the search learning still
    # credit the domain that turned up a night a promoter later confirmed.
    event_clause = (
        """
            // WITH, or the planner refuses: a MATCH may not directly follow the
            // updating clause the venue block ends on. The create path below
            // needs none because CREATE after SET is two updates in a row.
            WITH v, c
            MATCH (e:Event {uid: $event_uid})
            SET e.name = $name, e.name_norm = $name_norm,
                e.start_at = datetime($start_at),
                e.start_time_known = $start_time_known, e.timezone = $timezone,
                e.price_min = coalesce($price_min, e.price_min),
                e.price_max = coalesce($price_max, e.price_max),
                e.price_currency = $price_currency,
                e.description = CASE WHEN $description <> ''
                    THEN $description ELSE e.description END,
                e.ticket_url = CASE WHEN $ticket_url <> ''
                    THEN $ticket_url ELSE e.ticket_url END,
                e.source_url = CASE WHEN $source_url <> ''
                    THEN $source_url ELSE e.source_url END,
                e.source_domain = CASE WHEN $source_url <> ''
                    THEN $source_domain ELSE e.source_domain END,
                e.source = $source, e.owner_id = $owner_id,
                e.updated_at = datetime()
        """
        if adopting
        else """
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
        """
    )
    try:
        record = session.run(
            venue_clause
            + event_clause
            + """
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

            // The FOREACH above cannot return, so the artists are read back
            // here. This is every artist on the event, existing ones included;
            // which of them are new is decided by uid identity in Python.
            WITH e, v, c
            OPTIONAL MATCH (art:Artist)-[:PERFORMS_AT]->(e)
            RETURN e.uid AS uid, e.name AS name, v.name AS venue, c.name AS city,
                   v.uid AS venue_uid, collect(DISTINCT art.uid) AS artist_uids
            """,
            picked_uid=ident.uid,
            city=city,
            city_norm=norm(city),
            country_code=country_code,
            city_lat=city_geo.lat if city_geo else None,
            city_lng=city_geo.lng if city_geo else None,
            venue=ident.name,
            venue_norm=ident.name_norm,
            venue_uid=proposed_venue_uid,
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

    # A MERGEd artist that already existed kept its own uid, so the uid this
    # call proposed for it never landed. Intersecting the two sets is what
    # separates "created here" from "linked to" - and it also fixes the
    # embedding scope below, which used to pass proposed uids that matched no
    # node for every pre-existing artist.
    proposed_artist_uids = {a["uid"] for a in artist_rows}
    artist_uids_created = [
        uid for uid in (record["artist_uids"] or []) if uid in proposed_artist_uids
    ]

    if embed_texts is not None:
        # Scoped to the nodes this write created. Unscoped, this was a full-graph
        # scan for un-embedded nodes inside every single submission — the cost
        # grew with the graph, two writers duplicated each other's work and each
        # paid OpenAI for it. The unbounded sweep has exactly one owner now: the
        # nightly backfill flow.
        written = [record["uid"], record["venue_uid"], *artist_uids_created]
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
        status="adopted" if adopting else "created",
        uid=record["uid"],
        name=record["name"],
        venue=record["venue"],
        city=record["city"],
        venue_uid=record["venue_uid"],
        venue_created=record["venue_uid"] == proposed_venue_uid,
        artist_uids_created=artist_uids_created,
        warnings=warnings,
        message="Event updated." if adopting else "Event created.",
    )


# ── Owner edits (Phase E) ─────────────────────────────────────────────────────
#
# MATCH-by-uid + SET, PATCH semantics: only the fields present in `fields`
# change, and an explicit None clears where the schema allows it — the form
# sends a diff, so "absent" and "cleared" stay distinguishable. What adoption
# deliberately leaves alone stays untouchable here too (uid, created_at), and
# an edit additionally never touches source/owner_id — adoption sets those
# because ownership is being transferred; an edit transfers nothing.
# Authorization is the gateway's user_may_edit question; this module only
# writes. Venue/artist renames are excluded: name_norm IS the MERGE identity,
# and a rename is a node-merge design of its own, not a SET.

_EVENT_TEXT_FIELDS = {"name", "start_at", "description", "genre"}
_EVENT_EDITABLE = _EVENT_TEXT_FIELDS | {
    "price_min",
    "price_max",
    "price_currency",
    "ticket_url",
    "status",
}
_VENUE_TEXT_FIELDS = {"venue_type", "address", "description"}
_VENUE_EDITABLE = _VENUE_TEXT_FIELDS | {"capacity"}
_ARTIST_EDITABLE = {"description", "genres"}


class UpdateResult(BaseModel):
    status: Literal["updated", "duplicate", "invalid", "not_found", "error"]
    uid: str | None = None
    # field -> {"old": ..., "new": ...}. Only fields that actually changed
    # appear; this is the delta the gateway files into entity_edits, so it has
    # to be the writer's own reading of the node, not the caller's claim.
    changed: dict[str, dict] = {}
    warnings: list[str] = []
    message: str = ""


def _refresh_embedding(
    session, label: str, uid: str, embed_texts: EmbedFn | None, embedding_model: str
) -> list[str]:
    """NULL the embedding quartet, then re-embed in place when a client is on
    hand. The scoped backfill (and the nightly sweep) select only nodes with NO
    embedding, so an updated node must lose its vector first or it stays stale
    forever. Best-effort: the edit itself has already landed, so a failure here
    is a warning, not a lost write."""
    warnings: list[str] = []
    try:
        session.run(
            f"MATCH (n:{label} {{uid: $uid}}) "
            "SET n.embedding = NULL, n.embedding_text = NULL, "
            "n.embedding_model = NULL, n.embedding_updated_at = NULL",
            uid=uid,
        )
        if embed_texts is not None:
            backfill_embeddings(session, embed_texts, embedding_model, uids=[uid])
    except Exception as e:
        logger.error("Re-embedding failed: %s", e)
        warnings.append(f"Embedding not refreshed: {e}")
    return warnings


def update_event(
    session,
    uid: str,
    fields: dict,
    *,
    embed_texts: EmbedFn | None = None,
    embedding_model: str = "",
) -> UpdateResult:
    """Edit an event in place, PATCH-style.

    Editable: name, start_at, description, genre, prices, ticket_url, and
    status — the last whitelisted to scheduled/cancelled and only ever an
    explicit field, so a cancel is an intent and never a draft round-trip's
    side effect. Venue and artists are not editable here (relinking deferred).
    A name or date change re-runs the dedup probe excluding this uid: an edit
    must not silently land on another night's key.
    """
    unknown = set(fields) - _EVENT_EDITABLE
    if unknown:
        return UpdateResult(
            status="invalid",
            uid=uid,
            message=f"These fields cannot be edited: {', '.join(sorted(unknown))}",
        )

    try:
        current = session.run(
            """
            MATCH (e:Event {uid: $uid})
            OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
            OPTIONAL MATCH (e)-[:HAS_GENRE]->(g:Genre)
            RETURN e.name AS cur_name, toString(e.start_at) AS cur_start_at,
                   e.timezone AS cur_timezone,
                   e.price_min AS cur_price_min, e.price_max AS cur_price_max,
                   e.price_currency AS cur_price_currency,
                   e.description AS cur_description,
                   e.ticket_url AS cur_ticket_url, e.status AS cur_status,
                   v.name_norm AS cur_venue_norm,
                   v.location.latitude AS cur_venue_lat,
                   v.location.longitude AS cur_venue_lng,
                   collect(DISTINCT g.slug) AS cur_genres
            """,
            uid=uid,
        ).single()
    except Exception as e:
        logger.error("Event load failed: %s", e)
        return UpdateResult(status="error", uid=uid, message=str(e))
    if current is None:
        return UpdateResult(status="not_found", uid=uid, message="No such event.")

    changed: dict[str, dict] = {}
    sets: list[str] = []
    params: dict = {"uid": uid}
    warnings: list[str] = []

    if "name" in fields:
        name = (fields["name"] or "").strip()
        if not name:
            return UpdateResult(
                status="invalid",
                uid=uid,
                message="An event needs a name — it cannot be cleared.",
            )
        if name != current["cur_name"]:
            changed["name"] = {"old": current["cur_name"], "new": name}
            sets.append("e.name = $name, e.name_norm = $name_norm")
            params["name"] = name
            params["name_norm"] = norm(name)

    if "start_at" in fields:
        raw = fields["start_at"] or ""
        parsed = parse_start_at(raw)
        if parsed is None:
            return UpdateResult(
                status="invalid",
                uid=uid,
                message=f"Could not parse start_at: {raw!r}",
            )
        timezone = resolve_timezone(current["cur_venue_lat"], current["cur_venue_lng"])
        if timezone is not None:
            if parsed.tzinfo is None:
                # An owner typing "22:00" means 22:00 at the door — the
                # venue's wall clock, the same rule write_event applies.
                parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
            else:
                parsed = parsed.astimezone(ZoneInfo(timezone))
        else:
            warnings.append(
                "Could not resolve the venue's timezone; the start time is stored as UTC."
            )
        if parsed.isoformat() != current["cur_start_at"]:
            changed["start_at"] = {
                "old": current["cur_start_at"],
                "new": parsed.isoformat(),
            }
            sets.append(
                "e.start_at = datetime($start_at), "
                "e.start_time_known = $start_time_known, e.timezone = $timezone"
            )
            params["start_at"] = parsed.isoformat()
            params["start_time_known"] = has_explicit_time(raw)
            params["timezone"] = timezone or ""

    scalars: dict[str, tuple[str, Callable]] = {
        "price_min": ("cur_price_min", lambda v: None if v is None else float(v)),
        "price_max": ("cur_price_max", lambda v: None if v is None else float(v)),
        "price_currency": ("cur_price_currency", lambda v: v or "EUR"),
        "description": ("cur_description", lambda v: v or ""),
        "ticket_url": ("cur_ticket_url", lambda v: v or ""),
    }
    for field, (cur_key, parse) in scalars.items():
        if field in fields:
            try:
                new = parse(fields[field])
            except (TypeError, ValueError):
                return UpdateResult(
                    status="invalid", uid=uid, message=f"Invalid value for {field}."
                )
            if new != current[cur_key]:
                changed[field] = {"old": current[cur_key], "new": new}
                sets.append(f"e.{field} = ${field}")
                params[field] = new

    if "status" in fields:
        status = fields["status"]
        if status not in ("scheduled", "cancelled"):
            return UpdateResult(
                status="invalid",
                uid=uid,
                message="status must be 'scheduled' or 'cancelled'.",
            )
        if status != current["cur_status"]:
            changed["status"] = {"old": current["cur_status"], "new": status}
            sets.append("e.status = $status")
            params["status"] = status

    new_genre = ""
    if "genre" in fields:
        new_genre = genre_slug(fields["genre"]) if fields["genre"] else ""
        old_genres = sorted(g for g in (current["cur_genres"] or []) if g)
        if ([new_genre] if new_genre else []) != old_genres:
            changed["genre"] = {"old": ", ".join(old_genres), "new": new_genre}

    # ── Dedup re-probe: a moved key must not land on another night ──────────
    if ("name" in changed or "start_at" in changed) and current["cur_venue_norm"]:
        try:
            clash = session.run(
                """
                MATCH (e:Event {name_norm: $name_norm})-[:HOSTED_AT]->(v:Venue {name_norm: $venue_norm})
                WHERE date(e.start_at) = date(datetime($start_at)) AND e.uid <> $uid
                RETURN e.uid AS uid, e.name AS name, e.owner_id AS owner_id LIMIT 1
                """,
                name_norm=params.get("name_norm") or norm(current["cur_name"]),
                venue_norm=current["cur_venue_norm"],
                start_at=params.get("start_at") or current["cur_start_at"],
                uid=uid,
            ).single()
        except Exception as e:
            logger.error("Edit dedup probe failed: %s", e)
            return UpdateResult(status="error", uid=uid, message=str(e))
        if clash:
            return UpdateResult(
                status="duplicate",
                uid=uid,
                message="An event with the same name, date, and venue already exists.",
            )

    if not changed:
        return UpdateResult(status="updated", uid=uid, message="Nothing changed.")

    try:
        if sets:
            record = session.run(
                f"MATCH (e:Event {{uid: $uid}}) "
                f"SET {', '.join(sets)}, e.updated_at = datetime() "
                "RETURN e.uid AS updated_uid",
                **params,
            ).single()
            if record is None:
                return UpdateResult(
                    status="not_found", uid=uid, message="No such event."
                )
        if "genre" in changed:
            session.run(
                """
                MATCH (e:Event {uid: $uid})
                OPTIONAL MATCH (e)-[r:HAS_GENRE]->(:Genre)
                DELETE r
                WITH DISTINCT e
                FOREACH (_ IN CASE WHEN $genre <> '' THEN [1] ELSE [] END |
                    MERGE (g:Genre {slug: $genre})
                    ON CREATE SET g.name = $genre_name
                    MERGE (e)-[:HAS_GENRE]->(g)
                )
                SET e.updated_at = datetime()
                """,
                uid=uid,
                genre=new_genre,
                genre_name=(fields.get("genre") or "").strip().title(),
            )
    except Exception as e:
        logger.error("Event update failed: %s", e)
        return UpdateResult(status="error", uid=uid, message=str(e))

    if _EVENT_TEXT_FIELDS & set(changed):
        warnings += _refresh_embedding(
            session, "Event", uid, embed_texts, embedding_model
        )
    return UpdateResult(
        status="updated",
        uid=uid,
        changed=changed,
        warnings=warnings,
        message="Event updated.",
    )


def update_venue(
    session,
    uid: str,
    fields: dict,
    *,
    geocoder: NominatimGeocoder | None = None,
    address_resolver: AddressResolver | None = None,
    embed_texts: EmbedFn | None = None,
    embedding_model: str = "",
) -> UpdateResult:
    """Edit a venue in place, PATCH-style.

    Editable: address, venue_type, description, capacity. This is the owner's
    door the write path defers to: write_event only ever *completes* an empty
    address, while changing a stated one happens here — and an address change
    re-geocodes and restamps the precision, under geocode_venue's own
    plausibility guard. A geocode miss keeps the old pin and says so rather
    than wiping a good coordinate. No rename: name_norm is the MERGE identity.
    """
    unknown = set(fields) - _VENUE_EDITABLE
    if unknown:
        return UpdateResult(
            status="invalid",
            uid=uid,
            message=f"These fields cannot be edited: {', '.join(sorted(unknown))}",
        )

    try:
        current = session.run(
            """
            MATCH (v:Venue {uid: $uid})
            OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)
            WITH v, c LIMIT 1
            RETURN v.name AS cur_name, v.venue_type AS cur_venue_type,
                   v.address AS cur_address, v.description AS cur_description,
                   v.capacity AS cur_capacity, c.name AS cur_city
            """,
            uid=uid,
        ).single()
    except Exception as e:
        logger.error("Venue load failed: %s", e)
        return UpdateResult(status="error", uid=uid, message=str(e))
    if current is None:
        return UpdateResult(status="not_found", uid=uid, message="No such venue.")

    changed: dict[str, dict] = {}
    sets: list[str] = []
    params: dict = {"uid": uid}
    warnings: list[str] = []

    scalars: dict[str, tuple[str, Callable]] = {
        "venue_type": ("cur_venue_type", lambda v: v or ""),
        "description": ("cur_description", lambda v: v or ""),
        "capacity": ("cur_capacity", lambda v: None if v is None else int(v)),
        "address": ("cur_address", lambda v: (v or "").strip()),
    }
    for field, (cur_key, parse) in scalars.items():
        if field in fields:
            try:
                new = parse(fields[field])
            except (TypeError, ValueError):
                return UpdateResult(
                    status="invalid", uid=uid, message=f"Invalid value for {field}."
                )
            if new != current[cur_key]:
                changed[field] = {"old": current[cur_key], "new": new}
                sets.append(f"v.{field} = ${field}")
                params[field] = new

    if "address" in changed and params.get("address") and geocoder is not None:
        city = current["cur_city"] or ""
        city_geo = geocoder.geocode(city) if city else None
        venue_geo = geocoder.geocode_venue(
            current["cur_name"],
            params["address"],
            city,
            near=city_geo,
            address_resolver=address_resolver,
        )
        if venue_geo is not None:
            changed["location"] = {
                "old": None,
                "new": {"lat": venue_geo.lat, "lng": venue_geo.lng},
            }
            sets.append(
                "v.location = point({latitude: $venue_lat, longitude: $venue_lng}), "
                "v.geocode_precision = $geocode_precision"
            )
            params["venue_lat"] = venue_geo.lat
            params["venue_lng"] = venue_geo.lng
            params["geocode_precision"] = "venue"
        else:
            warnings.append(
                "The new address could not be geocoded; the map pin is unchanged."
            )

    if not changed:
        return UpdateResult(status="updated", uid=uid, message="Nothing changed.")

    try:
        record = session.run(
            f"MATCH (v:Venue {{uid: $uid}}) "
            f"SET {', '.join(sets)}, v.updated_at = datetime() "
            "RETURN v.uid AS updated_uid",
            **params,
        ).single()
        if record is None:
            return UpdateResult(status="not_found", uid=uid, message="No such venue.")
    except Exception as e:
        logger.error("Venue update failed: %s", e)
        return UpdateResult(status="error", uid=uid, message=str(e))

    if _VENUE_TEXT_FIELDS & set(changed):
        warnings += _refresh_embedding(
            session, "Venue", uid, embed_texts, embedding_model
        )
    return UpdateResult(
        status="updated",
        uid=uid,
        changed=changed,
        warnings=warnings,
        message="Venue updated.",
    )


def update_artist(
    session,
    uid: str,
    fields: dict,
    *,
    embed_texts: EmbedFn | None = None,
    embedding_model: str = "",
) -> UpdateResult:
    """Edit an artist in place, PATCH-style.

    Editable: description, and genres — which REPLACE the artist's HAS_GENRE
    edges. That is deliberately stronger than tag_artist_genres (which only
    ever adds): this is the owner speaking about their own act, and their word
    replaces the machine's. No rename: name_norm is the MERGE identity.
    """
    unknown = set(fields) - _ARTIST_EDITABLE
    if unknown:
        return UpdateResult(
            status="invalid",
            uid=uid,
            message=f"These fields cannot be edited: {', '.join(sorted(unknown))}",
        )

    try:
        current = session.run(
            """
            MATCH (a:Artist {uid: $uid})
            OPTIONAL MATCH (a)-[:HAS_GENRE]->(g:Genre)
            RETURN a.name AS cur_name, a.description AS cur_description,
                   collect(DISTINCT g.slug) AS cur_genres
            """,
            uid=uid,
        ).single()
    except Exception as e:
        logger.error("Artist load failed: %s", e)
        return UpdateResult(status="error", uid=uid, message=str(e))
    if current is None:
        return UpdateResult(status="not_found", uid=uid, message="No such artist.")

    changed: dict[str, dict] = {}
    warnings: list[str] = []
    new_desc = None
    if "description" in fields:
        new_desc = fields["description"] or ""
        if new_desc != current["cur_description"]:
            changed["description"] = {
                "old": current["cur_description"],
                "new": new_desc,
            }

    genre_rows: list[dict] = []
    if "genres" in fields:
        seen: set[str] = set()
        for raw in fields["genres"] or []:
            slug = genre_slug(raw) if raw else ""
            if slug and slug not in seen:
                seen.add(slug)
                genre_rows.append({"slug": slug, "name": raw.strip().title()})
        old_genres = sorted(g for g in (current["cur_genres"] or []) if g)
        if sorted(seen) != old_genres:
            changed["genres"] = {"old": old_genres, "new": sorted(seen)}

    if not changed:
        return UpdateResult(status="updated", uid=uid, message="Nothing changed.")

    try:
        if "description" in changed:
            record = session.run(
                "MATCH (a:Artist {uid: $uid}) "
                "SET a.description = $description, a.updated_at = datetime() "
                "RETURN a.uid AS updated_uid",
                uid=uid,
                description=new_desc,
            ).single()
            if record is None:
                return UpdateResult(
                    status="not_found", uid=uid, message="No such artist."
                )
        if "genres" in changed:
            session.run(
                """
                MATCH (a:Artist {uid: $uid})
                OPTIONAL MATCH (a)-[r:HAS_GENRE]->(:Genre)
                DELETE r
                WITH DISTINCT a
                FOREACH (tag IN $genres |
                    MERGE (g:Genre {slug: tag.slug})
                    ON CREATE SET g.name = tag.name
                    MERGE (a)-[:HAS_GENRE]->(g)
                )
                SET a.updated_at = datetime()
                """,
                uid=uid,
                genres=genre_rows,
            )
    except Exception as e:
        logger.error("Artist update failed: %s", e)
        return UpdateResult(status="error", uid=uid, message=str(e))

    warnings += _refresh_embedding(session, "Artist", uid, embed_texts, embedding_model)
    return UpdateResult(
        status="updated",
        uid=uid,
        changed=changed,
        warnings=warnings,
        message="Artist updated.",
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
