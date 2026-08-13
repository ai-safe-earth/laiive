"""
Unit tests for QueryBuilderTool — Cypher generation, safety validation,
execution, and prompt content. All LLM/Neo4j calls mocked.
"""

import json
from unittest.mock import Mock, patch

import pytest

from agent.tools.query_builder import QueryBuilderTool

MOCK_SCHEMA = "# Node Labels\n- Event\n- Artist\n- Venue\n- City\n- Genre"


def make_tool(schema: str = MOCK_SCHEMA) -> QueryBuilderTool:
    tool = QueryBuilderTool(neo4j_client=Mock(), schema=schema, client=Mock())
    return tool


def mock_llm(cypher: str):
    response = Mock()
    response.choices = [Mock(message=Mock(content=cypher))]
    return patch(
        "agent.tools.query_builder.chat_completion_with_retry", return_value=response
    )


class TestCypherGeneration:
    def test_basic_query_success(self):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = [{"name": "Jazz Night"}]
        with mock_llm("MATCH (e:Event) RETURN e LIMIT 10"):
            data = json.loads(tool.run("Find jazz concerts in Berlin"))
        assert data["status"] == "success"
        assert data["cypher"] == "MATCH (e:Event) RETURN e LIMIT 10"
        assert data["result_count"] == 1

    def test_markdown_fences_stripped(self):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = []
        with mock_llm("```cypher\nMATCH (e:Event) RETURN e\n```"):
            data = json.loads(tool.run("anything"))
        assert data["cypher"] == "MATCH (e:Event) RETURN e"

    def test_unsafe_cypher_rejected(self):
        tool = make_tool()
        with mock_llm("MATCH (e:Event) DETACH DELETE e"):
            data = json.loads(tool.run("delete everything"))
        assert data["status"] == "error"
        assert "safety" in data["error"].lower()
        tool.neo4j.execute_read.assert_not_called()

    def test_generation_error_returns_error_json(self):
        tool = make_tool()
        with patch(
            "agent.tools.query_builder.chat_completion_with_retry",
            side_effect=Exception("LLM down"),
        ):
            data = json.loads(tool.run("find events"))
        assert data["status"] == "error"
        assert data["results"] == []


class TestQueryExecution:
    def test_empty_results(self):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = []
        with mock_llm("MATCH (e:Event) RETURN e"):
            data = json.loads(tool.run("events on the moon"))
        assert data["status"] == "success"
        assert data["result_count"] == 0

    def test_neo4j_error_surfaces_as_error_json(self):
        tool = make_tool()
        tool.neo4j.execute_read.side_effect = Exception("Connection timeout")
        with mock_llm("MATCH (e:Event) RETURN e"):
            data = json.loads(tool.run("find events"))
        assert data["status"] == "error"
        assert "timeout" in data["error"].lower()

    def test_results_capped_at_limit(self):
        from config import settings

        tool = make_tool()
        tool.neo4j.execute_read.return_value = [{"i": i} for i in range(50)]
        with mock_llm("MATCH (e:Event) RETURN e"):
            data = json.loads(tool.run("all events"))
        assert len(data["results"]) == settings.max_results_limit


class TestSchemaAndPrompt:
    def test_schema_lazy_loaded_from_neo4j(self):
        neo4j = Mock()
        neo4j.get_schema.return_value = "LIVE SCHEMA"
        tool = QueryBuilderTool(neo4j_client=neo4j, client=Mock())
        assert tool.db_schema == "LIVE SCHEMA"
        neo4j.get_schema.assert_called_once()

    def test_schema_and_date_in_system_prompt(self):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = []
        with mock_llm("MATCH (e:Event) RETURN e") as mocked:
            tool.run("find events")
        system = mocked.call_args.kwargs["messages"][0]["content"]
        assert MOCK_SCHEMA in system
        assert "Today is" in system

    def test_prompt_teaches_new_ontology(self):
        from agent.tools.query_builder import QUERY_BUILDER_PROMPT

        assert "name_norm" in QUERY_BUILDER_PROMPT
        assert "country_code" in QUERY_BUILDER_PROMPT
        assert "PART_OF" not in QUERY_BUILDER_PROMPT  # dead relationship
        assert "collect(DISTINCT art.name) AS artists" in QUERY_BUILDER_PROMPT


class TestEdgeCases:
    @pytest.mark.parametrize(
        "question",
        ["", "x" * 5000, 'events with "quotes" & spëcial chars ñ'],
    )
    def test_odd_inputs_do_not_crash(self, question):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = []
        with mock_llm("MATCH (e:Event) RETURN e"):
            data = json.loads(tool.run(question))
        assert data["status"] in ("success", "error")
