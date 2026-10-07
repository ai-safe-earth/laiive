"""
Unit tests for QueryBuilderTool — Cypher generation, safety validation,
execution, and prompt content. All LLM/Neo4j calls mocked.
"""

from unittest.mock import Mock

import pytest

from agent.tools.query_builder import QueryBuilderTool

MOCK_SCHEMA = "# Node Labels\n- Event\n- Artist\n- Venue\n- City\n- Genre"


def make_tool(schema: str = MOCK_SCHEMA) -> QueryBuilderTool:
    tool = QueryBuilderTool(neo4j_client=Mock(), schema=schema, client=Mock())
    return tool


def mock_llm(tool: QueryBuilderTool, cypher: str):
    """Point the tool's injected client at one canned completion.

    The tenacity wrapper this used to patch is gone - the SDK's own retries
    replaced it - so the seam is the client the tool was built with, which
    these tests already pass in. Returns the create() mock, for the tests that
    assert on what was sent.
    """
    response = Mock()
    response.choices = [Mock(message=Mock(content=cypher))]
    create = tool.client.chat.completions.create
    create.return_value = response
    return create


class TestCypherGeneration:
    def test_basic_query_success(self):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = [{"name": "Jazz Night"}]
        mock_llm(tool, "MATCH (e:Event) RETURN e LIMIT 10")
        result = tool.run("Find jazz concerts in Berlin")
        assert not result.error
        assert result.cypher == "MATCH (e:Event) RETURN e LIMIT 10"
        assert len(result.rows) == 1

    def test_markdown_fences_stripped(self):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = []
        mock_llm(tool, "```cypher\nMATCH (e:Event) RETURN e\n```")
        result = tool.run("anything")
        assert result.cypher == "MATCH (e:Event) RETURN e"

    def test_unsafe_cypher_rejected(self):
        tool = make_tool()
        mock_llm(tool, "MATCH (e:Event) DETACH DELETE e")
        result = tool.run("delete everything")
        assert result.error
        assert "safety" in result.error.lower()
        tool.neo4j.execute_read.assert_not_called()

    def test_generation_error_returns_error_json(self):
        tool = make_tool()
        tool.client.chat.completions.create.side_effect = Exception("LLM down")
        result = tool.run("find events")
        assert result.error
        assert result.rows == []


class TestQueryExecution:
    def test_empty_results(self):
        tool = make_tool()
        tool.neo4j.execute_read.return_value = []
        mock_llm(tool, "MATCH (e:Event) RETURN e")
        result = tool.run("events on the moon")
        assert not result.error
        assert result.rows == []

    def test_neo4j_error_surfaces_as_error_json(self):
        tool = make_tool()
        tool.neo4j.execute_read.side_effect = Exception("Connection timeout")
        mock_llm(tool, "MATCH (e:Event) RETURN e")
        result = tool.run("find events")
        assert result.error
        assert "timeout" in result.error.lower()

    def test_results_capped_at_limit(self):
        from config import settings

        tool = make_tool()
        tool.neo4j.execute_read.return_value = [{"i": i} for i in range(50)]
        mock_llm(tool, "MATCH (e:Event) RETURN e")
        result = tool.run("all events")
        assert len(result.rows) == settings.max_results_limit


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
        mocked = mock_llm(tool, "MATCH (e:Event) RETURN e")
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
        mock_llm(tool, "MATCH (e:Event) RETURN e")
        result = tool.run(question)
        assert result.cypher or result.error
