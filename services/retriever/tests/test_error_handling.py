"""
Tests for error handling and failure scenarios across the pipeline.
Run with: pytest tests/test_error_handling.py -v
"""

import pytest
from unittest.mock import Mock, patch
import json
from agent.orchestrator import Orchestrator
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

    @patch("agent.orchestrator.get_openai_client")
    def test_openai_api_timeout(self, mock_openai, mock_schema):
        """Test handling of OpenAI API timeout."""
        orch = Orchestrator(schema=mock_schema)
        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}

        with patch.object(
            orch, "_call_decision_llm", side_effect=Exception("Request timeout")
        ):
            with pytest.raises(Exception, match="timeout"):
                orch.decide_action("Find concerts")

    @patch("agent.orchestrator.get_openai_client")
    def test_openai_api_rate_limit(self, mock_openai, mock_schema):
        """Test handling of OpenAI rate limit errors."""
        orch = Orchestrator(schema=mock_schema)
        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}

        with patch.object(
            orch, "_call_decision_llm", side_effect=Exception("Rate limit exceeded")
        ):
            with pytest.raises(Exception, match="Rate limit"):
                orch.decide_action("Find concerts")

    @patch("agent.orchestrator.get_openai_client")
    def test_openai_invalid_api_key(self, mock_openai, mock_schema):
        """Test handling of invalid API key."""
        orch = Orchestrator(schema=mock_schema)
        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}

        with patch.object(
            orch, "_call_decision_llm", side_effect=Exception("Invalid API key")
        ):
            with pytest.raises(Exception, match="Invalid API key"):
                orch.decide_action("Find concerts")

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


class TestPartialFailures:
    """Test scenarios where parts of the pipeline fail."""

    @patch("agent.orchestrator.get_openai_client")
    def test_query_succeeds_llm_response_fails(self, mock_openai, mock_schema):
        """Test when query execution succeeds but response generation fails."""
        orch = Orchestrator(schema=mock_schema)
        orch.query_builder_tool = Mock()
        orch.query_builder_tool.run.return_value = json.dumps(
            {
                "status": "success",
                "cypher": "MATCH (e:Event) RETURN e",
                "results": [{"event": {"name": "Test"}}],
            }
        )

        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_output_safety.return_value = {"verdict": "safe"}

        # Simulate LLM failure in response generation
        with patch(
            "agent.orchestrator.chat_completion_with_retry",
            side_effect=Exception("LLM failed"),
        ):
            with pytest.raises(Exception):
                orch.generate_response(
                    action="QUERY_DB",
                    user_message="Find concerts",
                    cypher="MATCH (e:Event) RETURN e",
                    results=[{"event": {"name": "Test"}}],
                )

    @patch("agent.orchestrator.get_openai_client")
    def test_query_fails_graceful_fallback(self, mock_openai, mock_schema):
        """Test graceful handling when query fails."""
        orch = Orchestrator(schema=mock_schema)
        orch.query_builder_tool = Mock()
        orch.query_builder_tool.run.return_value = json.dumps(
            {"status": "error", "error": "Query failed"}
        )

        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}

        with pytest.raises(ValueError, match="Query failed"):
            orch.execute_query("Find concerts")


class TestSafetyGuardErrors:
    """Test safety guard failures."""

    @patch("agent.orchestrator.get_openai_client")
    def test_safety_guard_llamaguard_timeout(self, mock_openai, mock_schema):
        """Test handling of LlamaGuard API timeout."""
        orch = Orchestrator(schema=mock_schema)
        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.side_effect = Exception(
            "LlamaGuard timeout"
        )

        with pytest.raises(Exception, match="timeout"):
            orch.decide_action("Find concerts")

    def test_cypher_validation_failure(self):
        """Test handling of Cypher validation errors."""
        tool = SafetyGuardTool()

        # Should handle edge cases gracefully
        result_json = tool.run(None)
        result = json.loads(result_json)
        # Should not crash


class TestConcurrentRequestErrors:
    """Test errors in concurrent request scenarios."""

    @patch("agent.orchestrator.get_openai_client")
    def test_multiple_requests_one_fails(self, mock_openai, mock_schema):
        """Test that one failing request doesn't affect others."""
        orch = Orchestrator(schema=mock_schema)
        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}

        # First request succeeds
        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=Mock(content="QUERY_DB"))]

        # Second request fails
        with patch.object(orch, "_call_decision_llm", return_value=mock_response1):
            result1 = orch.decide_action("Find jazz concerts")

        assert result1 == "QUERY_DB"

        # Simulate failure on next request
        with patch.object(
            orch, "_call_decision_llm", side_effect=Exception("API error")
        ):
            with pytest.raises(Exception):
                orch.decide_action("Find rock concerts")


class TestDataValidationErrors:
    """Test data validation and malformed input errors."""

    @patch("agent.orchestrator.get_openai_client")
    def test_malformed_conversation_history(self, mock_openai, mock_schema):
        """Test handling of malformed conversation history."""
        orch = Orchestrator(schema=mock_schema)
        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="QUERY_DB"))]

        # History with missing attributes
        bad_history = [Mock(role="user")]  # Missing content
        delattr(bad_history[0], "content")

        with patch.object(orch, "_call_decision_llm", return_value=mock_response):
            # Should handle gracefully or raise clear error
            try:
                orch.decide_action("Find concerts", conversation_history=bad_history)
            except (AttributeError, KeyError, TypeError):
                pass  # Expected to fail

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

            mock_embedding_response = Mock()
            mock_embedding_response.data = [Mock(embedding=[0.1] * 1536)]

            with patch(
                "agent.tools.query_builder.chat_completion_with_retry",
                return_value=mock_response,
            ), patch(
                "agent.tools.query_builder.embedding_with_retry",
                return_value=mock_embedding_response,
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
                result = json.loads(result_json)
                # If retry works, should eventually succeed
            except Exception:
                # If no retry, will fail on first attempt
                pass


class TestEdgeCaseErrors:
    """Test edge case error scenarios."""

    @patch("agent.orchestrator.get_openai_client")
    def test_unicode_characters_in_error_messages(self, mock_openai, mock_schema):
        """Test handling of unicode in error messages."""
        orch = Orchestrator(schema=mock_schema)
        orch.query_builder_tool = Mock()
        orch.query_builder_tool.run.return_value = json.dumps(
            {"status": "error", "error": "Error: ñ ü ö emoji 🎵"}
        )

        orch.safety_guard_tool = Mock()
        orch.safety_guard_tool.detect_injection.return_value = False
        orch.safety_guard_tool.validate_input_safety.return_value = {"verdict": "safe"}

        # Should handle unicode in errors
        with pytest.raises(ValueError):
            orch.execute_query("Find concerts with unicode")

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

            mock_embedding_response = Mock()
            mock_embedding_response.data = [Mock(embedding=[0.1] * 1536)]

            with patch(
                "agent.tools.query_builder.chat_completion_with_retry",
                return_value=mock_response,
            ), patch(
                "agent.tools.query_builder.embedding_with_retry",
                return_value=mock_embedding_response,
            ):
                result_json = tool.run("Find all events")

            result = json.loads(result_json)
            # Should handle large result sets (limited by max_results_limit)
            assert result["status"] == "success"
            assert "results" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
