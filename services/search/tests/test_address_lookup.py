"""The venue-address fallback: only fires on a geocode miss, never raises."""

import json

from agent import address_lookup
from conftest import http_response


def set_reply(client, payload):
    reply = client.chat.completions.create.return_value
    reply.choices[0].message.content = json.dumps(payload)


def test_returns_the_address_the_search_results_state(mock_address_lookup, mock_tavily):
    set_reply(mock_address_lookup, {"address": "Calle de Alberto Alcocer 32, 28036"})
    assert (
        address_lookup.resolve_address("Sala Mon Live", "Madrid")
        == "Calle de Alberto Alcocer 32, 28036"
    )


def test_no_address_in_the_results_is_none(mock_address_lookup, mock_tavily):
    set_reply(mock_address_lookup, {"address": None})
    assert address_lookup.resolve_address("Nowhere Club", "Madrid") is None


def test_a_bare_city_name_is_not_an_address(mock_address_lookup, mock_tavily):
    """It would geocode to the centroid and read as a real venue pin."""
    set_reply(mock_address_lookup, {"address": "Madrid"})
    assert address_lookup.resolve_address("Nowhere Club", "Madrid") is None


def test_no_search_hits_skips_the_llm_entirely(mock_address_lookup, mock_tavily):
    mock_tavily.post.return_value = http_response(payload={"results": []})
    assert address_lookup.resolve_address("Nowhere Club", "Madrid") is None
    assert not mock_address_lookup.chat.completions.create.called


def test_llm_failure_degrades_to_none(mock_address_lookup, mock_tavily):
    """A resolver outage must not fail an event submission."""
    mock_address_lookup.chat.completions.create.side_effect = RuntimeError("boom")
    assert address_lookup.resolve_address("Sala Mon Live", "Madrid") is None


def test_unparseable_reply_degrades_to_none(mock_address_lookup, mock_tavily):
    mock_address_lookup.chat.completions.create.return_value.choices[
        0
    ].message.content = "sorry, I could not find it"
    assert address_lookup.resolve_address("Sala Mon Live", "Madrid") is None


def test_empty_venue_never_searches(mock_address_lookup, mock_tavily):
    assert address_lookup.resolve_address("", "Madrid") is None
    assert not mock_tavily.post.called
