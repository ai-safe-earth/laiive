"""Safety: OpenAI moderation for content, regex guard for generated Cypher.

The OpenRouter/LlamaGuard layer is gone (05-decisions R3): a client bug meant
it never actually executed, and OpenAI's moderation endpoint is free and in
the SDK we already use.
"""

import json
import re

from loguru import logger

from ..utils.llm_utils import get_openai_client


class SafetyGuardTool:
    """Validates Cypher for read-only-ness and user content via moderation."""

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = get_openai_client()
        return self._client

    # ── Cypher guard (regex, no LLM) ────────────────────────────────────────

    def run(self, cypher: str | None) -> str:
        """Validate a Cypher query for safety. Returns a JSON verdict."""
        if cypher is None:
            return json.dumps(
                {
                    "is_safe": False,
                    "message": "Null query provided",
                    "violations": ["null_query"],
                }
            )
        is_safe, violations = self.validate_read_only(cypher)
        return json.dumps(
            {
                "is_safe": is_safe,
                "message": (
                    "Query is safe"
                    if is_safe
                    else f"Query contains forbidden operations: {', '.join(violations)}"
                ),
                "violations": violations,
            }
        )

    def validate_read_only(self, cypher: str) -> tuple[bool, list[str]]:
        """Returns (is_safe, violations) for a generated Cypher query."""
        violations = []
        cleaned = self._remove_comments_and_strings(cypher)
        upper = cleaned.upper()

        forbidden = [
            (r"\bCREATE\b", "CREATE"),
            (r"\bDELETE\b", "DELETE"),
            (r"\bMERGE\b", "MERGE"),
            (r"\bSET\b", "SET"),
            (r"\bREMOVE\b", "REMOVE"),
            (r"\bDROP\b", "DROP"),
            (r"\bDETACH\s+DELETE\b", "DETACH DELETE"),
        ]
        for pattern, keyword in forbidden:
            if re.search(pattern, upper):
                violations.append(keyword)

        dangerous_apoc = [
            r"apoc\.export",
            r"apoc\.import",
            r"apoc\.trigger",
            r"apoc\.periodic\.commit",
            r"apoc\.cypher\.runFile",
            r"apoc\.load\.driver",
        ]
        for pattern in dangerous_apoc:
            if re.search(pattern, cypher, re.IGNORECASE):
                violations.append(f"Dangerous APOC procedure: {pattern}")

        return len(violations) == 0, violations

    @staticmethod
    def _remove_comments_and_strings(cypher: str) -> str:
        cypher = re.sub(r"//.*?$", "", cypher, flags=re.MULTILINE)
        cypher = re.sub(r"/\*.*?\*/", "", cypher, flags=re.DOTALL)
        cypher = re.sub(r"'[^']*'", "''", cypher)
        cypher = re.sub(r'"[^"]*"', '""', cypher)
        return cypher

    # ── Prompt-injection heuristics (no LLM) ───────────────────────────────

    _INJECTION_PATTERNS = [
        r"\bDETACH\s+DELETE\b",
        r"\bDROP\s+(CONSTRAINT|INDEX|DATABASE)\b",
        r"\bDELETE\s+\w+\b.*\bMATCH\b",
        r"\bMERGE\s*\(",
        r"\bCREATE\s*\(\w*:",
        r"\bSET\s+\w+\.\w+\s*=",
        r"ignore\s+(previous|all|my)\s+instructions",
        r"(raw|actual|real)\s+cypher",
        r"system\s+prompt",
    ]

    def detect_injection(self, user_input: str) -> bool:
        """Heuristic screen for Cypher/prompt injection in user text."""
        return any(
            re.search(p, user_input, re.IGNORECASE) for p in self._INJECTION_PATTERNS
        )

    # ── Content moderation (OpenAI, free endpoint) ─────────────────────────

    def moderate(self, text: str) -> bool:
        """True when the text is flagged. Fails open — search must not die
        because moderation did."""
        try:
            result = self.client.moderations.create(
                model="omni-moderation-latest", input=text[:4000]
            )
            return bool(result.results[0].flagged)
        except Exception as e:
            logger.warning(f"Moderation call failed (continuing unmoderated): {e}")
            return False
