"""
Prompt registry for the retriever agent.

Prompts are defined in the files that use them, co-located with the code for
readability. This module imports and re-exports all of them so they can be
discovered, versioned, and managed from one place.

Ownership:
  CLASSIFIER_SYSTEM_PROMPT → agent/classifier.py
  COMPOSER_SYSTEM_PROMPT   → agent/composer.py
  QUERY_BUILDER_PROMPT     → agent/tools/query_builder.py
"""

from agent.classifier import CLASSIFIER_PROMPT_VERSION, CLASSIFIER_SYSTEM_PROMPT
from agent.composer import COMPOSER_PROMPT_VERSION, COMPOSER_SYSTEM_PROMPT
from agent.tools.query_builder import (
    QUERY_BUILDER_PROMPT,
    QUERY_BUILDER_PROMPT_VERSION,
)

__all__ = [
    "CLASSIFIER_SYSTEM_PROMPT",
    "CLASSIFIER_PROMPT_VERSION",
    "COMPOSER_SYSTEM_PROMPT",
    "COMPOSER_PROMPT_VERSION",
    "QUERY_BUILDER_PROMPT",
    "QUERY_BUILDER_PROMPT_VERSION",
]
