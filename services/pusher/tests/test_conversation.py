"""Conversation + converters unit tests (all OpenAI calls mocked)."""

import json

from agent.conversation import (
    MAX_EVENTS_PER_TURN,
    _gaps,
    clarification_rounds,
    default_currency,
    process_turn,
)
from agent.converters import (
    audio_to_text,
    document_to_text,
    extract_draft_from_text,
    extract_drafts_from_text,
    image_to_text,
)


def set_extraction(mock_openai, payload: dict | list | str):
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


class TestMultiEventExtraction:
    """A spreadsheet or a line-up is the same extraction, longer."""

    def test_events_wrapper_keeps_order(self, mock_openai):
        set_extraction(
            mock_openai,
            {"events": [COMPLETE, {**COMPLETE, "venue": "Second Venue"}]},
        )
        drafts = extract_drafts_from_text("two gigs")
        assert [d.venue for d in drafts] == ["Test Venue", "Second Venue"]

    def test_bare_object_is_a_list_of_one(self, mock_openai):
        # conftest's canned response is a single unwrapped event
        assert len(extract_drafts_from_text("one gig")) == 1

    def test_bare_list_accepted(self, mock_openai):
        set_extraction(mock_openai, [COMPLETE, COMPLETE])
        assert len(extract_drafts_from_text("x")) == 2

    def test_unusable_entry_dropped_not_fatal(self, mock_openai):
        set_extraction(mock_openai, {"events": [{"artists": {"bad": 1}}, COMPLETE]})
        drafts = extract_drafts_from_text("x")
        assert [d.venue for d in drafts] == ["Test Venue"]

    def test_unparseable_response_gives_no_drafts(self, mock_openai):
        set_extraction(mock_openai, "not json")
        assert extract_drafts_from_text("gibberish") == []


class TestProcessTurn:
    def test_complete_first_message_goes_straight_to_form(self, mock_openai):
        turn = process_turn([{"role": "user", "content": "full event info"}])
        assert turn.show_form is True
        assert turn.missing == [[]]
        assert turn.draft.price_currency == "EUR"  # defaulted from Berlin

    def test_incomplete_first_message_asks_once(self, mock_openai):
        set_extraction(mock_openai, {"artists": ["X"], "city": "Berlin"})
        turn = process_turn([{"role": "user", "content": "gig by X in Berlin"}])
        assert turn.show_form is False
        assert set(turn.draft_missing) == {"start_at", "venue", "price_min"}

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
        assert any(turn.missing)  # still-missing fields travel with it

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


class TestManyEventsInOneTurn:
    TWO = {"events": [COMPLETE, {"artists": ["Y"], "city": "Berlin"}]}

    def test_one_clarification_round_covers_the_whole_set(self, mock_openai):
        set_extraction(mock_openai, self.TWO)
        turn = process_turn([{"role": "user", "content": "two gigs"}])
        assert len(turn.drafts) == 2
        assert turn.show_form is False  # one event incomplete → still one round
        assert turn.missing[0] == []
        assert set(turn.missing[1]) == {"start_at", "venue", "price_min"}

    def test_after_the_round_every_event_gets_its_form(self, mock_openai):
        set_extraction(mock_openai, self.TWO)
        turn = process_turn(
            [
                {"role": "user", "content": "two gigs"},
                {"role": "assistant", "content": "when is the second one?"},
                {"role": "user", "content": "not sure yet"},
            ]
        )
        assert turn.show_form is True
        assert len(turn.drafts) == len(turn.missing) == 2

    def test_currency_defaulted_per_event(self, mock_openai):
        set_extraction(
            mock_openai,
            {"events": [COMPLETE, {**COMPLETE, "city": "London"}]},
        )
        turn = process_turn([{"role": "user", "content": "two gigs"}])
        assert [d.price_currency for d in turn.drafts] == ["EUR", "GBP"]

    def test_beyond_the_cap_is_truncated_and_flagged(self, mock_openai):
        set_extraction(mock_openai, {"events": [COMPLETE] * (MAX_EVENTS_PER_TURN + 3)})
        turn = process_turn([{"role": "user", "content": "a whole season"}])
        assert len(turn.drafts) == MAX_EVENTS_PER_TURN
        assert turn.truncated is True

    def test_nothing_extracted_still_makes_one_draft(self, mock_openai):
        set_extraction(mock_openai, "not json")
        turn = process_turn([{"role": "user", "content": "hello?"}])
        assert len(turn.drafts) == 1
        assert turn.show_form is False  # unchanged behavior: ask, don't dump a form

    def test_gap_summary_counts_across_events(self):
        gaps = _gaps([[], ["price_min"], ["price_min", "venue"]])
        assert gaps == (
            "1 of them is missing the venue; 2 of them are missing the ticket price"
        )


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
