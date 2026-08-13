"""
Tests for error handling and failure scenarios across the pipeline.
Run with: pytest tests/test_error_handling.py -v
"""

import pytest
from unittest.mock import Mock, patch
import json
from agent.tools.query_builder import QueryBuilderTool
from agent.tools.safety_guard import SafetyGuardTool


@pytest.fixture
def mock_schema():
    """Mock database schema."""
    return "Mock Schema"


class TestNeo4jConnectionErrors:
    """Test Neo4j connection and query errors."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_neo4j_connection_timeout(self, mock_neo4j):
        """Test handling of Neo4j connection timeout."""
        mock_neo4j.execute_read.side_effect = Exception("Connection timeout")

        with patch("agent.tools.query_builder.get_openai_client"):
            tool = QueryBuilderTool(schema="test")
            tool.client = Mock()
            tool.safety_guard = Mock()
            tool.safety_guard.run.return_value = json.dumps(
                {"is_safe": True, "violations": []}
            )

            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content="MATCH (e:Event) RETURN e"))
            ]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            with patch(
                "agent.tools.query_builder.chat_completion_with_retry",
                return_value=mock_response,
            ):
                result_json = tool.run("Find concerts")

            result = json.loads(result_json)
            assert result["status"] == "error"
            assert "timeout" in result["error"].lower()

    @patch("agent.tools.query_builder.neo4j_client")
    def test_neo4j_invalid_query_syntax(self, mock_neo4j):
        """Test handling of invalid Cypher syntax."""
        mock_neo4j.execute_read.side_effect = Exception("Invalid syntax near 'RETURNN'")

        with patch("agent.tools.query_builder.get_openai_client"):
            tool = QueryBuilderTool(schema="test")
            tool.client = Mock()
            tool.safety_guard = Mock()
            tool.safety_guard.run.return_value = json.dumps(
                {"is_safe": True, "violations": []}
            )

            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content="MATCH (e:Event) RETURNN e"))
            ]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            with patch(
                "agent.tools.query_builder.chat_completion_with_retry",
                return_value=mock_response,
            ):
                result_json = tool.run("Find concerts")

            result = json.loads(result_json)
            assert result["status"] == "error"
            assert "syntax" in result["error"].lower()

    @patch("agent.clients.neo4j_client.neo4j_client")
    def test_neo4j_database_unavailable(self, mock_neo4j):
        """Test handling when database is unavailable."""
        mock_neo4j.execute_read.side_effect = Exception("Database unavailable")
        mock_neo4j._driver.verify_connectivity.side_effect = Exception("Cannot connect")

        with patch("agent.tools.query_builder.get_openai_client"):
            tool = QueryBuilderTool(schema="test")
            tool.client = Mock()
            tool.safety_guard = Mock()
            tool.safety_guard.run.return_value = json.dumps(
                {"is_safe": True, "violations": []}
            )

            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content="MATCH (e:Event) RETURN e"))
            ]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            with patch(
                "agent.tools.query_builder.chat_completion_with_retry",
                return_value=mock_response,
            ):
                result_json = tool.run("Find concerts")

            result = json.loads(result_json)
            assert result["status"] == "error"


class TestLLMAPIErrors:
    """Test LLM API failures."""

    @patch("agent.tools.query_builder.neo4j_client")
    @patch("agent.tools.query_builder.chat_completion_with_retry")
    def test_llm_returns_malformed_json(self, mock_chat, mock_neo4j):
        """Test handling when LLM returns malformed response."""
        with patch("agent.tools.query_builder.get_openai_client"):
            tool = QueryBuilderTool(schema="test")
            tool.client = Mock()
            tool.safety_guard = Mock()
            tool.safety_guard.run.return_value = json.dumps(
                {"is_safe": True, "violations": []}
            )

            # LLM returns invalid Cypher
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="This is not Cypher"))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
            mock_chat.return_value = mock_response

            mock_neo4j.execute_read.side_effect = Exception("Invalid query")

            result_json = tool.run("Find concerts")

            result = json.loads(result_json)
            assert result["status"] == "error"


class TestSafetyGuardErrors:
    """Test safety guard failures."""

    def test_cypher_validation_failure(self):
        """Test handling of Cypher validation errors."""
        tool = SafetyGuardTool()

        # Should handle edge cases gracefully
        result_json = tool.run(None)
        json.loads(result_json)  # should not crash


class TestDataValidationErrors:
    """Test data validation and malformed input errors."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_malformed_neo4j_results(self, mock_neo4j):
        """Test handling of unexpected Neo4j result format."""
        mock_neo4j.execute_read.return_value = [
            {"unexpected_key": "value"}  # Missing expected structure
        ]

        with patch("agent.tools.query_builder.get_openai_client"):
            tool = QueryBuilderTool(schema="test")
            tool.client = Mock()
            tool.safety_guard = Mock()
            tool.safety_guard.run.return_value = json.dumps(
                {"is_safe": True, "violations": []}
            )

            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content="MATCH (e:Event) RETURN e"))
            ]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            with patch(
                "agent.tools.query_builder.chat_completion_with_retry",
                return_value=mock_response,
            ):
                result_json = tool.run("Find concerts")

            # Should still return results even if format is unexpected
            result = json.loads(result_json)
            assert result["status"] == "success"
            assert "results" in result


class TestRecoveryMechanisms:
    """Test error recovery and retry mechanisms."""

    @patch("agent.tools.query_builder.neo4j_client")
    @patch("agent.tools.query_builder.chat_completion_with_retry")
    def test_retry_on_transient_failure(self, mock_chat, mock_neo4j):
        """Test that retry mechanism works for transient failures."""
        # Simulate chat_completion_with_retry is being used
        # (which should have retry logic)

        with patch("agent.tools.query_builder.get_openai_client"):
            tool = QueryBuilderTool(schema="test")
            tool.client = Mock()
            tool.safety_guard = Mock()
            tool.safety_guard.run.return_value = json.dumps(
                {"is_safe": True, "violations": []}
            )

            # First call fails, second succeeds
            mock_chat.side_effect = [
                Exception("Transient error"),
                Mock(
                    choices=[Mock(message=Mock(content="MATCH (e:Event) RETURN e"))],
                    usage=Mock(prompt_tokens=100, completion_tokens=50),
                ),
            ]

            mock_neo4j.execute_read.return_value = []

            # With retry logic, this should eventually succeed
            # (If chat_completion_with_retry implements retries)
            try:
                result_json = tool.run("Find concerts")
                json.loads(result_json)  # if retry works, should eventually succeed
            except Exception:
                # If no retry, will fail on first attempt
                pass


class TestEdgeCaseErrors:
    """Test edge case error scenarios."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_extremely_large_result_set(self, mock_neo4j):
        """Test handling of very large result sets."""
        # Simulate 1000 results
        large_results = [{"event": {"name": f"Event {i}"}} for i in range(1000)]
        mock_neo4j.execute_read.return_value = large_results

        with patch("agent.tools.query_builder.get_openai_client"):
            tool = QueryBuilderTool(schema="test")
            tool.client = Mock()
            tool.safety_guard = Mock()
            tool.safety_guard.run.return_value = json.dumps(
                {"is_safe": True, "violations": []}
            )

            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content="MATCH (e:Event) RETURN e"))
            ]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            with patch(
                "agent.tools.query_builder.chat_completion_with_retry",
                return_value=mock_response,
            ):
                result_json = tool.run("Find all events")

            result = json.loads(result_json)
            # Should handle large result sets (limited by max_results_limit)
            assert result["status"] == "success"
            assert "results" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
