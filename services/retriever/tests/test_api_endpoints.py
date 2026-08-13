"""
Tests for FastAPI endpoints - health checks, chat endpoints, and error handling.
Run with: pytest tests/test_api_endpoints.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


# Mock dependencies before importing app
@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock Neo4j and external dependencies."""
    with patch("agent.api.neo4j_client") as mock_neo4j:
        mock_neo4j.get_schema.return_value = "Mock Schema"
        mock_neo4j._driver.verify_connectivity.return_value = True

        from agent.api import app

        yield app, mock_neo4j


@pytest.fixture
def client(mock_dependencies):
    """Create test client."""
    app, _ = mock_dependencies
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check and info endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "endpoints" in data
        assert data["version"] == "0.2.0"

    def test_health_endpoint_all_ok(self, client, mock_dependencies):
        """Test health endpoint when all services are healthy."""
        _, mock_neo4j = mock_dependencies

        with patch("openai.models.list") as mock_openai:
            mock_openai.return_value = []

            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "ok"
            assert data["checks"]["api"] == "ok"
            assert data["checks"]["neo4j"] == "ok"
            assert data["checks"]["openai"] == "ok"

    def test_health_endpoint_neo4j_down(self, client, mock_dependencies):
        """Test health endpoint when Neo4j is down."""
        _, mock_neo4j = mock_dependencies
        mock_neo4j._driver.verify_connectivity.side_effect = Exception(
            "Connection refused"
        )

        with patch("openai.models.list") as mock_openai:
            mock_openai.return_value = []

            response = client.get("/health")
            assert response.status_code == 503

            data = response.json()
            assert data["status"] == "degraded"
            assert "error" in data["checks"]["neo4j"]

    def test_schema_endpoint_success(self, client, mock_dependencies):
        """Test schema endpoint returns schema."""
        _, mock_neo4j = mock_dependencies
        mock_neo4j.get_schema.return_value = "Test Schema Content"

        response = client.get("/schema")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["schema"] == "Test Schema Content"

    def test_schema_endpoint_error(self, client, mock_dependencies):
        """Test schema endpoint handles errors."""
        _, mock_neo4j = mock_dependencies
        mock_neo4j.get_schema.side_effect = Exception("Schema error")

        response = client.get("/schema")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "error"
        assert data["schema"] is None
        assert "error" in data


class TestChatEndpoint:
    """Test /chat JSON endpoint."""

    @patch("agent.api.manager")
    def test_chat_basic_query(self, mock_manager, client):
        """Test basic chat query."""
        mock_manager.run_react.return_value = (
            "I can help you find concerts!",
            None,
            None,
            False,
            False,
        )

        response = client.post("/chat", json={"message": "Hello"})

        assert response.status_code == 200
        data = response.json()

        assert "request_id" in data
        assert "response" in data
        assert data["response"] == "I can help you find concerts!"
        assert data["used_query"] is False
        assert data["needs_more_info"] is False

    @patch("agent.api.manager")
    def test_chat_with_database_query(self, mock_manager, client):
        """Test chat with database query execution."""
        mock_manager.run_react.return_value = (
            "I found some events:",
            "MATCH (e:Event) RETURN e LIMIT 5",
            [{"event": {"name": "Jazz Night"}}],
            True,
            False,
        )

        response = client.post("/chat", json={"message": "Find jazz concerts"})

        assert response.status_code == 200
        data = response.json()

        assert data["used_query"] is True
        assert data["cypher"] is not None
        assert data["results"] is not None
        assert len(data["results"]) > 0

    @patch("agent.api.manager")
    def test_chat_needs_more_info(self, mock_manager, client):
        """Test chat when more info is needed."""
        mock_manager.run_react.return_value = (
            "Where would you like to find events?",
            None,
            None,
            False,
            True,
        )

        response = client.post("/chat", json={"message": "Find concerts"})

        assert response.status_code == 200
        data = response.json()

        assert data["needs_more_info"] is True
        assert data["used_query"] is False

    @patch("agent.api.manager")
    def test_chat_with_conversation_history(self, mock_manager, client):
        """Test chat with conversation history."""
        mock_manager.run_react.return_value = (
            "Based on our conversation...",
            "MATCH ...",
            [],
            True,
            False,
        )

        response = client.post(
            "/chat",
            json={
                "message": "What about tomorrow?",
                "conversation_history": [
                    {"role": "user", "content": "Find jazz concerts"},
                    {"role": "assistant", "content": "I found 5 concerts"},
                ],
            },
        )

        assert response.status_code == 200
        mock_manager.run_react.assert_called_once()

        # Verify conversation history was passed
        call_args = mock_manager.run_react.call_args
        assert call_args[0][1] is not None  # conversation_history arg

    @patch("agent.api.manager")
    def test_chat_query_execution_error(self, mock_manager, client):
        """Test error handling when ReAct agent fails — returns graceful 200."""
        mock_manager.run_react.side_effect = Exception("Agent failed")

        response = client.post("/chat", json={"message": "Find concerts"})

        # _process_chat catches exceptions and returns a graceful error response
        assert response.status_code == 200
        data = response.json()
        assert "trouble" in data["response"].lower()

    def test_chat_invalid_request(self, client):
        """Test chat with invalid request body."""
        response = client.post("/chat", json={})

        assert response.status_code == 422  # Validation error

    def test_chat_invalid_json(self, client):
        """Test chat with invalid JSON."""
        response = client.post("/chat", data="invalid json")

        assert response.status_code == 422


class TestChatStreamEndpoint:
    """Test /chat/stream SSE endpoint."""

    @patch("agent.api.manager")
    def test_chat_stream_basic(self, mock_manager, client):
        """Test basic SSE streaming."""
        mock_manager.run_react.return_value = (
            "Hello!",
            None,
            None,
            False,
            False,
        )

        response = client.post(
            "/chat/stream", json={"messages": [{"role": "user", "content": "Hi"}]}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "X-Request-ID" in response.headers

    def test_chat_stream_no_messages(self, client):
        """Test SSE endpoint with no messages."""
        response = client.post("/chat/stream", json={"messages": []})

        assert response.status_code == 400

    @patch("agent.api.manager")
    def test_chat_stream_with_location(self, mock_manager, client):
        """Test SSE with location data."""
        mock_manager.run_react.return_value = (
            "Found events near you",
            "MATCH ...",
            [],
            True,
            False,
        )

        response = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Events near me"}],
                "location": {"latitude": 52.52, "longitude": 13.40, "city": "Berlin"},
                "language": "en",
            },
        )

        assert response.status_code == 200

    def test_chat_stream_invalid_message_role(self, client):
        """Test SSE with invalid message role."""
        response = client.post(
            "/chat/stream",
            json={"messages": [{"role": "invalid_role", "content": "Test"}]},
        )

        assert response.status_code == 422


class TestMetricsEndpoint:
    """Test metrics endpoint."""

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint returns basic status."""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "operational"


class TestRequestValidation:
    """Test Pydantic request validation."""

    def test_message_validation_role(self, client):
        """Test that invalid role is rejected."""
        response = client.post(
            "/chat",
            json={
                "message": "test",
                "conversation_history": [{"role": "hacker", "content": "test"}],
            },
        )

        assert response.status_code == 422

    def test_location_validation(self, client):
        """Test location validation."""
        response = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "location": {
                    "latitude": "invalid",  # Should be float
                    "longitude": 13.40,
                },
            },
        )

        assert response.status_code == 422

    def test_required_fields(self, client):
        """Test required fields are enforced."""
        response = client.post(
            "/chat",
            json={
                "conversation_history": []
                # Missing 'message' field
            },
        )

        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
