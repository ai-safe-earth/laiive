"""
Unit tests for Orchestrator class - decision making, query execution, and response generation.
Run with: pytest tests/test_orchestrator_unit.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from agent.orchestrator import Orchestrator


@pytest.fixture
def mock_schema():
    """Mock database schema."""
    return """
    Nodes:
    - Event (name, description, start_at, price_amount, price_currency)
    - Artist (name, genre)
    - Venue (name, city, address)

    Relationships:
    - (Artist)-[:PERFORMS_AT]->(Event)
    - (Event)-[:AT_VENUE]->(Venue)
    """


@pytest.fixture
def orchestrator(mock_schema):
    """Create Orchestrator instance with mocked dependencies."""
    with patch('agent.orchestrator.get_openai_client'):
        orch = Orchestrator(schema=mock_schema)
        orch.client = Mock()
        orch.query_builder_tool = Mock()
        orch.safety_guard_tool = Mock()
        yield orch


class TestDecideAction:
    """Test action decision logic."""

    def test_decide_action_injection_detected(self, orchestrator):
        """Test that Cypher/SQL injection attempts are blocked."""
        orchestrator.safety_guard_tool.detect_injection.return_value = True

        result = orchestrator.decide_action("MATCH (n) DELETE n")

        assert result == "UNSAFE_INPUT"
        orchestrator.safety_guard_tool.detect_injection.assert_called_once()

    def test_decide_action_unsafe_content(self, orchestrator):
        """Test that unsafe content is blocked."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "unsafe",
            "categories": ["violence"]
        }

        result = orchestrator.decide_action("harmful message")

        assert result == "UNSAFE_INPUT"

    def test_decide_action_query_db(self, orchestrator):
        """Test QUERY_DB action is selected for valid queries."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="QUERY_DB"))]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response):
            result = orchestrator.decide_action("Find jazz concerts in Berlin")

        assert result == "QUERY_DB"

    def test_decide_action_needs_info(self, orchestrator):
        """Test NEEDS_INFO action for vague queries."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="NEEDS_INFO"))]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response):
            result = orchestrator.decide_action("Show me concerts")

        assert result == "NEEDS_INFO"

    def test_decide_action_out_of_scope(self, orchestrator):
        """Test OUT_OF_SCOPE action for unrelated queries."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="OUT_OF_SCOPE"))]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response):
            result = orchestrator.decide_action("What's the weather like?")

        assert result == "OUT_OF_SCOPE"

    def test_decide_action_bye_message(self, orchestrator):
        """Test BYE_MESSAGE action for goodbyes."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="BYE_MESSAGE"))]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response):
            result = orchestrator.decide_action("Thanks, goodbye!")

        assert result == "BYE_MESSAGE"

    def test_decide_action_with_conversation_history(self, orchestrator):
        """Test that conversation history is passed to LLM."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="QUERY_DB"))]

        history = [
            Mock(role="user", content="Find jazz concerts"),
            Mock(role="assistant", content="I found 5 concerts")
        ]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response) as mock_llm:
            result = orchestrator.decide_action("What about tomorrow?", conversation_history=history)

            # Verify conversation history was included in prompt
            call_args = mock_llm.call_args[0][0]
            assert "Conversation history" in call_args
            assert "Find jazz concerts" in call_args

    def test_decide_action_default_to_query_db(self, orchestrator):
        """Test that unexpected LLM responses default to QUERY_DB."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="UNEXPECTED_RESPONSE"))]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response):
            result = orchestrator.decide_action("Find concerts")

        assert result == "QUERY_DB"


class TestExecuteQuery:
    """Test query execution logic."""

    def test_execute_query_success(self, orchestrator):
        """Test successful query execution."""
        cypher = "MATCH (e:Event) RETURN e LIMIT 5"
        results = [{"event": {"name": "Jazz Night"}}]

        orchestrator.query_builder_tool.run.return_value = json.dumps({
            "status": "success",
            "cypher": cypher,
            "results": results
        })

        returned_cypher, returned_results = orchestrator.execute_query("Find jazz concerts")

        assert returned_cypher == cypher
        assert returned_results == results
        orchestrator.query_builder_tool.run.assert_called_once_with("Find jazz concerts")

    def test_execute_query_error(self, orchestrator):
        """Test query execution error handling."""
        orchestrator.query_builder_tool.run.return_value = json.dumps({
            "status": "error",
            "error": "Invalid query"
        })

        with pytest.raises(ValueError, match="Invalid query"):
            orchestrator.execute_query("Bad query")

    def test_execute_query_empty_results(self, orchestrator):
        """Test query with empty results."""
        orchestrator.query_builder_tool.run.return_value = json.dumps({
            "status": "success",
            "cypher": "MATCH (e:Event) WHERE false RETURN e",
            "results": []
        })

        cypher, results = orchestrator.execute_query("Find nonexistent events")

        assert results == []
        assert cypher is not None


class TestGenerateResponse:
    """Test response generation for different actions."""

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_unsafe_input(self, mock_chat, orchestrator):
        """Test response for UNSAFE_INPUT action — LLM generates a localised reply."""
        mock_chat.return_value = Mock(
            choices=[Mock(message=Mock(content="Sorry, I can't process that."))]
        )

        response, cypher, results, used_query, needs_info = orchestrator.generate_response(
            action="UNSAFE_INPUT",
            user_message="malicious input",
        )

        assert response == "Sorry, I can't process that."
        assert cypher is None
        assert results is None
        assert used_query is False
        assert needs_info is False
        mock_chat.assert_called_once()

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_out_of_scope(self, mock_chat, orchestrator):
        """Test response for OUT_OF_SCOPE action — LLM generates a localised reply."""
        mock_chat.return_value = Mock(
            choices=[Mock(message=Mock(content="I only help with live music events."))]
        )

        response, cypher, results, used_query, needs_info = orchestrator.generate_response(
            action="OUT_OF_SCOPE",
            user_message="What's the weather?",
        )

        assert response == "I only help with live music events."
        assert cypher is None
        assert results is None
        assert used_query is False
        assert needs_info is False
        mock_chat.assert_called_once()

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_needs_info(self, mock_chat, orchestrator):
        """Test response for NEEDS_INFO action."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Where would you like to find events?"))]
        mock_chat.return_value = mock_response

        response, cypher, results, used_query, needs_info = orchestrator.generate_response(
            action="NEEDS_INFO",
            user_message="Find concerts"
        )

        assert "Where would you like to find events?" in response
        assert cypher is None
        assert results is None
        assert used_query is False
        assert needs_info is True

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_query_db_with_results(self, mock_chat, orchestrator):
        """Test response for QUERY_DB with results."""
        orchestrator.safety_guard_tool.validate_output_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="I found some great jazz concerts for you!"))]
        mock_chat.return_value = mock_response

        test_results = [{"event": {"name": "Jazz Night"}}]
        response, cypher, results, used_query, needs_info = orchestrator.generate_response(
            action="QUERY_DB",
            user_message="Find jazz concerts",
            cypher="MATCH (e:Event) RETURN e",
            results=test_results
        )

        assert "I found some great jazz concerts" in response
        assert cypher == "MATCH (e:Event) RETURN e"
        assert results == test_results
        assert used_query is True
        assert needs_info is False

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_query_db_no_results(self, mock_chat, orchestrator):
        """Test response for QUERY_DB with no results."""
        orchestrator.safety_guard_tool.validate_output_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="No events found. Try different criteria."))]
        mock_chat.return_value = mock_response

        response, cypher, results, used_query, needs_info = orchestrator.generate_response(
            action="QUERY_DB",
            user_message="Find impossible events",
            cypher="MATCH (e:Event) WHERE false RETURN e",
            results=[]
        )

        assert "No events found" in response
        assert results == []
        assert used_query is True

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_unsafe_output(self, mock_chat, orchestrator):
        """Test that unsafe LLM output is caught and replaced."""
        orchestrator.safety_guard_tool.validate_output_safety.return_value = {
            "verdict": "unsafe",
            "categories": ["harmful"]
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Unsafe response"))]
        mock_chat.return_value = mock_response

        with patch('agent.orchestrator.settings') as mock_settings:
            mock_settings.conversation_model = "gpt-4o"
            mock_settings.llm_temperature_conversation = 0.7
            mock_settings.results_preview_limit = 5
            mock_settings.enable_output_safety_check = True

            response, _, _, _, _ = orchestrator.generate_response(
                action="QUERY_DB",
                user_message="Find events",
                cypher="MATCH (e:Event) RETURN e",
                results=[{"event": {"name": "Test"}}]
            )

        assert "Unsafe response" not in response
        assert "more careful" in response

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_bye_message(self, mock_chat, orchestrator):
        """Test response for BYE_MESSAGE action."""
        orchestrator.safety_guard_tool.validate_output_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Thanks for using our service! Enjoy the shows!"))]
        mock_chat.return_value = mock_response

        response, cypher, results, used_query, needs_info = orchestrator.generate_response(
            action="BYE_MESSAGE",
            user_message="Goodbye!"
        )

        assert "Thanks for using our service" in response
        assert cypher is None
        assert results is None
        assert used_query is False
        assert needs_info is False

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_with_conversation_history(self, mock_chat, orchestrator):
        """Test that conversation history is included in response generation."""
        orchestrator.safety_guard_tool.validate_output_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Based on what we discussed..."))]
        mock_chat.return_value = mock_response

        history = [
            Mock(role="user", content="Find jazz concerts"),
            Mock(role="assistant", content="I found 5 concerts")
        ]

        response, _, _, _, _ = orchestrator.generate_response(
            action="QUERY_DB",
            user_message="What about tomorrow?",
            conversation_history=history,
            cypher="MATCH ...",
            results=[{"event": {"name": "Test"}}]
        )

        # Verify chat was called
        assert mock_chat.called
        messages = mock_chat.call_args[1]["messages"]

        # Check that history was included
        assert any("Find jazz concerts" in str(msg) for msg in messages)

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_generate_response_large_results_truncated(self, mock_chat, orchestrator):
        """Test that large result sets are truncated in prompt."""
        orchestrator.safety_guard_tool.validate_output_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Found many events"))]
        mock_chat.return_value = mock_response

        # Create 20 results
        large_results = [{"event": {"name": f"Event {i}"}} for i in range(20)]

        with patch('agent.orchestrator.settings') as mock_settings:
            mock_settings.conversation_model = "gpt-4o"
            mock_settings.llm_temperature_conversation = 0.7
            mock_settings.results_preview_limit = 5

            response, _, _, _, _ = orchestrator.generate_response(
                action="QUERY_DB",
                user_message="Find all events",
                cypher="MATCH (e:Event) RETURN e",
                results=large_results
            )

            # Verify truncation message is included in LLM prompt
            call_args = mock_chat.call_args[1]["messages"]
            prompt_text = str(call_args)
            assert "Showing 5 of 20 total events" in prompt_text


class TestSafetyIntegration:
    """Test safety guard integration."""

    def test_input_safety_check_called(self, orchestrator):
        """Test that input safety check is called."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="QUERY_DB"))]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response):
            orchestrator.decide_action("Find concerts")

        orchestrator.safety_guard_tool.validate_input_safety.assert_called_once()

    @patch('agent.orchestrator.chat_completion_with_retry')
    def test_output_safety_check_called(self, mock_chat, orchestrator):
        """Test that output safety check is called when enabled."""
        orchestrator.safety_guard_tool.validate_output_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Safe response"))]
        mock_chat.return_value = mock_response

        with patch('agent.orchestrator.settings') as mock_settings:
            mock_settings.conversation_model = "gpt-4o"
            mock_settings.llm_temperature_conversation = 0.7
            mock_settings.results_preview_limit = 5
            mock_settings.enable_output_safety_check = True

            orchestrator.generate_response(
                action="QUERY_DB",
                user_message="Find concerts",
                cypher="MATCH ...",
                results=[{"event": {"name": "Test"}}]
            )

        orchestrator.safety_guard_tool.validate_output_safety.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_user_message(self, orchestrator):
        """Test handling of empty user message."""
        orchestrator.safety_guard_tool.detect_injection.return_value = False
        orchestrator.safety_guard_tool.validate_input_safety.return_value = {
            "verdict": "safe"
        }

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="NEEDS_INFO"))]

        with patch.object(orchestrator, '_call_decision_llm', return_value=mock_response):
            result = orchestrator.decide_action("")

        assert result in ["NEEDS_INFO", "OUT_OF_SCOPE"]

    def test_unknown_action(self, orchestrator):
        """Test handling of unknown action type."""
        response, cypher, results, used_query, needs_info = orchestrator.generate_response(
            action="UNKNOWN_ACTION",
            user_message="test"
        )

        assert "not sure how to help" in response
        assert cypher is None
        assert results is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
