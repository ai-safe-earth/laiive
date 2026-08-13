"""Legacy presentation helpers.

The current frontend renders a markdown stream and OpenAI-shaped SSE frames.
Both die with the Phase 4 frontend, which consumes the shared named-event
protocol and renders cards from `events.result` instead.
"""

import json
from datetime import datetime
from typing import Any

from laiive_shared import EventCard


def format_datetime(iso_datetime: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
        return dt.strftime("%a, %b %d, %Y at %I:%M %p")
    except (ValueError, AttributeError):
        return iso_datetime


def format_price(price_min: Any, price_max: Any, currency: str | None) -> str:
    try:
        p_min = float(price_min) if price_min is not None else None
    except (ValueError, TypeError):
        p_min = None
    try:
        p_max = float(price_max) if price_max is not None else None
    except (ValueError, TypeError):
        p_max = None

    currency = currency or "EUR"
    if p_min is None and p_max is None:
        return "Price TBA"
    if (p_min or 0) == 0 and (p_max is None or p_max == 0):
        return "Free"
    if p_min is not None and p_max is not None and p_min != p_max:
        return f"{p_min:.0f}–{p_max:.0f} {currency}"
    val = p_min if p_min is not None else p_max
    return "Free" if val == 0 else f"{val:.2f} {currency}"


def cards_to_markdown(cards: list[EventCard]) -> str:
    """EventCards → the markdown block the legacy frontend expects."""
    if not cards:
        return "No events found matching your criteria."

    parts = []
    for idx, card in enumerate(cards, 1):
        artist = card.artists[0] if card.artists else "Unknown Artist"
        venue = ", ".join(p for p in (card.venue, card.city) if p) or "Venue TBA"
        time_str = format_datetime(card.start_at) if card.start_at else "Date TBA"
        md = f"""
### {idx}. {card.name or f"{artist} Live"}

**Source:** {"Verified Source" if card.source != "internet" else "Internet Source"}

**Artist:** {artist}

**Venue:** {venue}

**Time:** {time_str}

**Price:** {format_price(card.price_min, card.price_max, card.price_currency)}
"""
        if card.description:
            truncated = card.description[:200]
            ellipsis = "..." if len(card.description) > 200 else ""
            md += f"\n**About:** {truncated}{ellipsis}\n"
        if card.ticket_url:
            md += f"\n[Get Tickets]({card.ticket_url})\n"
        md += "\n---\n"
        parts.append(md)
    return "\n".join(parts)


def create_sse_message(content: str) -> str:
    """Legacy OpenAI-shaped data-only frame."""
    payload = json.dumps(
        {"choices": [{"delta": {"content": content}}]}, ensure_ascii=False
    )
    return f"data: {payload}\n\n"


def create_sse_done() -> str:
    return "data: [DONE]\n\n"
