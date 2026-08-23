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


def test_a_sweep_spends_one_tavily_credit_per_query_template(mock_tavily):
    """A credit is charged per call, not per result, and the free plan is 1000
    a month. Templates x towns x weeks is the whole budget, so a change that
    adds a phrasing should be a deliberate one, priced here rather than on the
    bill: five templates over twenty towns is ~430 credits a month."""
    discovery.sweep_city("Bergamo")
    assert mock_tavily.post.call_count == len(discovery.QUERY_TEMPLATES) == 5


def test_the_sweep_reports_what_it_spent(mock_tavily):
    result = discovery.sweep_city("Bergamo")
    assert result.stats["tavily_credits"] == len(discovery.QUERY_TEMPLATES)


def test_max_pages_does_not_reduce_the_tavily_spend(mock_tavily):
    """It is applied after the calls, so it bounds the OpenAI extraction bill
    and nothing else. Easy to reach for as a cost control and wrong."""
    discovery.sweep_city("Bergamo", max_pages=1)
    assert mock_tavily.post.call_count == len(discovery.QUERY_TEMPLATES)


def test_the_search_is_biased_to_the_swept_country(mock_tavily):
    """Both provinces are Italian; the locale boost is free."""
    discovery.sweep_city("Torino")
    body = mock_tavily.post.call_args.kwargs["json"]
    assert body["country"] == "italy"
    # An empty domain filter must never be sent: an over-restricted query
    # returns nothing and reads as a town with no music.
    assert "include_domains" not in body
    assert "exclude_domains" not in body


def test_every_template_reaches_the_page_budget(mock_tavily, mock_openai):
    """max_pages truncates, and concatenating template after template spends
    the whole budget on the first phrasing. The later, narrower ones are the
    reason the list is long -- they must not be what falls off the end."""
    calls = {"n": 0}

    def three_hits_per_query(url, **kwargs):
        """Each template answers with three pages on its own domain."""
        template_index = calls["n"]
        calls["n"] += 1
        return http_response(
            200,
            {
                "results": [
                    {
                        "url": f"https://t{template_index}.example/{page}",
                        "title": "Agenda",
                        "content": "x",
                        "raw_content": "x",
                        "score": 0.5,
                    }
                    for page in range(3)
                ]
            },
        )

    mock_tavily.post.side_effect = three_hits_per_query
    result = discovery.sweep_city("Bergamo", max_pages=3)

    assert result.stats["pages_searched"] == 3
    # Asserted on what was read, not on the candidates: the fake extractor
    # answers every page with the same event, and the intra-sweep dedup then
    # collapses them to one candidate whatever the pages were.
    read = "".join(
        call.kwargs["messages"][0]["content"]
        for call in mock_openai.chat.completions.create.call_args_list
    )
    # One page from each of three templates. Concatenation would have read
    # three pages all from t0.
    assert "t0.example" in read
    assert "t1.example" in read
    assert "t2.example" in read


def test_the_queries_are_italian_all_the_way_through(mock_tavily):
    """The templates are Italian because the query language picks the language
    of the sites reached -- measured 3/9 Italian domains for an English query
    against 7/9 for an Italian one. An English month name inside them is the
    same mistake in miniature, and strftime("%B") answers in the C locale."""
    discovery.sweep_city("Torino")
    queries = [call.kwargs["json"]["query"] for call in mock_tavily.post.call_args_list]
    assert queries, "no query was issued"
    for query in queries:
        assert "concerts" not in query and "live music" not in query
        assert not any(
            month in query
            for month in (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            )
        ), f"English month leaked into {query!r}"


def test_italian_month_year_does_not_depend_on_the_process_locale():
    from datetime import datetime as dt

    assert discovery.italian_month_year(dt(2026, 8, 23)) == "agosto 2026"
    assert discovery.italian_month_year(dt(2027, 1, 5)) == "gennaio 2027"
    assert discovery.italian_month_year(dt(2026, 12, 31)) == "dicembre 2026"
