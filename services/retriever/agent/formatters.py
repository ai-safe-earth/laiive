"""
Formatters for converting database results to frontend-compatible formats.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime


def format_event_for_frontend(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Format a Neo4j event result into the structure expected by the frontend.

    Frontend expects:
    {
        artist: string,
        tagline: string,
        venue: string,
        time: string,
        price: string,
        description?: string,
        ticketUrl?: string
    }
    """
    # Extract event properties
    event_props = event.get("event", {})
    if isinstance(event_props, dict):
        event_name = event_props.get("name", "")
        event_desc = event_props.get("description", "")
        start_at = event_props.get("start_at", "")
        price_amount = event_props.get("price_amount")
        price_currency = event_props.get("price_currency", "EUR")
        ticket_url = event_props.get("ticket_url") or event_props.get("url")
    else:
        # Flat structure
        event_name = event.get("name", "")
        event_desc = event.get("description", "")
        start_at = event.get("start_at", "")
        price_amount = event.get("price_amount")
        price_currency = event.get("price_currency", "EUR")
        ticket_url = event.get("ticket_url") or event.get("url")

    # Extract artist information
    artist_data = event.get("artist", {}) or event.get("artists", [])
    if isinstance(artist_data, list) and artist_data:
        artist_data = artist_data[0]

    if isinstance(artist_data, dict):
        artist_name = artist_data.get("name", "Unknown Artist")
    elif isinstance(artist_data, str):
        artist_name = artist_data
    else:
        artist_name = "Unknown Artist"

    # Extract venue information
    venue_data = event.get("venue", {})
    if isinstance(venue_data, dict):
        venue_name = venue_data.get("name", "")
        venue_city = venue_data.get("city", "")
        venue_address = venue_data.get("address", "")

        # Format venue string
        venue_parts = [venue_name]
        if venue_address:
            venue_parts.append(venue_address)
        if venue_city:
            venue_parts.append(venue_city)
        venue_str = ", ".join(filter(None, venue_parts))
    else:
        venue_str = str(venue_data) if venue_data else "Venue TBA"

    # Format time
    time_str = format_datetime(start_at) if start_at else "Date TBA"

    # Format price
    if price_amount is not None:
        try:
            price_val = float(price_amount)
            if price_val == 0:
                price_str = "Free"
            else:
                price_str = f"{price_val:.2f} {price_currency}"
        except (ValueError, TypeError):
            price_str = "Price TBA"
    else:
        price_str = "Price TBA"

    return {
        "artist": artist_name,
        "tagline": event_name or f"{artist_name} Live",
        "venue": venue_str,
        "time": time_str,
        "price": price_str,
        "description": event_desc or "",
        "ticketUrl": ticket_url or ""
    }


def format_datetime(iso_datetime: str) -> str:
    """
    Format ISO datetime string to a user-friendly format.

    Example: "2026-01-15T20:00:00Z" -> "Wed, Jan 15, 2026 at 8:00 PM"
    """
    try:
        dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))
        return dt.strftime("%a, %b %d, %Y at %I:%M %p")
    except (ValueError, AttributeError):
        return iso_datetime


def format_events_as_markdown(events: List[Dict[str, Any]]) -> str:
    """
    Format events as markdown that can be parsed by the frontend.

    The frontend looks for patterns like:
    - **Artist:** artist name
    - **Event:** event name
    - **Venue:** venue details
    - **Time:** formatted time
    - **Price:** price info
    - **[Get Tickets](url)**
    """
    if not events:
        return "No events found matching your criteria."

    markdown_parts = []

    for idx, event in enumerate(events, 1):
        formatted = format_event_for_frontend(event)

        event_md = f"""
### {idx}. {formatted['tagline']}

**Artist:** {formatted['artist']}

**Venue:** {formatted['venue']}

**Time:** {formatted['time']}

**Price:** {formatted['price']}
"""

        if formatted.get('description'):
            event_md += f"\n**About:** {formatted['description'][:200]}{'...' if len(formatted['description']) > 200 else ''}\n"

        if formatted.get('ticketUrl'):
            event_md += f"\n[Get Tickets]({formatted['ticketUrl']})\n"

        event_md += "\n---\n"
        markdown_parts.append(event_md)

    return "\n".join(markdown_parts)


def format_events_as_json(events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Format events as a list of frontend-compatible event objects.
    """
    return [format_event_for_frontend(event) for event in events]


def create_sse_message(content: str) -> str:
    """
    Format content as a Server-Sent Event message compatible with OpenAI's streaming format.

    Returns a string like: 'data: {"choices":[{"delta":{"content":"text"}}]}\n\n'
    """
    import json
    message = {
        "choices": [
            {
                "delta": {
                    "content": content
                }
            }
        ]
    }
    return f"data: {json.dumps(message)}\n\n"


def create_sse_done() -> str:
    """
    Create the final SSE done message.
    """
    return "data: [DONE]\n\n"
