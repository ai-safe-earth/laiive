"""Shared fixtures for search tests.

Module-level clients that must be patched here (any NEW module with its own
module-level client gets added to this list or tests hit the real API):
  agent.tavily._http       — Tavily search
  agent.extraction._client — OpenAI extraction
  agent.address_lookup._client — OpenAI venue-address lookup
  agent.reports._http      — Supabase PostgREST
  agent.stats._prefect     — Prefect Cloud (scheduler panel)
  agent.learning._http     — Supabase PostgREST (source + query ranking)

The Tavily fake dispatches on the endpoint: /search and /extract have different
response shapes and different billing, so a test that conflates them measures
nothing.
  agent.graph._openai      — embeddings
  agent.graph._driver      — Neo4j driver
  agent.graph._geocoder    — Nominatim
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# The root .env carries a real INTERNAL_API_KEY and the middleware installs at
# import time of agent.api — blank it before any test module imports the app.
# Enforcement itself is covered in shared's test_internal_auth.py.
os.environ["INTERNAL_API_KEY"] = ""

EXTRACTION_JSON = json.dumps(
    {
        "events": [
            {
                "name": "Test Night",
                "artists": ["Test Artist"],
                "start_at": "2027-04-01T21:00:00",
                "venue": "Test Venue",
                "city": "Berlin",
                "price_min": 15,
            }
        ]
    }
)

TAVILY_PAYLOAD = {
    "results": [
        {
            "url": "https://example.com/agenda",
            "title": "Agenda",
            "content": "snippet",
            "raw_content": "Test Artist plays Test Venue on 2027-04-01, 15 EUR",
            "score": 0.9,
        }
    ]
}


def http_response(status_code=200, payload=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = text or json.dumps(payload or {})
    return response


@pytest.fixture(autouse=True)
def mock_address_lookup():
    """No OpenAI call from the venue-address fallback.

    Returns no address by default, so the geocode path under test is the
    ordinary one; a test that wants the fallback sets the reply itself.
    """
    client = MagicMock()
    reply = MagicMock()
    reply.choices = [MagicMock()]
    reply.choices[0].message.content = '{"address": null}'
    client.chat.completions.create.return_value = reply
    with patch("agent.address_lookup._client", client):
        yield client


@pytest.fixture(autouse=True)
def mock_genre_lookup():
    """Autouse: genre_lookup holds a module-level OpenAI client of its own.

    Recognises nothing by default, so a test that does not care about genres
    never depends on what a model would have said.
    """
    client = MagicMock()
    reply = MagicMock()
    reply.choices = [MagicMock()]
    reply.choices[0].message.content = '{"artists": []}'
    client.chat.completions.create.return_value = reply
    with patch("agent.genre_lookup._client", client):
        yield client


# What /extract answers with. A distinct URL from TAVILY_PAYLOAD's, because the
# two endpoints reaching the same page would hide a dedup bug rather than
# exercise one.
TAVILY_EXTRACT_PAYLOAD = {
    "results": [
        {
            "url": "https://drusobg.it/",
            "raw_content": "DRUSO agenda - Test Night at Test Venue",
        }
    ],
    "failed_results": [],
}


@pytest.fixture(autouse=True)
def mock_tavily():
    """Dispatches on the endpoint: /search and /extract are different calls
    with different response shapes and different billing."""
    http = MagicMock()
    http.post.return_value = http_response(payload=TAVILY_PAYLOAD)

    def post(url, *args, **kwargs):
        if "extract" in url:
            return http_response(payload=TAVILY_EXTRACT_PAYLOAD)
        # Deferred rather than captured, so the established idiom still works:
        # a test that sets post.return_value is changing the *search* answer,
        # and side_effect would otherwise silently outrank it.
        return http.post.return_value

    http.post.side_effect = post
    with patch("agent.tavily._http", http):
        yield http


@pytest.fixture(autouse=True)
def mock_openai():
    mock_client = MagicMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = EXTRACTION_JSON
    mock_client.chat.completions.create.return_value = mock_response

    mock_embed = MagicMock()
    mock_embed.data = [MagicMock()]
    mock_embed.data[0].embedding = [0.1] * 1536
    mock_client.embeddings.create.return_value = mock_embed

    with (
        patch("agent.extraction._client", mock_client),
        patch("agent.graph._openai", mock_client),
    ):
        yield mock_client


@pytest.fixture(autouse=True)
def mock_reports_http():
    http = MagicMock()
    http.post.return_value = http_response(
        201, [{"id": "00000000-0000-0000-0000-000000000001"}]
    )
    http.get.return_value = http_response(200, [])
    # A non-empty representation = the claim won the race (see reports.claim_report).
    http.patch.return_value = http_response(
        200, [{"id": "00000000-0000-0000-0000-000000000001", "status": "approved"}]
    )
    with patch("agent.reports._http", http):
        yield http


@pytest.fixture(autouse=True)
def mock_prefect_http():
    """No Prefect Cloud from tests, whatever lands in the root .env."""
    http = MagicMock()
    http.post.return_value = http_response(200, [])
    with patch("agent.stats._prefect", http):
        yield http


@pytest.fixture(autouse=True)
def mock_learning_http():
    """An empty store: nothing learned yet, which is also the first-run state.

    GET returns [] so the sweep falls back to the file's templates and applies
    no domain filters; POST accepts the upsert. A test that wants a populated
    ranking sets http.get.return_value itself.
    """
    http = MagicMock()
    http.get.return_value = http_response(200, [])
    http.post.return_value = http_response(201, [])
    with patch("agent.learning._http", http):
        yield http


@pytest.fixture(autouse=True)
def mock_geocoder():
    from laiive_shared.geocode import GeocodeResult

    geocoder = MagicMock()
    city = GeocodeResult(
        lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
    )
    # Both are stubbed: the write path and the backfill geocode the city with
    # geocode() and the venue with geocode_venue(). A MagicMock left to
    # autospec geocode_venue returns a mock whose .lat flows into the Cypher.
    # The venue answer is deliberately a different point from the city: when
    # the two coincide the backfill treats it as a centroid fallback, which is
    # its own case and has its own test.
    venue = GeocodeResult(
        lat=52.5111, lng=13.4433, country_code="DE", display_name="Berghain, Berlin"
    )
    geocoder.geocode.return_value = city
    geocoder.geocode_venue.return_value = venue
    with patch("agent.graph._geocoder", geocoder):
        yield geocoder


class FakeNeo4jResult:
    def __init__(self, single=None, rows=None):
        self._single = single
        self._rows = rows or []

    def single(self):
        return self._single

    def __iter__(self):
        return iter(self._rows)


class FakeNeo4jSession:
    """Understands the writer's query sequence plus the read-only probes."""

    def __init__(self, dedup_hit=None, vector_hit=None):
        self.queries = []
        self.dedup_hit = dedup_hit
        self.vector_hit = vector_hit

    def run(self, query, **params):
        self.queries.append((query, params))
        if "RETURN e.uid AS uid, e.name AS name LIMIT 1" in query:
            return FakeNeo4jResult(single=self.dedup_hit)
        if "db.index.vector.queryNodes" in query:
            return FakeNeo4jResult(single=self.vector_hit)
        if "CREATE (e:Event" in query:
            return FakeNeo4jResult(
                single={
                    "uid": params["event_uid"],
                    "name": params["name"],
                    "venue": params["venue"],
                    "city": params["city"],
                    "venue_uid": params["venue_uid"],
                }
            )
        if "RETURN 1" in query:
            return FakeNeo4jResult(single={"1": 1})
        return FakeNeo4jResult(rows=[])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


@pytest.fixture(autouse=True)
def mock_neo4j():
    driver = MagicMock()
    session = FakeNeo4jSession()
    driver.session.return_value = session
    driver.fake_session = session
    with patch("agent.graph._driver", driver):
        yield driver
