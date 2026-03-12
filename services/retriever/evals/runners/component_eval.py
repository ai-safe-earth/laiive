"""
Component-level evaluation runner.
Evaluates individual components (query builder, orchestrator, safety guard) across
different models and prompt versions.
"""

import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from agent.utils.llm_utils import get_openai_client
from dataclasses import dataclass, asdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import settings
from agent.tools.query_builder import QueryBuilderTool
from agent.orchestrator import Orchestrator
from agent.tools.safety_guard import SafetyGuardTool
from evals.config import (
    EvalConfig,
    PromptVersion,
    ModelConfig,
    QUERY_BUILDER_PROMPTS_DICT as QUERY_BUILDER_PROMPTS,
    DECISION_PROMPTS_DICT as DECISION_PROMPTS,
)


@dataclass
class EvalResult:
    """Single evaluation result."""

    test_id: str
    model: str
    prompt_version: str
    passed: bool
    score: float
    latency_ms: float
    output: Any
    expected: Any
    errors: List[str]
    metadata: Dict[str, Any]


class ComponentEvaluator:
    """Evaluates individual components of the retrieval system."""

    def __init__(self, eval_config: EvalConfig):
        self.config = eval_config
        self.results: List[EvalResult] = []

    def run_query_builder_eval(
        self,
        test_cases: List[Dict],
        prompt_version: PromptVersion,
        model_config: ModelConfig,
    ) -> List[EvalResult]:
        """Evaluate query builder with specific prompt version and model."""
        print(f"\n{'='*60}")
        print(f"Evaluating Query Builder")
        print(f"  Model: {model_config.name}")
        print(f"  Prompt: {prompt_version.version} ({prompt_version.name})")
        print(f"{'='*60}\n")

        results = []

        for i, test_case in enumerate(test_cases, 1):
            print(f"Test {i}/{len(test_cases)}: {test_case['id']}")

            start_time = datetime.now()

            try:
                # Create modified query builder with specific prompt
                tool = QueryBuilderTool(schema="Mock schema")
                # Override the system prompt
                QueryBuilderTool.SYSTEM_PROMPT = prompt_version.prompt_text

                # Mock client with specific model
                tool.client = get_openai_client()

                # Generate Cypher query
                cypher = tool._generate_cypher(
                    test_case["user_query"],
                    date_info=(
                        {"start_date": test_case.get("date_context", "2026-01-22")}
                        if test_case.get("date_context")
                        else None
                    ),
                )

                latency = (datetime.now() - start_time).total_seconds() * 1000

                # Evaluate output
                passed, score, errors = self._evaluate_cypher(cypher, test_case)

                result = EvalResult(
                    test_id=test_case["id"],
                    model=model_config.name,
                    prompt_version=prompt_version.version,
                    passed=passed,
                    score=score,
                    latency_ms=latency,
                    output=cypher,
                    expected=test_case.get("expected_patterns", []),
                    errors=errors,
                    metadata=test_case.get("metadata", {}),
                )

                results.append(result)
                print(
                    f"  ✓ Passed: {passed}, Score: {score:.2f}, Latency: {latency:.0f}ms"
                )

            except Exception as e:
                result = EvalResult(
                    test_id=test_case["id"],
                    model=model_config.name,
                    prompt_version=prompt_version.version,
                    passed=False,
                    score=0.0,
                    latency_ms=0.0,
                    output=None,
                    expected=test_case.get("expected_patterns", []),
                    errors=[str(e)],
                    metadata=test_case.get("metadata", {}),
                )
                results.append(result)
                print(f"  ✗ Error: {str(e)}")

        return results

    def run_intent_classification_eval(
        self,
        test_cases: List[Dict],
        prompt_version: PromptVersion,
        model_config: ModelConfig,
    ) -> List[EvalResult]:
        """Evaluate intent classification (decide_action)."""
        print(f"\n{'='*60}")
        print(f"Evaluating Intent Classification")
        print(f"  Model: {model_config.name}")
        print(f"  Prompt: {prompt_version.version}")
        print(f"{'='*60}\n")

        results = []

        for i, test_case in enumerate(test_cases, 1):
            print(f"Test {i}/{len(test_cases)}: {test_case['id']}")

            start_time = datetime.now()

            try:
                # Create orchestrator
                orchestrator = Orchestrator(schema="Mock schema")
                # TODO: Override decision prompt with versioned one

                # Get action decision
                action = orchestrator.decide_action(
                    test_case["user_message"],
                    conversation_history=test_case.get("conversation_history"),
                )

                latency = (datetime.now() - start_time).total_seconds() * 1000

                # Evaluate
                expected_action = test_case["expected_action"]
                passed = action == expected_action
                score = 1.0 if passed else 0.0
                errors = [] if passed else [f"Expected {expected_action}, got {action}"]

                result = EvalResult(
                    test_id=test_case["id"],
                    model=model_config.name,
                    prompt_version=prompt_version.version,
                    passed=passed,
                    score=score,
                    latency_ms=latency,
                    output=action,
                    expected=expected_action,
                    errors=errors,
                    metadata={"reasoning": test_case.get("reasoning", "")},
                )

                results.append(result)
                print(
                    f"  {'✓' if passed else '✗'} Expected: {expected_action}, Got: {action}, Latency: {latency:.0f}ms"
                )

            except Exception as e:
                result = EvalResult(
                    test_id=test_case["id"],
                    model=model_config.name,
                    prompt_version=prompt_version.version,
                    passed=False,
                    score=0.0,
                    latency_ms=0.0,
                    output=None,
                    expected=test_case["expected_action"],
                    errors=[str(e)],
                    metadata={},
                )
                results.append(result)
                print(f"  ✗ Error: {str(e)}")

        return results

    def run_safety_eval(
        self, test_cases: List[Dict], model_config: ModelConfig
    ) -> List[EvalResult]:
        """Evaluate safety guard."""
        print(f"\n{'='*60}")
        print(f"Evaluating Safety Guard")
        print(f"  Model: {model_config.name}")
        print(f"{'='*60}\n")

        results = []
        safety_tool = SafetyGuardTool()

        for i, test_case in enumerate(test_cases, 1):
            print(f"Test {i}/{len(test_cases)}: {test_case['id']}")

            start_time = datetime.now()

            try:
                # Run safety check based on input type
                if test_case["input_type"] in ["cypher_injection", "safe_query"]:
                    result_json = safety_tool.run(test_case["input_text"])
                    result_data = json.loads(result_json)
                    verdict = "safe" if result_data.get("is_safe") else "unsafe"
                else:
                    # First check regex-based injection detection
                    if safety_tool.detect_injection(test_case["input_text"]):
                        verdict = "unsafe"
                    else:
                        # Then check with LlamaGuard for content safety
                        safety_result = safety_tool.validate_input_safety(
                            test_case["input_text"]
                        )
                        verdict = safety_result.get("verdict", "safe")

                latency = (datetime.now() - start_time).total_seconds() * 1000

                # Evaluate
                expected_verdict = test_case["expected_verdict"]
                passed = verdict == expected_verdict
                score = 1.0 if passed else 0.0
                errors = (
                    [] if passed else [f"Expected {expected_verdict}, got {verdict}"]
                )

                result = EvalResult(
                    test_id=test_case["id"],
                    model=model_config.name,
                    prompt_version="v1.0",
                    passed=passed,
                    score=score,
                    latency_ms=latency,
                    output=verdict,
                    expected=expected_verdict,
                    errors=errors,
                    metadata={"input_type": test_case["input_type"]},
                )

                results.append(result)
                print(
                    f"  {'✓' if passed else '✗'} Expected: {expected_verdict}, Got: {verdict}"
                )

            except Exception as e:
                result = EvalResult(
                    test_id=test_case["id"],
                    model=model_config.name,
                    prompt_version="v1.0",
                    passed=False,
                    score=0.0,
                    latency_ms=0.0,
                    output=None,
                    expected=test_case["expected_verdict"],
                    errors=[str(e)],
                    metadata={},
                )
                results.append(result)
                print(f"  ✗ Error: {str(e)}")

        return results

    def _evaluate_cypher(
        self, cypher: str, test_case: Dict
    ) -> tuple[bool, float, List[str]]:
        """Evaluate generated Cypher query against test case expectations."""
        errors = []
        score = 0.0
        max_score = 0.0

        # Check for forbidden patterns
        should_not_contain = test_case.get("should_not_contain", [])
        max_score += len(should_not_contain)
        for pattern in should_not_contain:
            if re.search(pattern, cypher, re.IGNORECASE):
                errors.append(f"Contains forbidden pattern: {pattern}")
            else:
                score += 1.0

        # Check for expected patterns
        expected_patterns = test_case.get("expected_patterns", [])
        max_score += len(expected_patterns)
        for pattern in expected_patterns:
            if re.search(pattern, cypher, re.IGNORECASE):
                score += 1.0
            else:
                errors.append(f"Missing expected pattern: {pattern}")

        # Check expected structure
        if "expected_cypher_structure" in test_case:
            structure = test_case["expected_cypher_structure"]
            for key, expected_value in structure.items():
                max_score += 1.0
                if key == "has_datetime_conversion":
                    if "datetime(e.start_at)" in cypher:
                        score += 1.0
                    else:
                        errors.append("Missing datetime conversion")
                elif key == "has_price_filter":
                    if re.search(r"price_amount.*[<>=]", cypher):
                        score += 1.0
                    else:
                        errors.append("Missing price filter")
                # Add more structure checks as needed

        passed = len(errors) == 0
        normalized_score = score / max_score if max_score > 0 else 1.0

        return passed, normalized_score, errors

    def generate_report(self, results: List[EvalResult], output_path: str):
        """Generate evaluation report."""
        report = {
            "eval_name": self.config.eval_name,
            "component": self.config.component,
            "timestamp": datetime.now().isoformat(),
            "summary": self._calculate_summary(results),
            "results": [asdict(r) for r in results],
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {output_path}")
        self._print_summary(report["summary"])

    def _calculate_summary(self, results: List[EvalResult]) -> Dict[str, Any]:
        """Calculate summary statistics."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        avg_score = sum(r.score for r in results) / total if total > 0 else 0
        avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0

        # Group by model and prompt version
        by_model = {}
        by_prompt = {}

        for r in results:
            if r.model not in by_model:
                by_model[r.model] = {"total": 0, "passed": 0, "avg_score": 0}
            by_model[r.model]["total"] += 1
            by_model[r.model]["passed"] += 1 if r.passed else 0
            by_model[r.model]["avg_score"] += r.score

            if r.prompt_version not in by_prompt:
                by_prompt[r.prompt_version] = {"total": 0, "passed": 0, "avg_score": 0}
            by_prompt[r.prompt_version]["total"] += 1
            by_prompt[r.prompt_version]["passed"] += 1 if r.passed else 0
            by_prompt[r.prompt_version]["avg_score"] += r.score

        # Calculate averages
        for model_stats in by_model.values():
            model_stats["avg_score"] /= model_stats["total"]
            model_stats["accuracy"] = model_stats["passed"] / model_stats["total"]

        for prompt_stats in by_prompt.values():
            prompt_stats["avg_score"] /= prompt_stats["total"]
            prompt_stats["accuracy"] = prompt_stats["passed"] / prompt_stats["total"]

        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "accuracy": passed / total if total > 0 else 0,
            "avg_score": avg_score,
            "avg_latency_ms": avg_latency,
            "by_model": by_model,
            "by_prompt_version": by_prompt,
        }

    def _print_summary(self, summary: Dict[str, Any]):
        """Print summary to console."""
        print(f"\n{'='*60}")
        print("EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']} ({summary['accuracy']*100:.1f}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Avg Score: {summary['avg_score']:.3f}")
        print(f"Avg Latency: {summary['avg_latency_ms']:.0f}ms")

        print(f"\nBy Model:")
        for model, stats in summary["by_model"].items():
            print(
                f"  {model}: {stats['accuracy']*100:.1f}% accuracy, {stats['avg_score']:.3f} avg score"
            )

        print(f"\nBy Prompt Version:")
        for version, stats in summary["by_prompt_version"].items():
            print(
                f"  {version}: {stats['accuracy']*100:.1f}% accuracy, {stats['avg_score']:.3f} avg score"
            )
        print(f"{'='*60}\n")


def run_component_eval(eval_config: EvalConfig):
    """Main entry point for component evaluation."""
    evaluator = ComponentEvaluator(eval_config)

    # Load dataset
    with open(eval_config.dataset_path) as f:
        dataset = json.load(f)
    test_cases = dataset.get("test_cases", [])

    all_results = []

    # Run evals for each model and prompt version combination
    for model_config in eval_config.models:
        for prompt_version_id in eval_config.prompt_versions:
            if eval_config.component == "query_builder":
                prompt_version = QUERY_BUILDER_PROMPTS[prompt_version_id]
                results = evaluator.run_query_builder_eval(
                    test_cases, prompt_version, model_config
                )
            elif eval_config.component == "orchestrator":
                prompt_version = DECISION_PROMPTS[prompt_version_id]
                results = evaluator.run_intent_classification_eval(
                    test_cases, prompt_version, model_config
                )
            elif eval_config.component == "safety_guard":
                results = evaluator.run_safety_eval(test_cases, model_config)
            else:
                raise ValueError(f"Unknown component: {eval_config.component}")

            all_results.extend(results)

    # Generate report
    evaluator.generate_report(all_results, eval_config.output_path)

    return all_results


if __name__ == "__main__":
    from evals.config import COMPONENT_EVALS

    # Example: Run query builder eval
    # run_component_eval(COMPONENT_EVALS["query_builder"])

    # Example: Run intent classification eval
    # run_component_eval(COMPONENT_EVALS["intent_classification"])

    # Example: Run safety eval
    # run_component_eval(COMPONENT_EVALS["safety_guard"])

    print("Component evaluator ready. Import and run with specific eval config.")
