"""Shared fixtures for pusher tests.

Module-level clients that must be patched here (any NEW module with its own
module-level client gets added to this list or tests hit the real API):
  agent.converters._client    — extraction / vision / whisper
  agent.conversation._client  — clarify / handoff replies
  agent.graph._openai         — embeddings on write
  agent.graph._driver         — Neo4j driver
  agent.graph._geocoder       — Nominatim
  agent.push_records._http    — the Supabase PostgREST client
"""

import json
from datetime import date, timedelta
import os
from unittest.mock import MagicMock, patch

import pytest
from laiive_shared.testing import FakeSession

# The root .env carries a real INTERNAL_API_KEY, and the middleware installs at
# import time of agent.api — so it must be blanked *before* any test module
# imports the app, or every request 403s. Process env beats env_file in
# pydantic-settings. Enforcement itself is covered in shared's
# test_internal_auth.py.
os.environ["INTERNAL_API_KEY"] = ""
# Likewise: PHOENIX_ENABLED=true in the root .env would instrument the openai
# module for the whole suite and ship test spans to the dev collector, mixed in
# with real turns. Tests never trace.
os.environ["PHOENIX_ENABLED"] = "false"
# A real SUPABASE_URL in the root .env would make every write test fire a
# live push_records insert. Empty URL no-ops the write, same as the
# retriever does for eval_records.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""

# Relative, not a literal. A hard-coded date silently rots into the past, and
# the correction layer then reads every fixture as "did you mean a later date?"
# - which is the check working and the suite lying.
SOON = (date.today() + timedelta(days=90)).isoformat()

EXTRACTION_JSON = json.dumps(
    {
        "artists": ["Test Artist"],
        "start_at": f"{SOON}T21:00:00",
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
def mock_push_records():
    """No live PostgREST inserts from tests.

    The empty SUPABASE_URL above already short-circuits `write()`, so this is
    the second line of defence — and the one that keeps holding if a test ever
    sets a URL to exercise the write path itself.
    """
    http = MagicMock()
    http.post.return_value = MagicMock(status_code=201, text="")
    with patch("agent.push_records._http", http):
        yield http


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


@pytest.fixture
def mock_neo4j():
    """Fake driver whose sessions replay the shared writer protocol."""
    driver = MagicMock()
    session = FakeSession()
    driver.session.return_value = session
    driver.fake_session = session
    with patch("agent.graph._driver", driver):
        yield driver
