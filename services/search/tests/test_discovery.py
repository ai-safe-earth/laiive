"""Sweep pipeline: extraction plumbing, dedup verdicts, bounds."""

import json
from unittest.mock import MagicMock

from agent import discovery, extraction
from conftest import http_response


def test_sweep_produces_new_candidate():
    result = discovery.sweep_city("Berlin")
    assert result.stats["pages_searched"] == 1
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.dedup_status == "new"
    assert candidate.source_url == "https://example.com/agenda"
    assert candidate.draft.venue == "Test Venue"
    assert candidate.missing == []


def test_sweep_skips_past_events(mock_openai):
    past = json.dumps(
        {
            "events": [
                {
                    "artists": ["Old"],
                    "start_at": "2020-01-01T20:00:00",
                    "venue": "V",
                    "city": "Berlin",
                    "price_min": 5,
                }
            ]
        }
    )
    mock_openai.chat.completions.create.return_value.choices[0].message.content = past
    result = discovery.sweep_city("Berlin")
    assert result.candidates == []
    assert result.stats["skipped_past"] == 1


def test_sweep_dedups_same_event_across_pages(mock_tavily):
    page = dict(mock_tavily.post.return_value.json.return_value["results"][0])
    second = dict(page, url="https://other.com/gigs")
    mock_tavily.post.return_value = http_response(payload={"results": [page, second]})
    result = discovery.sweep_city("Berlin")
    assert result.stats["pages_searched"] == 2
    assert len(result.candidates) == 1


def test_sweep_fills_missing_city(mock_openai):
    no_city = json.dumps(
        {
            "events": [
                {
                    "artists": ["A"],
                    "start_at": "2027-04-01T21:00:00",
                    "venue": "V",
                    "price_min": 5,
                }
            ]
        }
    )
    mock_openai.chat.completions.create.return_value.choices[
        0
    ].message.content = no_city
    result = discovery.sweep_city("Madrid")
    assert result.candidates[0].draft.city == "Madrid"


def test_sweep_marks_exact_duplicate(mock_neo4j):
    mock_neo4j.fake_session.dedup_hit = {"uid": "abc", "name": "Test Night"}
    result = discovery.sweep_city("Berlin")
    candidate = result.candidates[0]
    assert candidate.dedup_status == "exists"
    assert candidate.matched_uid == "abc"


def test_sweep_marks_vector_similar(mock_neo4j):
    mock_neo4j.fake_session.vector_hit = {
        "uid": "xyz",
        "name": "Test Nite",
        "score": 0.95,
    }
    result = discovery.sweep_city("Berlin")
    candidate = result.candidates[0]
    assert candidate.dedup_status == "similar"
    assert candidate.similarity == 0.95


def test_extraction_falls_back_on_unparseable_reply(mock_openai):
    """Mini garbage → one more call with the fallback model."""
    garbage = MagicMock()
    garbage.choices = [MagicMock()]
    garbage.choices[0].message.content = "sorry, I cannot"
    good = MagicMock()
    good.choices = [MagicMock()]
    good.choices[0].message.content = json.dumps(
        {
            "events": [
                {
                    "artists": ["A"],
                    "venue": "V",
                    "city": "C",
                    "start_at": "2027-01-01T20:00:00",
                    "price_min": 1,
                }
            ]
        }
    )
    mock_openai.chat.completions.create.side_effect = [garbage, good]

    drafts = extraction.extract_events_from_page(
        "text", url="https://x.com", city="Berlin"
    )
    assert len(drafts) == 1
    models = [
        call.kwargs["model"]
        for call in mock_openai.chat.completions.create.call_args_list
    ]
    assert models[0] != models[1]


def test_extraction_empty_list_is_not_low_confidence(mock_openai):
    """A clean empty answer is final — no fallback spend on empty pages."""
    empty = MagicMock()
    empty.choices = [MagicMock()]
    empty.choices[0].message.content = '{"events": []}'
    mock_openai.chat.completions.create.return_value = empty
    mock_openai.chat.completions.create.side_effect = None

    drafts = extraction.extract_events_from_page(
        "text", url="https://x.com", city="Berlin"
    )
    assert drafts == []
    assert mock_openai.chat.completions.create.call_count == 1


def test_tavily_failure_yields_empty_sweep(mock_tavily):
    mock_tavily.post.side_effect = RuntimeError("boom")
    result = discovery.sweep_city("Berlin")
    assert result.candidates == []
    assert result.stats["pages_searched"] == 0
