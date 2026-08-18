"""Conversation + converters unit tests (all OpenAI calls mocked)."""

import json

from agent.conversation import (
    MAX_EVENTS_PER_TURN,
    WalkInput,
    clarification_rounds,
    default_currency,
    process_turn,
)
from agent.converters import (
    audio_to_text,
    document_to_text,
    extract_drafts_from_text,
    image_to_text,
    refine_draft,
)
from laiive_shared import EventDraft


def set_extraction(mock_openai, payload: dict | list | str):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    mock_openai.chat.completions.create.return_value.choices[
        0
    ].message.content = content


COMPLETE = {
    "artists": ["Test Artist"],
    "start_at": "2026-04-01T21:00:00",
    "venue": "Test Venue",
    "address": "Kantstrasse 12a",
    "city": "Berlin",
    "price_min": 15,
}


def first_draft(text: str):
    """The one-event view of an extraction that always returns a list."""
    drafts = extract_drafts_from_text(text)
    return drafts[0] if drafts else EventDraft()


class TestExtraction:
    def test_extracts_complete_draft(self, mock_openai):
        draft = first_draft("Test Artist, April 1st, Test Venue, Berlin, 15€")
        assert draft.artists == ["Test Artist"]
        assert draft.venue == "Test Venue"
        assert draft.price_min == 15.0

    def test_invalid_json_gives_empty_draft(self, mock_openai):
        set_extraction(mock_openai, "not json")
        draft = first_draft("gibberish")
        assert draft.model_dump(exclude_none=True, exclude_defaults=True) == {}

    def test_markdown_fences_stripped(self, mock_openai):
        set_extraction(mock_openai, "```json\n" + json.dumps(COMPLETE) + "\n```")
        assert first_draft("whatever").venue == "Test Venue"

    def test_string_artist_becomes_list(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "artists": "Solo Act"})
        assert first_draft("x").artists == ["Solo Act"]

    def test_free_price_is_zero_not_missing(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "price_min": "free"})
        assert first_draft("free show").price_min == 0.0

    def test_unknown_fields_ignored(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "hacker_field": "boom"})
        assert first_draft("x").venue == "Test Venue"


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
        assert turn.drafts[0].price_currency == "EUR"  # defaulted from Berlin

    def test_incomplete_first_message_asks_once(self, mock_openai):
        set_extraction(mock_openai, {"artists": ["X"], "city": "Berlin"})
        turn = process_turn([{"role": "user", "content": "gig by X in Berlin"}])
        assert turn.show_form is False
        assert set(turn.missing[0]) == {"start_at", "venue", "address", "price_min"}

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

    def test_reply_language_is_the_last_thing_the_model_reads(self, mock_openai):
        # A pasted flyer is what used to decide the language; the instruction
        # goes after the whole conversation for exactly that reason.
        process_turn([{"role": "user", "content": "full event info"}])
        reply_call = mock_openai.chat.completions.create.call_args.kwargs
        last = reply_call["messages"][-1]
        assert last["role"] == "system"
        assert "Write your reply in" in last["content"]

    def test_language_is_detected_from_the_promoters_own_last_words(self, mock_openai):
        from agent.conversation import latest_user_text

        assert (
            latest_user_text(
                [
                    {"role": "user", "content": "un concierto"},
                    {"role": "assistant", "content": "when?"},
                    {"role": "user", "content": "next friday"},
                ]
            )
            == "next friday"
        )
        assert latest_user_text([{"role": "assistant", "content": "hi"}]) == ""

    def test_no_confirmed_marker_anywhere(self, mock_openai):
        """The 'type yes'/**CONFIRMED** write path is gone."""
        import agent.api as api
        import agent.conversation as conversation

        for module in (conversation, api):
            source = open(module.__file__, encoding="utf-8").read()
            assert "CONFIRMED" not in source


class TestWalk:
    """Several events = a walk: one form per turn, client-carried cursor."""

    TWO = {"events": [COMPLETE, {"artists": ["Y"], "city": "Berlin"}]}

    def test_many_events_enter_the_walk_immediately(self, mock_openai):
        set_extraction(mock_openai, self.TWO)
        turn = process_turn([{"role": "user", "content": "two gigs"}])
        assert turn.walk is True
        assert turn.cursor == 0
        assert turn.show_form is True  # no set-wide round: the intro is the ask
        assert len(turn.drafts) == 2
        assert turn.missing[0] == []
        assert set(turn.missing[1]) == {"start_at", "venue", "address", "price_min"}

    def test_a_single_event_never_walks(self, mock_openai):
        turn = process_turn([{"role": "user", "content": "full event info"}])
        assert turn.walk is False

    def test_walk_turn_refines_only_the_cursor(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "venue": "Refined Venue"})
        untouched = EventDraft(artists=["A"], venue="First Venue")
        turn = process_turn(
            [{"role": "user", "content": "it's at Refined Venue"}],
            walk=WalkInput(drafts=[untouched, EventDraft(artists=["Y"])], cursor=1),
        )
        assert turn.walk is True
        assert turn.cursor == 1
        assert turn.drafts[0] is untouched  # neighbour not even copied
        assert turn.drafts[1].venue == "Refined Venue"
        # only refine + language + reply ran — no full re-extraction prompt
        prompts = [
            call.kwargs["messages"][0]["content"]
            for call in mock_openai.chat.completions.create.call_args_list
        ]
        assert not any("Extract live music events" in p for p in prompts)

    def test_walk_cursor_is_clamped(self, mock_openai):
        turn = process_turn(
            [{"role": "user", "content": "next"}],
            walk=WalkInput(drafts=[EventDraft(artists=["A"])], cursor=7),
        )
        assert turn.cursor == 0

    def test_empty_walk_falls_back_to_extraction(self, mock_openai):
        turn = process_turn(
            [{"role": "user", "content": "full event info"}],
            walk=WalkInput(drafts=[], cursor=0),
        )
        assert turn.walk is False
        assert turn.drafts[0].venue == "Test Venue"

    def test_walk_turn_defaults_currency_on_the_cursor(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "city": "London"})
        turn = process_turn(
            [{"role": "user", "content": "it's in London"}],
            walk=WalkInput(drafts=[EventDraft(artists=["A"])], cursor=0),
        )
        assert turn.drafts[0].price_currency == "GBP"

    def test_beyond_the_cap_is_truncated_and_flagged(self, mock_openai):
        set_extraction(mock_openai, {"events": [COMPLETE] * (MAX_EVENTS_PER_TURN + 3)})
        turn = process_turn([{"role": "user", "content": "a whole season"}])
        assert len(turn.drafts) == MAX_EVENTS_PER_TURN
        assert turn.truncated is True
        assert turn.walk is True

    def test_nothing_extracted_still_makes_one_draft(self, mock_openai):
        set_extraction(mock_openai, "not json")
        turn = process_turn([{"role": "user", "content": "hello?"}])
        assert len(turn.drafts) == 1
        assert turn.show_form is False  # unchanged behavior: ask, don't dump a form


class TestRefineDraft:
    def test_merges_the_message_into_the_draft(self, mock_openai):
        set_extraction(mock_openai, {**COMPLETE, "price_min": 20})
        refined = refine_draft(EventDraft(artists=["Test Artist"]), "20 euros")
        assert refined.price_min == 20.0

    def test_unparseable_reply_returns_the_draft_unchanged(self, mock_openai):
        set_extraction(mock_openai, "sure, done!")
        draft = EventDraft(artists=["A"], venue="V")
        assert refine_draft(draft, "thanks") is draft

    def test_current_draft_travels_in_the_prompt(self, mock_openai):
        refine_draft(EventDraft(artists=["A"], venue="Sala X"), "18 euros")
        prompt = mock_openai.chat.completions.create.call_args.kwargs["messages"][0][
            "content"
        ]
        assert "Sala X" in prompt
        assert "18 euros" in prompt


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
