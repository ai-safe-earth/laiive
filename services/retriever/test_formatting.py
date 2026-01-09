"""
Test script to verify event formatting for frontend compatibility.
Run with: python test_formatting.py
"""
from agent.formatters import (
    format_event_for_frontend,
    format_events_as_markdown,
    format_events_as_json,
    create_sse_message,
    create_sse_done
)


def test_event_formatting():
    """Test event data formatting."""
    print("\n" + "="*60)
    print("Testing Event Formatting for Frontend")
    print("="*60 + "\n")

    # Sample Neo4j event result
    sample_event = {
        "event": {
            "id": "evt-123",
            "name": "Jazz Night at Blue Note",
            "description": "An evening of smooth jazz featuring local and international artists. Experience the magic of live jazz in an intimate setting.",
            "start_at": "2026-01-15T20:00:00Z",
            "price_amount": 25.50,
            "price_currency": "EUR",
            "ticket_url": "https://tickets.example.com/jazz-night"
        },
        "artist": {
            "name": "John Coltrane Quartet",
            "genre": "Jazz"
        },
        "venue": {
            "name": "Blue Note Berlin",
            "city": "Berlin",
            "address": "Friedrichstraße 123"
        }
    }

    print("1. SAMPLE NEO4J EVENT DATA:")
    print("-" * 60)
    import json
    print(json.dumps(sample_event, indent=2))

    # Test single event formatting
    formatted = format_event_for_frontend(sample_event)

    print("\n2. FRONTEND-COMPATIBLE FORMAT:")
    print("-" * 60)
    print(json.dumps(formatted, indent=2))

    # Test markdown formatting
    markdown = format_events_as_markdown([sample_event])

    print("\n3. MARKDOWN FORMAT (for chat display):")
    print("-" * 60)
    print(markdown)

    # Test SSE message formatting
    print("\n4. SSE MESSAGE FORMAT:")
    print("-" * 60)
    sse_msg = create_sse_message("Hello from the API!")
    print(repr(sse_msg))
    print("\nRendered:")
    print(sse_msg)

    print("SSE DONE signal:")
    print(repr(create_sse_done()))


def test_multiple_events():
    """Test formatting multiple events."""
    print("\n" + "="*60)
    print("Testing Multiple Events Formatting")
    print("="*60 + "\n")

    events = [
        {
            "event": {"name": "Rock Night", "start_at": "2026-01-16T21:00:00Z", "price_amount": 30.0, "price_currency": "EUR"},
            "artist": {"name": "The Rolling Stones Tribute"},
            "venue": {"name": "Rock Arena", "city": "Berlin"}
        },
        {
            "event": {"name": "Classical Evening", "start_at": "2026-01-17T19:00:00Z", "price_amount": 0, "price_currency": "EUR"},
            "artist": {"name": "Berlin Philharmonic"},
            "venue": {"name": "Concert Hall", "city": "Berlin", "address": "Unter den Linden 1"}
        },
        {
            "event": {"name": "Electronic Beats", "start_at": "2026-01-18T23:00:00Z", "price_amount": None, "price_currency": "EUR"},
            "artist": {"name": "DJ Shadow"},
            "venue": {"name": "Club Matrix", "city": "Berlin"}
        }
    ]

    markdown = format_events_as_markdown(events)
    print(markdown)


def test_edge_cases():
    """Test edge cases and missing data."""
    print("\n" + "="*60)
    print("Testing Edge Cases")
    print("="*60 + "\n")

    # Missing fields
    minimal_event = {
        "event": {"name": "Mystery Concert"},
    }

    print("Event with minimal data:")
    formatted = format_event_for_frontend(minimal_event)
    import json
    print(json.dumps(formatted, indent=2))

    print("\nMarkdown for minimal event:")
    print(format_events_as_markdown([minimal_event]))

    # Flat structure (no nested dicts)
    flat_event = {
        "name": "Flat Event",
        "description": "Test description",
        "start_at": "2026-02-01T18:00:00Z",
        "price_amount": 15.0,
        "artist": "Solo Artist"
    }

    print("\n" + "-"*60)
    print("Flat structure event:")
    formatted = format_event_for_frontend(flat_event)
    print(json.dumps(formatted, indent=2))


def main():
    """Run all tests."""
    try:
        test_event_formatting()
        test_multiple_events()
        test_edge_cases()

        print("\n" + "="*60)
        print("[SUCCESS] All formatting tests completed successfully!")
        print("="*60 + "\n")
        return 0
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
