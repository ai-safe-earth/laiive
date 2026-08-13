"""
Tests for conversation session management and field extraction.
Run with: cd services/pusher && python -m pytest tests/test_conversation.py -v
"""

import pytest
from unittest.mock import patch, MagicMock


class TestSession:
    def test_session_creation(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-1")
        assert session.session_id == "test-1"
        assert not session.confirmed
        assert all(v is None for v in session.fields.values())

    def test_missing_required_fields(self, mock_openai):
        from agent.conversation import Session, REQUIRED_FIELDS

        session = Session("test-2")
        missing = session._missing_required()
        assert set(missing) == set(REQUIRED_FIELDS)

    def test_all_required_collected(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-3")
        session.fields["artist"] = "Test Artist"
        session.fields["date_time"] = "2026-04-01 21:00"
        session.fields["venue"] = "Test Venue"
        session.fields["city"] = "Berlin"
        session.fields["price"] = "15"
        assert session.all_required_collected()

    def test_not_all_required(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-4")
        session.fields["artist"] = "Test Artist"
        assert not session.all_required_collected()

    def test_extract_fields_from_text(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-5")
        extracted = session.extract_fields_from_text(
            "DJ Shadow at Berghain in Berlin on March 20 at 23:00 for 15 euros"
        )
        assert isinstance(extracted, dict)
        # The mock returns fixed fields
        assert session.fields["artist"] == "Test Artist"
        assert session.fields["city"] == "Berlin"

    def test_extract_fields_invalid_json(self, mock_openai):
        from agent.conversation import Session

        mock_openai.chat.completions.create.return_value.choices[
            0
        ].message.content = "not json"
        session = Session("test-6")
        extracted = session.extract_fields_from_text("random text")
        assert extracted == {}

    def test_extract_fields_strips_markdown_fences(self, mock_openai):
        from agent.conversation import Session

        mock_openai.chat.completions.create.return_value.choices[
            0
        ].message.content = '```json\n{"artist": "Fenced Artist"}\n```'
        session = Session("test-7")
        extracted = session.extract_fields_from_text("test")
        assert extracted.get("artist") == "Fenced Artist"
        assert session.fields["artist"] == "Fenced Artist"

    def test_chat_confirmation(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-8")
        # Fill all required fields
        session.fields["artist"] = "Test Artist"
        session.fields["date_time"] = "2026-04-01 21:00"
        session.fields["venue"] = "Test Venue"
        session.fields["city"] = "Berlin"
        session.fields["price"] = "15"

        reply = session.chat("yes")
        assert session.confirmed
        assert "CONFIRMED" in reply

    def test_chat_no_confirmation_without_fields(self, mock_openai):
        from agent.conversation import Session

        # Make extraction return empty (no fields found)
        mock_openai.chat.completions.create.return_value.choices[
            0
        ].message.content = "{}"
        session = Session("test-9")
        session.chat("yes")
        assert not session.confirmed

    def test_to_event_data(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-10")
        session.fields["artist"] = "Test Artist"
        session.fields["date_time"] = "2026-04-01 21:00"
        session.fields["venue"] = "Test Venue"
        session.fields["city"] = "Berlin"
        session.fields["price"] = "15"
        session.fields["description"] = "Great show"
        session.fields["genre"] = "electronic"

        data = session.to_event_data()
        assert data["artist"] == "Test Artist"
        assert data["venue"] == "Test Venue"
        assert data["city"] == "Berlin"
        assert data["price_amount"] == 15.0
        assert data["price_currency"] == "EUR"  # Berlin defaults to EUR
        assert data["genre"] == "electronic"

    def test_currency_detection(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-11")
        session.fields["city"] = "New York"
        assert session.get_currency() == "USD"

        session.fields["city"] = "London"
        assert session.get_currency() == "GBP"

        session.fields["city"] = "Tokyo"
        assert session.get_currency() == "JPY"

        session.fields["city"] = "Unknown City"
        assert session.get_currency() == "EUR"

    def test_price_parsing_free(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-12")
        session.fields.update(
            {
                "artist": "A",
                "date_time": "2026-01-01",
                "venue": "V",
                "city": "Berlin",
                "price": "free",
            }
        )
        data = session.to_event_data()
        assert data["price_amount"] == 0.0

    def test_price_parsing_comma_decimal(self, mock_openai):
        from agent.conversation import Session

        session = Session("test-13")
        session.fields.update(
            {
                "artist": "A",
                "date_time": "2026-01-01",
                "venue": "V",
                "city": "Berlin",
                "price": "12,50",
            }
        )
        data = session.to_event_data()
        assert data["price_amount"] == 12.5


class TestSessionStore:
    def test_get_or_create(self, mock_openai):
        from agent.conversation import SessionStore

        store = SessionStore()
        s1 = store.get_or_create("a")
        s2 = store.get_or_create("a")
        assert s1 is s2

    def test_different_sessions(self, mock_openai):
        from agent.conversation import SessionStore

        store = SessionStore()
        s1 = store.get_or_create("a")
        s2 = store.get_or_create("b")
        assert s1 is not s2

    def test_remove(self, mock_openai):
        from agent.conversation import SessionStore

        store = SessionStore()
        store.get_or_create("a")
        store.remove("a")
        # Getting again creates a new session
        s = store.get_or_create("a")
        assert not s.confirmed
        assert all(v is None for v in s.fields.values())

    def test_remove_nonexistent(self, mock_openai):
        from agent.conversation import SessionStore

        store = SessionStore()
        store.remove("nonexistent")  # Should not raise


class TestConverters:
    def test_audio_to_text(self, mock_openai):
        from agent.converters import audio_to_text

        text = audio_to_text(b"fake audio bytes", "test.webm")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_image_to_text(self, mock_openai):
        from agent.converters import image_to_text

        # Mock returns the extraction prompt response
        mock_openai.chat.completions.create.return_value.choices[
            0
        ].message.content = "DJ Shadow at Berghain"
        text = image_to_text(b"fake image bytes", "image/png")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_extract_fields_from_text(self, mock_openai):
        from agent.converters import extract_fields_from_text

        fields = extract_fields_from_text("DJ Shadow at Berghain in Berlin")
        assert isinstance(fields, dict)
        assert "artist" in fields

    def test_extract_from_url(self, mock_openai):
        from agent.converters import extract_from_url

        with patch("agent.converters.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.text = "<html>DJ Shadow at Berghain Berlin March 20</html>"
            mock_response.raise_for_status.return_value = None

            instance = MagicMock()
            instance.get.return_value = mock_response
            instance.__enter__ = lambda self: self
            instance.__exit__ = lambda self, *a: None
            mock_client.return_value = instance

            fields = extract_from_url("https://example.com/event")
            assert isinstance(fields, dict)

    def test_extract_from_url_failure(self, mock_openai):
        from agent.converters import extract_from_url

        with patch("agent.converters.httpx.Client") as mock_client:
            instance = MagicMock()
            instance.get.side_effect = Exception("Connection failed")
            instance.__enter__ = lambda self: self
            instance.__exit__ = lambda self, *a: None
            mock_client.return_value = instance

            with pytest.raises(ValueError, match="Could not fetch URL"):
                extract_from_url("https://bad-url.com")

    def test_document_to_text_txt(self, mock_openai):
        from agent.converters import document_to_text

        text = document_to_text(b"Some event text", "event.txt")
        assert text == "Some event text"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
