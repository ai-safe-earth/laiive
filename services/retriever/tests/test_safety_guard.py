"""
Tests for SafetyGuardTool - Cypher query validation and content moderation.
"""
import json
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.tools.safety_guard import SafetyGuardTool


class TestCypherValidation:
    """Test Cypher query safety validation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.tool = SafetyGuardTool()

    def test_safe_read_query(self):
        """Test that safe read-only queries pass validation."""
        safe_queries = [
            "MATCH (n:Event) RETURN n LIMIT 10",
            "MATCH (e:Event)-[:AT_VENUE]->(v:Venue) WHERE v.city = 'Berlin' RETURN e, v",
            "OPTIONAL MATCH (a:Artist)-[:PERFORMS_AT]->(e:Event) RETURN a, e",
            "MATCH (n) WHERE n.name = 'Test' RETURN n",
        ]

        for query in safe_queries:
            result_json = self.tool.run(query)
            result = json.loads(result_json)
            assert result["is_safe"] is True, f"Query should be safe: {query}"
            assert result["violations"] == []

    def test_unsafe_create_query(self):
        """Test that CREATE queries are blocked."""
        unsafe_query = "CREATE (n:Event {name: 'Test'}) RETURN n"
        result_json = self.tool.run(unsafe_query)
        result = json.loads(result_json)

        assert result["is_safe"] is False
        assert "CREATE" in result["violations"]

    def test_unsafe_delete_query(self):
        """Test that DELETE queries are blocked."""
        unsafe_queries = [
            "MATCH (n:Event) DELETE n",
            "MATCH (n) DETACH DELETE n",
        ]

        for query in unsafe_queries:
            result_json = self.tool.run(query)
            result = json.loads(result_json)
            assert result["is_safe"] is False
            assert any(v in ["DELETE", "DETACH DELETE"] for v in result["violations"])

    def test_unsafe_merge_query(self):
        """Test that MERGE queries are blocked."""
        unsafe_query = "MERGE (n:Event {id: 1}) RETURN n"
        result_json = self.tool.run(unsafe_query)
        result = json.loads(result_json)

        assert result["is_safe"] is False
        assert "MERGE" in result["violations"]

    def test_unsafe_set_query(self):
        """Test that SET queries are blocked."""
        unsafe_query = "MATCH (n:Event) SET n.name = 'Updated' RETURN n"
        result_json = self.tool.run(unsafe_query)
        result = json.loads(result_json)

        assert result["is_safe"] is False
        assert "SET" in result["violations"]

    def test_unsafe_remove_query(self):
        """Test that REMOVE queries are blocked."""
        unsafe_query = "MATCH (n:Event) REMOVE n.property RETURN n"
        result_json = self.tool.run(unsafe_query)
        result = json.loads(result_json)

        assert result["is_safe"] is False
        assert "REMOVE" in result["violations"]

    def test_unsafe_drop_query(self):
        """Test that DROP queries are blocked."""
        unsafe_query = "DROP INDEX event_name_index"
        result_json = self.tool.run(unsafe_query)
        result = json.loads(result_json)

        assert result["is_safe"] is False
        assert "DROP" in result["violations"]

    def test_query_with_comments(self):
        """Test that comments don't cause false positives."""
        query_with_comment = """
        // This query will CREATE results by matching
        MATCH (n:Event)
        WHERE n.name = 'CREATE EVENT' // Comment with DELETE
        RETURN n
        """
        result_json = self.tool.run(query_with_comment)
        result = json.loads(result_json)

        # Should be safe since CREATE and DELETE are in comments
        assert result["is_safe"] is True

    def test_query_with_strings(self):
        """Test that keywords in strings don't cause false positives."""
        query = """
        MATCH (n:Event)
        WHERE n.description = 'This will CREATE great memories'
        RETURN n
        """
        result_json = self.tool.run(query)
        result = json.loads(result_json)

        # Should be safe since CREATE is in a string
        assert result["is_safe"] is True

    def test_dangerous_apoc_procedures(self):
        """Test that dangerous APOC procedures are blocked."""
        dangerous_queries = [
            "CALL apoc.export.csv.all('file.csv', {})",
            "CALL apoc.import.json('data.json')",
            "CALL apoc.trigger.add('trigger_name', 'MATCH (n) RETURN n', {})",
        ]

        for query in dangerous_queries:
            result_json = self.tool.run(query)
            result = json.loads(result_json)
            assert result["is_safe"] is False
            assert any("APOC" in str(v) for v in result["violations"])

    def test_safe_apoc_procedures(self):
        """Test that safe APOC procedures are allowed."""
        safe_queries = [
            "CALL apoc.help('search')",
            "RETURN apoc.text.join(['a', 'b'], ',')",
            "MATCH (n) RETURN apoc.node.labels(n)",
        ]

        for query in safe_queries:
            result_json = self.tool.run(query)
            result = json.loads(result_json)
            assert result["is_safe"] is True

    def test_multiple_violations(self):
        """Test query with multiple violations."""
        unsafe_query = "CREATE (n:Event) SET n.name = 'Test' DELETE n"
        result_json = self.tool.run(unsafe_query)
        result = json.loads(result_json)

        assert result["is_safe"] is False
        assert "CREATE" in result["violations"]
        assert "SET" in result["violations"]
        assert "DELETE" in result["violations"]


class TestLlamaGuardIntegration:
    """Test LlamaGuard content moderation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.tool = SafetyGuardTool()

    @patch.object(SafetyGuardTool, 'llamaguard_classify')
    def test_input_validation_safe(self, mock_classify):
        """Test safe user input validation."""
        mock_classify.return_value = '{"verdict": "safe"}'

        result = self.tool.validate_input_safety("Find concerts in Berlin this weekend")

        assert result["verdict"] == "safe"
        assert result["categories"] == []
        mock_classify.assert_called_once()

    @patch.object(SafetyGuardTool, 'llamaguard_classify')
    def test_input_validation_unsafe(self, mock_classify):
        """Test unsafe user input validation."""
        mock_classify.return_value = '{"verdict": "unsafe", "categories": ["violence", "hate"]}'

        result = self.tool.validate_input_safety("Harmful content here")

        assert result["verdict"] == "unsafe"
        assert "violence" in result["categories"]
        assert "hate" in result["categories"]

    @patch.object(SafetyGuardTool, 'llamaguard_classify')
    def test_output_validation_safe(self, mock_classify):
        """Test safe output validation."""
        mock_classify.return_value = '{"verdict": "safe"}'

        result = self.tool.validate_output_safety("I found 5 great concerts for you!")

        assert result["verdict"] == "safe"
        mock_classify.assert_called_once()

    @patch.object(SafetyGuardTool, 'llamaguard_classify')
    def test_output_validation_unsafe(self, mock_classify):
        """Test unsafe output validation."""
        mock_classify.return_value = '{"verdict": "unsafe", "categories": ["harmful_content"]}'

        result = self.tool.validate_output_safety("Problematic response")

        assert result["verdict"] == "unsafe"
        assert "harmful_content" in result["categories"]

    @patch.object(SafetyGuardTool, 'llamaguard_classify')
    def test_llamaguard_error_handling(self, mock_classify):
        """Test that LlamaGuard errors default to safe."""
        mock_classify.side_effect = Exception("API Error")

        result = self.tool.validate_input_safety("Find jazz concerts")

        # Should default to safe on error
        assert result["verdict"] == "safe"
        assert "error" in result

    def test_parse_llamaguard_response_json(self):
        """Test parsing valid JSON response."""
        response = '{"verdict": "unsafe", "categories": ["spam", "fraud"]}'
        result = self.tool._parse_llamaguard_response(response)

        assert result["verdict"] == "unsafe"
        assert result["categories"] == ["spam", "fraud"]

    def test_parse_llamaguard_response_invalid_json(self):
        """Test parsing invalid JSON falls back gracefully."""
        response = "unsafe content detected"
        result = self.tool._parse_llamaguard_response(response)

        assert result["verdict"] == "unsafe"
        assert result["categories"] == ["unknown"]

    def test_parse_llamaguard_response_safe_text(self):
        """Test parsing safe text response."""
        response = "The content is safe"
        result = self.tool._parse_llamaguard_response(response)

        assert result["verdict"] == "safe"


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def setup_method(self):
        """Setup test fixtures."""
        self.tool = SafetyGuardTool()

    def test_empty_query(self):
        """Test empty query handling."""
        result_json = self.tool.run("")
        result = json.loads(result_json)

        assert result["is_safe"] is True

    def test_whitespace_only_query(self):
        """Test whitespace-only query."""
        result_json = self.tool.run("   \n\t   ")
        result = json.loads(result_json)

        assert result["is_safe"] is True

    def test_case_insensitive_validation(self):
        """Test that validation is case-insensitive."""
        queries = [
            "create (n:Event) return n",
            "CrEaTe (n:Event) ReTuRn n",
            "CREATE (n:Event) RETURN n",
        ]

        for query in queries:
            result_json = self.tool.run(query)
            result = json.loads(result_json)
            assert result["is_safe"] is False
            assert "CREATE" in result["violations"]

    def test_multiline_query(self):
        """Test multiline query validation."""
        query = """
        MATCH (e:Event)
        WHERE e.start_at > datetime()
        RETURN e.name, e.start_at
        ORDER BY e.start_at
        LIMIT 10
        """
        result_json = self.tool.run(query)
        result = json.loads(result_json)

        assert result["is_safe"] is True

    def test_query_with_nested_keywords(self):
        """Test that nested keywords in property names don't trigger false positives."""
        query = "MATCH (n:Event) WHERE n.created_at > datetime() RETURN n"
        result_json = self.tool.run(query)
        result = json.loads(result_json)

        # 'created_at' contains 'CREATE' but should be safe
        assert result["is_safe"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
