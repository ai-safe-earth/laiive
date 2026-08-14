"""Shared fixtures for search tests.

Module-level clients that must be patched here (any NEW module with its own
module-level client gets added to this list or tests hit the real API):
  agent.tavily._http       — Tavily search
  agent.extraction._client — OpenAI extraction
  agent.reports._http      — Supabase PostgREST
  agent.graph._openai      — embeddings
  agent.graph._driver      — Neo4j driver
  agent.graph._geocoder    — Nominatim
"""

import json
from unittest.mock import MagicMock, patch

import pytest

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
def mock_tavily():
    http = MagicMock()
    http.post.return_value = http_response(payload=TAVILY_PAYLOAD)
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
    http.patch.return_value = http_response(204, {})
    with patch("agent.reports._http", http):
        yield http


@pytest.fixture(autouse=True)
def mock_geocoder():
    from laiive_shared.geocode import GeocodeResult

    geocoder = MagicMock()
    geocoder.geocode.return_value = GeocodeResult(
        lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
    )
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
