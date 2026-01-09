import json
import re
from typing import Dict, Any
from .base import Tool
from openai import OpenAI
from config import settings


class SafetyGuardTool(Tool):
    """Tool for validating Cypher queries and content safety using multiple validation methods."""

    name: str = "validate_query_safety"
    description: str = "Validates that a Cypher query contains only read operations and is safe to execute. Use this to check queries before execution."
    arg: str = "The Cypher query string to validate for safety"

    # OpenRouter client for LlamaGuard
    _client = None
    LLAMAGUARD_MODEL = "meta-llama/llama-guard-3-8b"

    @property
    def client(self) -> OpenAI:
        """Lazy initialization of OpenRouter client."""
        if self._client is None:
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
            )
        return self._client

    def run(self, prompt: str) -> str:
        """Validate a Cypher query for safety."""
        is_safe, violations = self.validate_read_only(prompt)

        result = {
            "is_safe": is_safe,
            "message": "Query is safe" if is_safe else f"Query contains forbidden operations: {', '.join(violations)}",
            "violations": violations
        }

        return json.dumps(result)

    def validate_read_only(self, cypher: str) -> tuple[bool, list[str]]:
        """
        Enhanced validation for read-only Cypher queries.
        Returns (is_safe, list_of_violations).
        """
        violations = []

        # Remove comments and strings to avoid false positives
        cleaned_query = self._remove_comments_and_strings(cypher)
        upper_query = cleaned_query.upper()

        # Check for forbidden write operations with word boundaries
        forbidden_patterns = [
            (r'\bCREATE\b', "CREATE"),
            (r'\bDELETE\b', "DELETE"),
            (r'\bMERGE\b', "MERGE"),
            (r'\bSET\b', "SET"),
            (r'\bREMOVE\b', "REMOVE"),
            (r'\bDROP\b', "DROP"),
            (r'\bDETACH\s+DELETE\b', "DETACH DELETE"),
        ]

        for pattern, keyword in forbidden_patterns:
            if re.search(pattern, upper_query):
                violations.append(keyword)

        # Check for dangerous APOC procedures
        dangerous_apoc = [
            r'apoc\.export',
            r'apoc\.import',
            r'apoc\.trigger',
            r'apoc\.periodic\.commit',
            r'apoc\.cypher\.runFile',
            r'apoc\.load\.driver',
        ]

        for pattern in dangerous_apoc:
            if re.search(pattern, cypher, re.IGNORECASE):
                violations.append(f"Dangerous APOC procedure: {pattern}")

        is_safe = len(violations) == 0
        return is_safe, violations

    def _remove_comments_and_strings(self, cypher: str) -> str:
        """Remove comments and string literals to avoid false positives."""
        # Remove single-line comments
        cypher = re.sub(r'//.*?$', '', cypher, flags=re.MULTILINE)

        # Remove multi-line comments
        cypher = re.sub(r'/\*.*?\*/', '', cypher, flags=re.DOTALL)

        # Remove string literals (both single and double quotes)
        cypher = re.sub(r"'[^']*'", "''", cypher)
        cypher = re.sub(r'"[^"]*"', '""', cypher)

        return cypher

    def validate_input_safety(self, user_input: str) -> Dict[str, Any]:
        """
        Validate user input using LlamaGuard.
        Returns dict with verdict and categories.
        """
        try:
            result = self.llamaguard_classify(user_input, mode="input")
            parsed = self._parse_llamaguard_response(result)
            return parsed
        except Exception as e:
            # If LlamaGuard fails, default to safe
            return {
                "verdict": "safe",
                "categories": [],
                "error": str(e)
            }

    def validate_output_safety(self, output_text: str) -> Dict[str, Any]:
        """
        Validate LLM output using LlamaGuard.
        Returns dict with verdict and categories.
        """
        try:
            result = self.llamaguard_classify(output_text, mode="output")
            parsed = self._parse_llamaguard_response(result)
            return parsed
        except Exception as e:
            # If LlamaGuard fails, default to safe
            return {
                "verdict": "safe",
                "categories": [],
                "error": str(e)
            }

    def llamaguard_classify(self, text: str, mode: str = "input") -> str:
        """
        Use LlamaGuard to classify text as safe or unsafe.
        Mode can be 'input' (user messages) or 'output' (AI responses).
        """
        prompt = f"""You are a safety classifier. Classify the following {mode} as SAFE or UNSAFE.
If UNSAFE, list the violated categories.
Return a compact JSON object exactly like:
{{"verdict":"safe"}} or {{"verdict":"unsafe","categories":["category1","category2"]}}

TEXT:
{text}
""".strip()

        resp = self.client.chat.completions.create(
            model=self.LLAMAGUARD_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return resp.choices[0].message.content

    def _parse_llamaguard_response(self, response: str) -> Dict[str, Any]:
        """Parse LlamaGuard JSON response."""
        try:
            data = json.loads(response)
            return {
                "verdict": data.get("verdict", "safe").lower(),
                "categories": data.get("categories", []),
            }
        except json.JSONDecodeError:
            # Fallback parsing if not JSON
            response_lower = response.lower()
            if "unsafe" in response_lower:
                return {"verdict": "unsafe", "categories": ["unknown"]}
            return {"verdict": "safe", "categories": []}
