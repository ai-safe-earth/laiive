"""Router — maps each atomic sub-query to an execution strategy (02-arch §3).

Pure code, no LLM call: the classifier already produced the resolved
constraint state; routing is a deterministic decision over it.
"""

from dataclasses import dataclass
from enum import StrEnum

from .classifier import Classification, Constraints


class PlanKind(StrEnum):
    TEMPLATE = "template"  # parameterized Cypher for the common shapes
    NEARBY = "nearby"  # point.distance with progressive radius
    VECTOR = "vector"  # kNN over event embeddings for fuzzy/vibe asks
    LLM_CYPHER = "llm_cypher"  # long tail: LLM-generated, read-only-validated


@dataclass(frozen=True)
class ExecutionPlan:
    kind: PlanKind
    constraints: Constraints


def route(classification: Classification, has_location: bool) -> list[ExecutionPlan]:
    """One plan per sub-query. Empty for smalltalk/out_of_scope/ambiguous."""
    if classification.query_type in ("smalltalk", "out_of_scope"):
        return []
    if classification.moment == "ambiguous" and not classification.sub_queries:
        return []

    plans: list[ExecutionPlan] = []
    for c in classification.sub_queries:
        if c.needs_custom_cypher:
            plans.append(ExecutionPlan(PlanKind.LLM_CYPHER, c))
        elif c.near_me:
            # Without a location this sub-query cannot run — the classifier
            # marks such turns ambiguous and asks for a place instead.
            if has_location:
                plans.append(ExecutionPlan(PlanKind.NEARBY, c))
        elif c.free_text:
            plans.append(ExecutionPlan(PlanKind.VECTOR, c))
        elif not c.is_empty():
            plans.append(ExecutionPlan(PlanKind.TEMPLATE, c))
    return plans
