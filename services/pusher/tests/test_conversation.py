"""Conversation + converters unit tests (all OpenAI calls mocked)."""

import json

from agent.conversation import (
    clarification_rounds,
    default_currency,
    process_turn,
)
from agent.converters import (
    audio_to_text,
    document_to_text,
    extract_draft_from_text,
    image_to_text,
)


def set_extraction(mock_openai, payload: dict | str):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    mock_openai.chat.completions.create.return_value.choices[
        0
    ].message.content = content


COMPLETE = {
    "artists": ["Test Artist"],
    "start_at": "2026-04-01T21:00:00",
    "venue": "Test Venue",
    "city": "Berlin",
    "price_min": 15,
}


class TestExtraction:
    def test_extracts_complete_draft(self, mock_openai):
        draft = extract_draft_from_text(
            "Test Artist, April 1st, Test Venue, Berlin, 15€"
        )
        assert draft.artists == ["Test Artist"]
        assert draft.venue == "Test Venue"
        assert draft.price_min == 15.0

    def test_invalid_json_gives_empty_draft(self, mock_openai):
        set_extraction(mock_openai, "not json")
        draft = extract_draft_from_text("gibberish")
        assert draft.model_dump(exclude_none=True, exclude_defaults=True) == {}

    def test_markdown_fences_stripped(self, mock_openai):
        set_extraction(mock_openai, "```json\n" + json.dumps(COMPLETE) + "\n```")
        draft = extract_draft_from_text("whatever")
        assert draft.venue == "Test Venue"

    def test_string_artist_becomes_list(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "artists": "Solo Act"})
        assert extract_draft_from_text("x").artists == ["Solo Act"]

    def test_free_price_is_zero_not_missing(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "price_min": "free"})
        draft = extract_draft_from_text("free show")
        assert draft.price_min == 0.0

    def test_unknown_fields_ignored(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "hacker_field": "boom"})
        draft = extract_draft_from_text("x")
        assert draft.venue == "Test Venue"


class TestProcessTurn:
    def test_complete_first_message_goes_straight_to_form(self, mock_openai):
        turn = process_turn([{"role": "user", "content": "full event info"}])
        assert turn.show_form is True
        assert turn.missing == []
        assert turn.draft.price_currency == "EUR"  # defaulted from Berlin

    def test_incomplete_first_message_asks_once(self, mock_openai):
        set_extraction(mock_openai, {"artists": ["X"], "city": "Berlin"})
        turn = process_turn([{"role": "user", "content": "gig by X in Berlin"}])
        assert turn.show_form is False
        assert set(turn.missing) == {"start_at", "venue", "price_min"}

    def test_second_round_always_shows_form_even_if_incomplete(self, mock_openai):
        set_extraction(mock_openai, {"artists": ["X"], "city": "Berlin"})
        turn = process_turn(
            [
                {"role": "user", "content": "gig by X in Berlin"},
                {"role": "assistant", "content": "when and where exactly?"},
                {"role": "user", "content": "not sure yet"},
            ]
        )
        assert turn.show_form is True  # ONE clarification round, then the form
        assert turn.missing  # still-missing fields travel with it

    def test_legacy_mode_keeps_asking(self, mock_openai):
        set_extraction(mock_openai, {"artists": ["X"], "city": "Berlin"})
        turn = process_turn(
            [
                {"role": "user", "content": "gig by X"},
                {"role": "assistant", "content": "when?"},
                {"role": "user", "content": "hmm"},
            ],
            one_round_rule=False,
        )
        assert turn.show_form is False

    def test_clarification_rounds_counted_from_history(self):
        assert clarification_rounds(None) == 0
        assert clarification_rounds([{"role": "user", "content": "x"}]) == 0
        assert (
            clarification_rounds(
                [
                    {"role": "user", "content": "x"},
                    {"role": "assistant", "content": "when?"},
                ]
            )
            == 1
        )

    def test_no_confirmed_marker_anywhere(self, mock_openai):
        """The 'type yes'/**CONFIRMED** write path is gone."""
        import agent.api as api
        import agent.conversation as conversation

        for module in (conversation, api):
            source = open(module.__file__, encoding="utf-8").read()
            assert "CONFIRMED" not in source


class TestCurrency:
    def test_known_cities(self):
        assert default_currency("London") == "GBP"
        assert default_currency("new york") == "USD"

    def test_default_eur(self):
        assert default_currency("Berlin") == "EUR"
        assert default_currency(None) == "EUR"


class TestConverters:
    def test_audio_to_text(self, mock_openai):
        assert "Test Artist" in audio_to_text(b"fake-audio")

    def test_image_to_text(self, mock_openai):
        set_extraction(mock_openai, "Concert poster: Test Artist at Test Venue")
        assert "Test Artist" in image_to_text(b"fake-image")

    def test_document_to_text_txt(self, mock_openai):
        assert document_to_text(b"plain text here", "notes.txt") == "plain text here"
