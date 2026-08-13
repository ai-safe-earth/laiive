"""Shared fixtures for pusher tests."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI client globally to avoid real API calls."""
    mock_client = MagicMock()

    # Mock chat completions
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = '{"artist": "Test Artist", "date_time": "2026-04-01T21:00:00", "venue": "Test Venue", "city": "Berlin", "price": "15"}'
    mock_client.chat.completions.create.return_value = mock_response

    # Mock embeddings
    mock_embed = MagicMock()
    mock_embed.data = [MagicMock()]
    mock_embed.data[0].embedding = [0.1] * 1536
    mock_client.embeddings.create.return_value = mock_embed

    # Mock whisper
    mock_transcription = MagicMock()
    mock_transcription.text = "Test Artist at Test Venue in Berlin on April 1st"
    mock_client.audio.transcriptions.create.return_value = mock_transcription

    with patch("agent.converters._client", mock_client), patch(
        "agent.conversation._client", mock_client
    ), patch("agent.neo4j_writer._openai", mock_client):
        yield mock_client


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j driver for write operations."""
    mock_record = MagicMock()
    mock_record.__getitem__ = lambda self, key: {
        "event_id": "test-uuid",
        "event_name": "Test Event",
        "artist": "Test Artist",
        "venue": "Test Venue",
        "city": "Berlin",
    }[key]

    mock_result = MagicMock()
    mock_result.single.return_value = mock_record

    mock_session = MagicMock()
    mock_session.run.return_value = mock_result
    mock_session.__enter__ = lambda self: self
    mock_session.__exit__ = lambda self, *a: None

    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    with patch("agent.neo4j_writer._driver", mock_driver):
        yield mock_driver
