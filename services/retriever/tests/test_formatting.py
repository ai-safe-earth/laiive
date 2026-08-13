"""Legacy formatter tests — markdown block + OpenAI-shaped frames."""

import json

from laiive_shared import EventCard

from agent.utils.formatters import (
    cards_to_markdown,
    create_sse_done,
    create_sse_message,
    format_price,
)

CARD = EventCard(
    uid="e1",
    name="Klangfeld Nacht",
    artists=["Klangfeld", "DJ Petra"],
    venue="Berghain",
    city="Berlin",
    start_at="2026-08-15T23:00:00+00:00",
    price_min=20.0,
    price_max=20.0,
    price_currency="EUR",
    description="Marathon techno night.",
    ticket_url="https://tickets.example/1",
    source="seed",
)


def test_markdown_contains_the_essentials():
    md = cards_to_markdown([CARD])
    assert "### 1. Klangfeld Nacht" in md
    assert "**Artist:** Klangfeld" in md
    assert "Berghain, Berlin" in md
    assert "20.00 EUR" in md
    assert "[Get Tickets](https://tickets.example/1)" in md
    assert "Verified Source" in md


def test_markdown_empty_list():
    assert "No events found" in cards_to_markdown([])


def test_markdown_handles_missing_fields():
    bare = EventCard(uid="e2", name="", artists=[], source="seed")
    md = cards_to_markdown([bare])
    assert "Unknown Artist" in md
    assert "Venue TBA" in md
    assert "Date TBA" in md
    assert "Price TBA" in md


def test_price_formatting():
    assert format_price(None, None, "EUR") == "Price TBA"
    assert format_price(0, 0, "EUR") == "Free"
    assert format_price(0, None, "EUR") == "Free"
    assert format_price(15, 20, "EUR") == "15–20 EUR"
    assert format_price(15, 15, "EUR") == "15.00 EUR"
    assert format_price("abc", None, "EUR") == "Price TBA"


def test_legacy_sse_frames():
    frame = create_sse_message("hola")
    assert frame.startswith("data: ")
    payload = json.loads(frame[len("data: ") :].strip())
    assert payload["choices"][0]["delta"]["content"] == "hola"
    assert create_sse_done() == "data: [DONE]\n\n"
