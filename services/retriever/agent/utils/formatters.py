from typing import List, Dict, Any
from datetime import datetime


def _get(event: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first non-None value found for the given keys."""
    for key in keys:
        val = event.get(key)
        if val is not None:
            return val
    return default


def format_event_for_frontend(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Format a Neo4j event result into the structure expected by the frontend.

    Handles three shapes:
    1. Internet-sourced events — already in the target format.
    2. Flat LLM-generated Cypher results (e.g. event_name, venue_name, city_name, artists, ...).
    3. Nested dicts (e.g. {"event": {...}, "artist": {...}, "venue": {...}}).
    """

    # Internet search results arrive pre-formatted — pass through
    if event.get("source") == "internet" and "tagline" in event:
        return {
            "artist": event.get("artist", "Unknown Artist"),
            "tagline": event.get("tagline", ""),
            "venue": event.get("venue", "Venue TBA"),
            "time": event.get("time", "Date TBA"),
            "price": event.get("price", "Price TBA"),
            "description": event.get("description", ""),
            "ticketUrl": event.get("ticketUrl", ""),
            "source": "internet",
        }

    # --- Extract event properties (flat or nested) ---
    event_props = event.get("event", {})
    if isinstance(event_props, dict) and event_props:
        event_name = event_props.get("name", "")
        event_desc = event_props.get("description", "")
        start_at = event_props.get("start_at", "")
        price_min = event_props.get("price_min") or event_props.get("price_amount")
        price_max = event_props.get("price_max")
        price_currency = event_props.get("price_currency", "EUR")
        ticket_url = event_props.get("ticket_url") or event_props.get("url")
    else:
        # Flat keys from LLM-generated Cypher — aliases vary (e.name, event.name, event_name, name)
        event_name = _get(
            event, "event_name", "e.name", "event.name", "name", default=""
        )
        event_desc = _get(
            event, "description", "e.description", "event.description", default=""
        )
        start_at = _get(event, "start_at", "e.start_at", "event.start_at", default="")
        price_min = _get(
            event,
            "price_min",
            "e.price_min",
            "event.price_min",
            "price_amount",
            "e.price_amount",
            "event.price_amount",
        )
        price_max = _get(event, "price_max", "e.price_max", "event.price_max")
        price_currency = _get(
            event,
            "price_currency",
            "e.price_currency",
            "event.price_currency",
            default="EUR",
        )
        ticket_url = _get(
            event, "ticket_url", "e.ticket_url", "event.ticket_url", "url"
        )

    # --- Artist ---
    artist_data = _get(event, "artists", "artist", "a.name")
    if isinstance(artist_data, list) and artist_data:
        artist_name = (
            artist_data[0]
            if isinstance(artist_data[0], str)
            else artist_data[0].get("name", "Unknown Artist")
        )
    elif isinstance(artist_data, dict):
        artist_name = artist_data.get("name", "Unknown Artist")
    elif isinstance(artist_data, str):
        artist_name = artist_data
    else:
        artist_name = "Unknown Artist"

    # --- Venue ---
    venue_data = _get(event, "venue", "venue_name", "v.name", "venue.name")
    city_data = _get(event, "city_name", "city", "c.name", "city.name", default="")
    if isinstance(venue_data, dict):
        venue_name = venue_data.get("name", "")
        venue_city = venue_data.get("city", "") or city_data
        venue_address = venue_data.get("address", "")
        venue_parts = [venue_name]
        if venue_address:
            venue_parts.append(venue_address)
        if venue_city:
            venue_parts.append(venue_city)
        venue_str = ", ".join(filter(None, venue_parts))
    elif isinstance(venue_data, str) and venue_data:
        venue_str = f"{venue_data}, {city_data}" if city_data else venue_data
    else:
        venue_str = city_data or "Venue TBA"

    # --- Time ---
    time_str = format_datetime(str(start_at)) if start_at else "Date TBA"

    # --- Price ---
    price_str = _format_price(price_min, price_max, price_currency)

    source = event.get("source", "verified")

    return {
        "artist": artist_name,
        "tagline": event_name or f"{artist_name} Live",
        "venue": venue_str,
        "time": time_str,
        "price": price_str,
        "description": event_desc or "",
        "ticketUrl": ticket_url or "",
        "source": source,
    }


def _format_price(price_min: Any, price_max: Any, currency: str) -> str:
    """Format price range into a display string."""
    try:
        p_min = float(price_min) if price_min is not None else None
    except (ValueError, TypeError):
        p_min = None
    try:
        p_max = float(price_max) if price_max is not None else None
    except (ValueError, TypeError):
        p_max = None

    if p_min is None and p_max is None:
        return "Price TBA"
    if p_min == 0 and (p_max is None or p_max == 0):
        return "Free"
    if p_min is not None and p_max is not None and p_min != p_max:
        return f"{p_min:.0f}–{p_max:.0f} {currency}"
    val = p_min if p_min is not None else p_max
    if val == 0:
        return "Free"
    return f"{val:.2f} {currency}"


def format_datetime(iso_datetime: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
        return dt.strftime("%a, %b %d, %Y at %I:%M %p")
    except (ValueError, AttributeError):
        return iso_datetime


def format_events_as_markdown(events: List[Dict[str, Any]]) -> str:
    if not events:
        return "No events found matching your criteria."

    markdown_parts = []

    for idx, event in enumerate(events, 1):
        formatted = format_event_for_frontend(event)

        source_label = (
            "Verified Source"
            if formatted.get("source") == "verified"
            else "Internet Source"
        )

        event_md = f"""
### {idx}. {formatted['tagline']}

**Source:** {source_label}

**Artist:** {formatted['artist']}

**Venue:** {formatted['venue']}

**Time:** {formatted['time']}

**Price:** {formatted['price']}
"""

        if formatted.get("description"):
            event_md += f"\n**About:** {formatted['description'][:200]}{'...' if len(formatted['description']) > 200 else ''}\n"

        if formatted.get("ticketUrl"):
            event_md += f"\n[Get Tickets]({formatted['ticketUrl']})\n"

        event_md += "\n---\n"
        markdown_parts.append(event_md)

    return "\n".join(markdown_parts)


def format_events_as_json(events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [format_event_for_frontend(event) for event in events]


def create_sse_message(content: str) -> str:
    import json

    message = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(message)}\n\n"


def create_sse_done() -> str:
    return "data: [DONE]\n\n"
