"""EventCard (retriever → frontend) and EventDraft (pusher form) shapes.

Mirrored in ts/protocol.ts — tests/test_ts_contract.py fails on drift.
"""

from pydantic import BaseModel


class EventCard(BaseModel):
    """The card contract — one shape, typed on both sides (02-architecture §2)."""

    uid: str
    name: str
    artists: list[str] = []
    venue: str | None = None
    # The venue's graph identity and address. A card that can only name its
    # venue by display string cannot be used to claim or edit it -- the uid is
    # what the ownership screens reference. None on rows read by paths that do
    # not select them.
    venue_uid: str | None = None
    venue_address: str | None = None
    venue_type: str | None = None
    city: str | None = None
    start_at: str | None = None  # ISO 8601
    # IANA zone of the venue, so the card can print the time at the door rather
    # than on the reader's clock. Empty or None is a row written before the
    # writer resolved zones, whose start_at is UTC by default.
    timezone: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    price_currency: str | None = None
    description: str | None = None
    ticket_url: str | None = None
    lat: float | None = None
    lng: float | None = None
    source: str = "pro_submission"  # pro_submission | admin_search | seed
    # The page a discovered event was read off, and its host. Empty or None on
    # a promoter submission (nobody searched for it) and on rows written before
    # the writer carried it. The card names the source rather than only
    # claiming there was one.
    source_url: str | None = None
    source_domain: str | None = None
    distance_km: float | None = None
    # False when the listing gave a date and no time, so start_at's 00:00 is a
    # default rather than a claim. None is a row written before the flag.
    start_time_known: bool | None = None
    # How much the lat/lng above is worth: 'venue' is the venue itself,
    # 'city_centroid' only means "somewhere in this city". None is a row written
    # before the flag existed. A pin the repair sweep flagged as 'suspect' never
    # reaches a card at all -- its coordinates are dropped, since a known-wrong
    # pin drawn on a map is a confident lie. See laiive_shared.geocode.
    geocode_precision: str | None = None
    # True once an organization's claim on this event was verified by an admin
    # (the claim stamp on the graph node). The card treats it as vouched, the
    # same trust a promoter's own submission gets. False until then --
    # including while a claim is merely pending.
    claimed: bool = False


class VenueHit(BaseModel):
    """One venue in a lookup answer — enough to pick it and prefill a form."""

    uid: str
    name: str
    venue_type: str | None = None
    address: str | None = None
    city: str | None = None


class VenueLookupResult(BaseModel):
    venues: list[VenueHit] = []


class ArtistHit(BaseModel):
    uid: str
    name: str
    genres: list[str] = []


class ArtistLookupResult(BaseModel):
    artists: list[ArtistHit] = []


class EventDraft(BaseModel):
    """A (possibly partial) event as extracted by the pusher, pre-publication."""

    name: str | None = None
    artists: list[str] = []
    start_at: str | None = None  # ISO 8601 or raw user text, parsed on write
    venue: str | None = None
    venue_type: str | None = None
    address: str | None = None
    city: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    price_currency: str | None = None
    description: str | None = None
    genre: str | None = None
    ticket_url: str | None = None


# Fields a draft must have before it can be written to the graph.
# name is derived from artists when absent; price 0 means free, so price_min
# counts as present when it is not None. address is required because a venue
# name alone geocodes badly -- the promoter knows the street, and asking costs
# one conversational turn against a permanently wrong pin.
REQUIRED_DRAFT_FIELDS = (
    "artists",
    "start_at",
    "venue",
    "address",
    "city",
    "price_min",
)

# Internet listings rarely state the lineup or the price, so discovery only
# demands what a consumer card cannot do without — and a name, since there
# are no artists to derive one from.
ADMIN_SEARCH_REQUIRED_FIELDS = ("name", "start_at", "venue", "city")

# What a resolved venue node supplies on its own: the fields missing_required
# waives when the caller passes venue_known. Declared beside the required
# tuples it filters, so a rename there is visibly a rename here.
VENUE_SUPPLIED_FIELDS = ("venue", "address", "city")


def missing_required(
    draft: EventDraft,
    source: str = "pro_submission",
    *,
    venue_known: bool = False,
) -> list[str]:
    """Names of required fields that are still empty on this draft.

    ``venue_known`` means the caller resolved an existing graph venue by uid:
    the node brings its own name, address and city, so those are not the
    promoter's to re-type. The writer still refuses the write when the picked
    venue itself has no address on file and the draft offers none.
    """
    required = (
        ADMIN_SEARCH_REQUIRED_FIELDS
        if source == "admin_search"
        else REQUIRED_DRAFT_FIELDS
    )
    missing: list[str] = []
    for field in required:
        value = getattr(draft, field)
        if value is None or value == [] or value == "":
            missing.append(field)
    if venue_known:
        missing = [f for f in missing if f not in VENUE_SUPPLIED_FIELDS]
    return missing
