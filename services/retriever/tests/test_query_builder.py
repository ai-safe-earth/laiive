"""
Unit tests for QueryBuilderTool - Cypher generation, date handling, and safety validation.
Run with: pytest tests/test_query_builder.py -v
"""

import pytest
from unittest.mock import Mock, patch
import json
from agent.tools.query_builder import QueryBuilderTool


@pytest.fixture
def mock_schema():
    """Mock database schema."""
    return """
    Nodes:
    - Event (name, description, start_at, price_amount, price_currency, ticket_url)
    - Artist (name, genre, embedding)
    - Venue (name, city, address)

    Relationships:
    - (Artist)-[:PERFORMS_AT]->(Event)
    - (Event)-[:AT_VENUE]->(Venue)
    """


@pytest.fixture
def query_builder(mock_schema):
    """Create QueryBuilderTool instance with mocked dependencies."""
    with patch("agent.tools.query_builder.get_openai_client"):
        tool = QueryBuilderTool(schema=mock_schema)
        tool.client = Mock()
        tool.safety_guard = Mock()
        yield tool


class TestCypherGeneration:
    """Test Cypher query generation."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_generate_cypher_basic_query(self, mock_neo4j, query_builder):
        """Test basic Cypher query generation."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = [{"event": {"name": "Jazz Night"}}]

        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="MATCH (e:Event) RETURN e LIMIT 10"))
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("Find jazz concerts in Berlin")

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert "MATCH" in result["cypher"]
        assert result["results"] is not None

    @patch("agent.tools.query_builder.neo4j_client")
    def test_unsafe_cypher_rejected(self, mock_neo4j, query_builder):
        """Test that unsafe Cypher queries are rejected."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {
                "is_safe": False,
                "violations": ["CREATE", "DELETE"],
                "message": "Query rejected: contains forbidden operations",
            }
        )

        # Mock LLM generating unsafe query
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="CREATE (n:Event) DELETE n"))
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("Malicious query")

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "rejected" in result["error"].lower()

    @patch("agent.tools.query_builder.neo4j_client")
    def test_cypher_with_date_context(self, mock_neo4j, query_builder):
        """Test that date context is properly included in Cypher generation."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content='MATCH (e:Event) WHERE datetime(e.start_at) >= datetime("2026-01-15T00:00:00Z") RETURN e'
                )
            )
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ) as mock_llm:
            date_info = {
                "today": "2026-01-15",
                "reference_time": "2026-01-15T10:00:00Z",
            }
            query_builder.run("Find concerts today", date_info=date_info)

            # Verify date context was passed to LLM
            call_args = mock_llm.call_args
            messages = call_args[1]["messages"]
            system_prompt = messages[0]["content"]

            assert "2026-01-15" in system_prompt

    @patch("agent.tools.query_builder.neo4j_client")
    def test_cypher_generation_error_handling(self, mock_neo4j, query_builder):
        """Test error handling during Cypher generation."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        # Mock LLM failure
        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            side_effect=Exception("LLM timeout"),
        ):
            result_json = query_builder.run("Find concerts")

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "LLM timeout" in result["error"]


class TestDateHandling:
    """Test date parsing and formatting."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_date_handling_datetime_format(self, mock_neo4j, query_builder):
        """Test that dates are formatted as datetime in Cypher."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        # Mock LLM response with proper datetime format
        cypher_with_datetime = 'MATCH (e:Event) WHERE datetime(e.start_at) >= datetime("2026-01-15T00:00:00Z") RETURN e'
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=cypher_with_datetime))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("Find concerts on January 15, 2026")

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert "datetime(" in result["cypher"]
        assert "Z" in result["cypher"]  # ISO-8601 with Z suffix


class TestQueryExecution:
    """Test query execution against Neo4j."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_query_execution_success(self, mock_neo4j, query_builder):
        """Test successful query execution."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        expected_results = [
            {"event": {"name": "Jazz Night", "start_at": "2026-01-15T20:00:00Z"}},
            {"event": {"name": "Rock Show", "start_at": "2026-01-16T21:00:00Z"}},
        ]
        mock_neo4j.execute_read.return_value = expected_results

        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="MATCH (e:Event) RETURN e LIMIT 2"))
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("Find 2 concerts")

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert len(result["results"]) == 2
        assert result["results"][0]["event"] == expected_results[0]["event"]
        assert result["results"][1]["event"] == expected_results[1]["event"]

    @patch("agent.tools.query_builder.neo4j_client")
    def test_query_execution_empty_results(self, mock_neo4j, query_builder):
        """Test query with no results."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="MATCH (e:Event) WHERE false RETURN e"))
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("Find impossible events")

        result = json.loads(result_json)
        assert result["status"] == "success"
        assert result["results"] == []

    @patch("agent.tools.query_builder.neo4j_client")
    def test_query_execution_neo4j_error(self, mock_neo4j, query_builder):
        """Test Neo4j execution error handling."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.side_effect = Exception("Connection lost")

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="MATCH (e:Event) RETURN e"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("Find concerts")

        result = json.loads(result_json)
        assert result["status"] == "error"
        assert "Connection lost" in result["error"]


class TestSchemaIntegration:
    """Test schema integration and validation."""

    def test_tool_initialized_with_schema(self, query_builder, mock_schema):
        """Test that tool is initialized with schema."""
        assert query_builder.db_schema == mock_schema

    @patch("agent.tools.query_builder.neo4j_client")
    def test_schema_included_in_llm_prompt(self, mock_neo4j, query_builder):
        """Test that schema is included in LLM prompt."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="MATCH (e:Event) RETURN e"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_embedding_response = Mock()
        mock_embedding_response.data = [Mock(embedding=[0.1] * 1536)]

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ) as mock_llm:
            query_builder.run("Find concerts")

            # Verify schema was passed to LLM
            call_args = mock_llm.call_args
            messages = call_args[1]["messages"]
            system_prompt = messages[0]["content"]

            assert "Schema:" in system_prompt
            assert "Event" in system_prompt
            assert "Artist" in system_prompt
            assert "Venue" in system_prompt


class TestPromptEngineering:
    """Test prompt construction and rules."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_date_context_injected_into_prompt(self, mock_neo4j, query_builder):
        """Test that current date is injected into prompt."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="MATCH (e:Event) RETURN e"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ) as mock_llm:
            query_builder.run("Find concerts today")

            call_args = mock_llm.call_args
            messages = call_args[1]["messages"]
            system_prompt = messages[0]["content"]

            # Should contain today's date
            assert "Current date:" in system_prompt


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("agent.tools.query_builder.neo4j_client")
    def test_empty_query_string(self, mock_neo4j, query_builder):
        """Test handling of empty query string."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="MATCH (e:Event) RETURN e LIMIT 10"))
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("")

        result = json.loads(result_json)
        # Should handle gracefully
        assert result["status"] in ["success", "error"]

    @patch("agent.tools.query_builder.neo4j_client")
    def test_very_long_query(self, mock_neo4j, query_builder):
        """Test handling of very long query string."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="MATCH (e:Event) RETURN e"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        long_query = "Find concerts " + " and ".join(["in Berlin"] * 100)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run(long_query)

        result = json.loads(result_json)
        assert result["status"] in ["success", "error"]

    @patch("agent.tools.query_builder.neo4j_client")
    def test_special_characters_in_query(self, mock_neo4j, query_builder):
        """Test handling of special characters."""
        query_builder.safety_guard.run.return_value = json.dumps(
            {"is_safe": True, "violations": []}
        )

        mock_neo4j.execute_read.return_value = []

        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="MATCH (e:Event) WHERE e.name CONTAINS \"Rock'n'Roll\" RETURN e"
                )
            )
        ]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            return_value=mock_response,
        ):
            result_json = query_builder.run("Find Rock'n'Roll concerts")

        result = json.loads(result_json)
        assert result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
