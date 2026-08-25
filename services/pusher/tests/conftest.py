"""Shared fixtures for pusher tests.

Module-level clients that must be patched here (any NEW module with its own
module-level client gets added to this list or tests hit the real API):
  agent.converters._client    — extraction / vision / whisper
  agent.conversation._client  — clarify / handoff replies
  agent.graph._openai         — embeddings on write
  agent.graph._driver         — Neo4j driver
  agent.graph._geocoder       — Nominatim
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# The root .env carries a real INTERNAL_API_KEY, and the middleware installs at
# import time of agent.api — so it must be blanked *before* any test module
# imports the app, or every request 403s. Process env beats env_file in
# pydantic-settings. Enforcement itself is covered in shared's
# test_internal_auth.py.
os.environ["INTERNAL_API_KEY"] = ""

EXTRACTION_JSON = json.dumps(
    {
        "artists": ["Test Artist"],
        "start_at": "2026-04-01T21:00:00",
        "venue": "Test Venue",
        "address": "Kantstrasse 12a",
        "city": "Berlin",
        "price_min": 15,
    }
)


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock every OpenAI client globally to avoid real API calls."""
    mock_client = MagicMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = EXTRACTION_JSON
    mock_client.chat.completions.create.return_value = mock_response

    mock_embed = MagicMock()
    mock_embed.data = [MagicMock()]
    mock_embed.data[0].embedding = [0.1] * 1536
    mock_client.embeddings.create.return_value = mock_embed

    mock_transcription = MagicMock()
    mock_transcription.text = "Test Artist at Test Venue in Berlin on April 1st"
    mock_client.audio.transcriptions.create.return_value = mock_transcription

    with (
        patch("agent.converters._client", mock_client),
        patch("agent.conversation._client", mock_client),
        patch("agent.graph._openai", mock_client),
    ):
        yield mock_client


@pytest.fixture(autouse=True)
def mock_geocoder():
    """No Nominatim calls from tests."""
    from laiive_shared.geocode import GeocodeResult

    geocoder = MagicMock()
    result = GeocodeResult(
        lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
    )
    # Both are stubbed: the writer geocodes the city with geocode() and the
    # venue with geocode_venue(). A MagicMock left to autospec geocode_venue
    # returns a mock whose .lat flows straight into the Cypher params.
    geocoder.geocode.return_value = result
    geocoder.geocode_venue.return_value = result
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
    """Understands the shared writer's query sequence: dedup probe → write →
    embedding-backfill selects."""

    def __init__(self, dedup_hit=None, venue_node=None):
        self.queries = []
        self.dedup_hit = dedup_hit
        self.venue_node = venue_node

    def run(self, query, **params):
        self.queries.append((query, params))
        if "MATCH (v:Venue {uid: $uid})" in query:
            return FakeNeo4jResult(single=self.venue_node)
        if "RETURN e.uid AS uid, e.name AS name LIMIT 1" in query:
            return FakeNeo4jResult(single=self.dedup_hit)
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
        return FakeNeo4jResult(rows=[])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


@pytest.fixture
def mock_neo4j():
    """Fake driver whose sessions replay the shared writer protocol."""
    driver = MagicMock()
    session = FakeNeo4jSession()
    driver.session.return_value = session
    driver.fake_session = session
    with patch("agent.graph._driver", driver):
        yield driver
