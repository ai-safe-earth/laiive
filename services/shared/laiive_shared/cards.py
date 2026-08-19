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
    venue_type: str | None = None
    city: str | None = None
    start_at: str | None = None  # ISO 8601
    price_min: float | None = None
    price_max: float | None = None
    price_currency: str | None = None
    description: str | None = None
    ticket_url: str | None = None
    lat: float | None = None
    lng: float | None = None
    source: str = "pro_submission"  # pro_submission | admin_search | seed
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


def missing_required(draft: EventDraft, source: str = "pro_submission") -> list[str]:
    """Names of required fields that are still empty on this draft."""
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
    return missing
