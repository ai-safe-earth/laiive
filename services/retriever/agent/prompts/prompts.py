"""
Prompt registry for the retriever agent.

Prompts are defined in the files that use them, co-located with the code for
readability. This module imports and re-exports all of them so they can be
discovered, versioned, and managed from one place.

Ownership:
  REACT_SYSTEM_PROMPT    → agent/orchestrator.py
  UNSAFE_CONTENT_PROMPT  → agent/orchestrator.py
  QUERY_BUILDER_PROMPT   → agent/tools/query_builder.py
  SAFETY_GUARD_PROMPT    → agent/tools/safety_guard.py
"""

from agent.orchestrator import (
    REACT_SYSTEM_PROMPT,
    UNSAFE_CONTENT_PROMPT,
)
from agent.tools.query_builder import QUERY_BUILDER_PROMPT
from agent.tools.safety_guard import SAFETY_GUARD_PROMPT

__all__ = [
    "REACT_SYSTEM_PROMPT",
    "UNSAFE_CONTENT_PROMPT",
    "QUERY_BUILDER_PROMPT",
    "SAFETY_GUARD_PROMPT",
]
