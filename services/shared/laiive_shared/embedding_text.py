"""Composite embedding-text recipes (03-ontology §5).

One recipe per label, used by every writer (seed, pusher, search) so that
re-embedding after a model change is a pure batch job. The stored
`embedding_text` is always the output of these functions.
"""


def _join(parts: list[str | None]) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def event_text(
    name: str,
    artists: list[str] | None = None,
    venue: str | None = None,
    city: str | None = None,
    genres: list[str] | None = None,
    start_at: str | None = None,
    description: str | None = None,
) -> str:
    """Event = name + artists + venue + city + genres + date + description."""
    where = None
    if venue and city:
        where = (
            f"{', '.join(artists)} at {venue}, {city}."
            if artists
            else f"At {venue}, {city}."
        )
    elif venue:
        where = f"{', '.join(artists)} at {venue}." if artists else f"At {venue}."
    elif artists:
        where = f"{', '.join(artists)}."
    return _join(
        [
            f"{name}.",
            where,
            f"Genres: {', '.join(genres)}." if genres else None,
            f"{start_at[:10]}." if start_at else None,
            description,
        ]
    )


def artist_text(
    name: str,
    genres: list[str] | None = None,
    city: str | None = None,
    description: str | None = None,
) -> str:
    """Artist = name + genres + city + description."""
    if genres and city:
        blurb = f"{', '.join(genres)} artist from {city}."
    elif genres:
        blurb = f"{', '.join(genres)} artist."
    elif city:
        blurb = f"Artist from {city}."
    else:
        blurb = None
    return _join([f"{name}.", blurb, description])


def venue_text(
    name: str,
    venue_type: str | None = None,
    city: str | None = None,
    address: str | None = None,
    description: str | None = None,
) -> str:
    """Venue = name + type + city + address + description."""
    if venue_type and city:
        blurb = f"{venue_type} in {city}."
    elif venue_type:
        blurb = f"{venue_type}."
    elif city:
        blurb = f"In {city}."
    else:
        blurb = None
    return _join([f"{name}.", blurb, f"{address}." if address else None, description])
