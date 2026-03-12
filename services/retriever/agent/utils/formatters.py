from typing import List, Dict, Any, Optional
from datetime import datetime


def format_event_for_frontend(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Format a Neo4j event result into the structure expected by the frontend.
    Internet-sourced events (source="internet") are already in the target format.
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

    event_props = event.get("event", {})
    if isinstance(event_props, dict):
        event_name = event_props.get("name", "")
        event_desc = event_props.get("description", "")
        start_at = event_props.get("start_at", "")
        price_amount = event_props.get("price_amount")
        price_currency = event_props.get("price_currency", "EUR")
        ticket_url = event_props.get("ticket_url") or event_props.get("url")
    else:
        event_name = event.get("name", "")
        event_desc = event.get("description", "")
        start_at = event.get("start_at", "")
        price_amount = event.get("price_amount")
        price_currency = event.get("price_currency", "EUR")
        ticket_url = event.get("ticket_url") or event.get("url")

    artist_data = event.get("artist", {}) or event.get("artists", [])
    if isinstance(artist_data, list) and artist_data:
        artist_data = artist_data[0]

    if isinstance(artist_data, dict):
        artist_name = artist_data.get("name", "Unknown Artist")
    elif isinstance(artist_data, str):
        artist_name = artist_data
    else:
        artist_name = "Unknown Artist"

    venue_data = event.get("venue", {})
    if isinstance(venue_data, dict):
        venue_name = venue_data.get("name", "")
        venue_city = venue_data.get("city", "")
        venue_address = venue_data.get("address", "")

        venue_parts = [venue_name]
        if venue_address:
            venue_parts.append(venue_address)
        if venue_city:
            venue_parts.append(venue_city)
        venue_str = ", ".join(filter(None, venue_parts))
    else:
        venue_str = str(venue_data) if venue_data else "Venue TBA"

    time_str = format_datetime(start_at) if start_at else "Date TBA"

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
            "Verified Source" if formatted.get("source") == "verified"
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
