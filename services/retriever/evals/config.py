"""
Evaluation configuration with prompt versioning support.

This config now references the service's prompt versions for consistency.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime
import sys
from pathlib import Path

# Import service prompts
sys.path.insert(0, str(Path(__file__).parent.parent))
from agent.prompts import QUERY_BUILDER_PROMPTS, DECISION_PROMPTS


class PromptVersion(BaseModel):
    """Version control for prompts."""
    version: str
    name: str
    created_at: str
    description: str
    prompt_text: str
    metadata: Optional[Dict] = {}


class ModelConfig(BaseModel):
    """Model configuration for evaluations."""
    name: str
    provider: str  # "openai", "anthropic", "openrouter"
    temperature: float = 0.0
    max_tokens: Optional[int] = None


class EvalConfig(BaseModel):
    """Configuration for running evaluations."""
    eval_name: str
    component: str  # "query_builder", "orchestrator", "safety_guard", "end_to_end"
    dataset_path: str
    models: List[ModelConfig]
    prompt_versions: List[str]  # Version IDs to test
    metrics: List[str]  # ["accuracy", "latency", "similarity", "safety_score"]
    output_path: str
    run_parallel: bool = False


# ============ Prompt Version Registry ============
# Now using service prompts directly for consistency

# Convert service prompt registry to eval format
_service_qb_prompts = QUERY_BUILDER_PROMPTS.list_versions()
QUERY_BUILDER_PROMPTS_DICT = {
    version: PromptVersion(
        version=prompt.version,
        name=prompt.name,
        created_at=prompt.created_at,
        description=prompt.description,
        prompt_text=prompt.prompt_text,
        metadata=prompt.metadata or {}
    )
    for version, prompt in _service_qb_prompts.items()
}

_service_decision_prompts = DECISION_PROMPTS.list_versions()
DECISION_PROMPTS_DICT = {
    version: PromptVersion(
        version=prompt.version,
        name=prompt.name,
        created_at=prompt.created_at,
        description=prompt.description,
        prompt_text=prompt.prompt_text,
        metadata=prompt.metadata or {}
    )
    for version, prompt in _service_decision_prompts.items()
}


# ============ Model Configurations ============

EVAL_MODELS = [
    ModelConfig(name="gpt-4o", provider="openai", temperature=0.0),
    ModelConfig(name="gpt-4o-mini", provider="openai", temperature=0.0),
    ModelConfig(name="gpt-3.5-turbo", provider="openai", temperature=0.0),
    # Add more models as needed
    # ModelConfig(name="claude-3-5-sonnet-20241022", provider="anthropic", temperature=0.0),
]


# ============ Standard Eval Configurations ============

COMPONENT_EVALS = {
    "query_builder": EvalConfig(
        eval_name="query_builder_comprehensive",
        component="query_builder",
        dataset_path="evals/datasets/query_generation/test_cases.json",
        models=[EVAL_MODELS[0], EVAL_MODELS[1]],  # gpt-4o, gpt-4o-mini
        prompt_versions=list(_service_qb_prompts.keys()),  # Use all available versions
        metrics=["cypher_validity", "semantic_correctness", "latency"],
        output_path="evals/reports/query_builder_eval.json",
    ),

    "intent_classification": EvalConfig(
        eval_name="intent_classification_eval",
        component="orchestrator",
        dataset_path="evals/datasets/intent_classification/test_cases.json",
        models=EVAL_MODELS[:3],
        prompt_versions=list(_service_decision_prompts.keys()),  # Use all available versions
        metrics=["accuracy", "precision", "recall", "latency"],
        output_path="evals/reports/intent_classification_eval.json",
    ),

    "safety_guard": EvalConfig(
        eval_name="safety_comprehensive",
        component="safety_guard",
        dataset_path="evals/datasets/safety/test_cases.json",
        models=[EVAL_MODELS[0]],
        prompt_versions=["v1.0"],
        metrics=["precision", "recall", "false_positive_rate"],
        output_path="evals/reports/safety_eval.json",
    ),
}

SYSTEM_EVALS = {
    "end_to_end": EvalConfig(
        eval_name="end_to_end_conversations",
        component="end_to_end",
        dataset_path="evals/datasets/end_to_end/conversations.json",
        models=[EVAL_MODELS[0]],
        prompt_versions=["v1.0"],
        metrics=["conversation_success_rate", "avg_latency", "user_satisfaction_score"],
        output_path="evals/reports/e2e_eval.json",
    ),
}
