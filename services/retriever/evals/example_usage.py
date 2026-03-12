"""
Example usage of the evaluation framework.

This file demonstrates how to:
1. Run evals programmatically
2. Create custom eval configurations
3. Analyze results
4. Integrate with CI/CD pipelines
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.config import (
    EvalConfig,
    ModelConfig,
    PromptVersion,
    COMPONENT_EVALS,
    SYSTEM_EVALS,
)
from evals.runners.component_eval import run_component_eval
from evals.runners.system_eval import run_system_eval
import json


def example_1_basic_component_eval():
    """Example 1: Run a basic component evaluation."""
    print("\n" + "="*60)
    print("Example 1: Basic Component Evaluation")
    print("="*60)

    # Use pre-configured eval
    eval_config = COMPONENT_EVALS["query_builder"]

    # Run evaluation
    results = run_component_eval(eval_config)

    # Access results
    print(f"\nCompleted {len(results)} test cases")
    for result in results[:3]:  # Show first 3
        print(f"  {result.test_id}: {'PASS' if result.passed else 'FAIL'} (score: {result.score:.2f})")


def example_2_custom_eval_config():
    """Example 2: Create and run a custom evaluation configuration."""
    print("\n" + "="*60)
    print("Example 2: Custom Evaluation Configuration")
    print("="*60)

    # Create custom config
    custom_eval = EvalConfig(
        eval_name="my_custom_query_eval",
        component="query_builder",
        dataset_path="evals/datasets/query_generation/test_cases.json",
        models=[
            ModelConfig(name="gpt-4o-mini", provider="openai", temperature=0.0),
        ],
        prompt_versions=["v1.0"],
        metrics=["accuracy", "latency"],
        output_path="evals/reports/custom_eval.json",
    )

    # Run it
    results = run_component_eval(custom_eval)
    print(f"\nCustom eval completed with {len(results)} results")


def example_3_compare_prompt_versions():
    """Example 3: Compare multiple prompt versions."""
    print("\n" + "="*60)
    print("Example 3: Comparing Prompt Versions")
    print("="*60)

    # Configure eval to test multiple prompt versions
    eval_config = EvalConfig(
        eval_name="prompt_comparison_v1_vs_v11",
        component="query_builder",
        dataset_path="evals/datasets/query_generation/test_cases.json",
        models=[ModelConfig(name="gpt-4o", provider="openai", temperature=0.0)],
        prompt_versions=["v1.0", "v1.1"],  # Compare two versions
        metrics=["accuracy", "latency"],
        output_path="evals/reports/prompt_comparison.json",
    )

    results = run_component_eval(eval_config)

    # Analyze results by prompt version
    v1_results = [r for r in results if r.prompt_version == "v1.0"]
    v11_results = [r for r in results if r.prompt_version == "v1.1"]

    v1_accuracy = sum(r.passed for r in v1_results) / len(v1_results) if v1_results else 0
    v11_accuracy = sum(r.passed for r in v11_results) / len(v11_results) if v11_results else 0

    print(f"\nPrompt v1.0 accuracy: {v1_accuracy:.1%}")
    print(f"Prompt v1.1 accuracy: {v11_accuracy:.1%}")
    print(f"Improvement: {(v11_accuracy - v1_accuracy):.1%}")


def example_4_multi_model_comparison():
    """Example 4: Compare multiple models."""
    print("\n" + "="*60)
    print("Example 4: Multi-Model Comparison")
    print("="*60)

    eval_config = EvalConfig(
        eval_name="model_comparison",
        component="query_builder",
        dataset_path="evals/datasets/query_generation/test_cases.json",
        models=[
            ModelConfig(name="gpt-4o", provider="openai", temperature=0.0),
            ModelConfig(name="gpt-4o-mini", provider="openai", temperature=0.0),
        ],
        prompt_versions=["v1.1"],
        metrics=["accuracy", "latency"],
        output_path="evals/reports/model_comparison.json",
    )

    results = run_component_eval(eval_config)

    # Group by model
    models = {}
    for r in results:
        if r.model not in models:
            models[r.model] = {"passed": 0, "total": 0, "latencies": []}
        models[r.model]["total"] += 1
        if r.passed:
            models[r.model]["passed"] += 1
        models[r.model]["latencies"].append(r.latency_ms)

    # Print comparison
    print("\nModel Comparison:")
    for model, stats in models.items():
        accuracy = stats["passed"] / stats["total"]
        avg_latency = sum(stats["latencies"]) / len(stats["latencies"])
        print(f"  {model}:")
        print(f"    Accuracy: {accuracy:.1%}")
        print(f"    Avg Latency: {avg_latency:.0f}ms")


def example_5_system_eval():
    """Example 5: Run end-to-end system evaluation."""
    print("\n" + "="*60)
    print("Example 5: System-Level Evaluation")
    print("="*60)

    eval_config = SYSTEM_EVALS["end_to_end"]

    results = run_system_eval(eval_config)

    print(f"\nEvaluated {len(results)} conversations")
    for result in results:
        print(f"  {result.conversation_id}: {'PASS' if result.success_criteria_met else 'FAIL'}")
        print(f"    Successful turns: {result.successful_turns}/{result.total_turns}")


def example_6_analyze_report():
    """Example 6: Load and analyze a saved report."""
    print("\n" + "="*60)
    print("Example 6: Analyzing Saved Reports")
    print("="*60)

    report_path = "evals/reports/query_builder_eval.json"

    try:
        with open(report_path) as f:
            report = json.load(f)

        summary = report["summary"]

        print(f"\nReport: {report['eval_name']}")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Overall Accuracy: {summary['accuracy']:.1%}")
        print(f"Average Score: {summary['avg_score']:.2f}")
        print(f"Average Latency: {summary['avg_latency_ms']:.0f}ms")

        # Show per-model breakdown
        print("\nBy Model:")
        for model, stats in summary["by_model"].items():
            print(f"  {model}: {stats['accuracy']:.1%} accuracy")

        # Show per-prompt breakdown
        print("\nBy Prompt Version:")
        for version, stats in summary["by_prompt_version"].items():
            print(f"  {version}: {stats['accuracy']:.1%} accuracy")

        # Identify failed tests
        print("\nFailed Tests:")
        failed_tests = [r for r in report["results"] if not r["passed"]]
        for test in failed_tests[:5]:  # Show first 5
            print(f"  {test['test_id']}:")
            print(f"    Model: {test['model']}, Prompt: {test['prompt_version']}")
            print(f"    Errors: {', '.join(test['errors'])}")

    except FileNotFoundError:
        print(f"Report not found at {report_path}")
        print("Run an evaluation first to generate a report")


def example_7_ci_cd_integration():
    """Example 7: CI/CD integration pattern."""
    print("\n" + "="*60)
    print("Example 7: CI/CD Integration Pattern")
    print("="*60)

    # This pattern can be used in CI/CD pipelines
    def run_regression_tests():
        """Run regression tests and return exit code."""

        # Define minimum acceptable metrics
        MIN_ACCURACY = 0.80
        MAX_AVG_LATENCY = 1000  # ms

        # Run evaluations
        eval_config = COMPONENT_EVALS["query_builder"]
        results = run_component_eval(eval_config)

        # Calculate metrics
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        accuracy = passed / total if total > 0 else 0
        avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0

        # Check thresholds
        accuracy_ok = accuracy >= MIN_ACCURACY
        latency_ok = avg_latency <= MAX_AVG_LATENCY

        print(f"\nRegression Test Results:")
        print(f"  Accuracy: {accuracy:.1%} (min: {MIN_ACCURACY:.1%}) {'✓' if accuracy_ok else '✗'}")
        print(f"  Avg Latency: {avg_latency:.0f}ms (max: {MAX_AVG_LATENCY}ms) {'✓' if latency_ok else '✗'}")

        # Return exit code (0 = success, 1 = failure)
        if accuracy_ok and latency_ok:
            print("\n✓ All regression tests passed!")
            return 0
        else:
            print("\n✗ Regression tests failed!")
            return 1

    exit_code = run_regression_tests()
    print(f"\nExit code: {exit_code}")


def example_8_custom_prompt_testing():
    """Example 8: Test a new prompt before deploying."""
    print("\n" + "="*60)
    print("Example 8: Testing New Prompt Version")
    print("="*60)

    # Define new experimental prompt
    experimental_prompt = PromptVersion(
        version="v2.0-experimental",
        name="experimental_with_better_context",
        created_at="2026-01-22",
        description="Experimental prompt with enhanced context handling",
        prompt_text="""Your new experimental prompt text here...""",
        metadata={"experimental": True},
    )

    # Test it against baseline
    eval_config = EvalConfig(
        eval_name="experimental_prompt_test",
        component="query_builder",
        dataset_path="evals/datasets/query_generation/test_cases.json",
        models=[ModelConfig(name="gpt-4o-mini", provider="openai", temperature=0.0)],
        prompt_versions=["v1.1", "v2.0-experimental"],  # Compare to current best
        metrics=["accuracy", "latency"],
        output_path="evals/reports/experimental_test.json",
    )

    # Note: You'd need to add the experimental prompt to the registry first
    # For now, this shows the pattern
    print("\nPattern for testing new prompts:")
    print("1. Create PromptVersion object")
    print("2. Add to prompt registry in config.py")
    print("3. Run comparison eval")
    print("4. Analyze results")
    print("5. Deploy if better than baseline")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run eval framework examples")
    parser.add_argument(
        "example",
        type=int,
        nargs="?",
        choices=range(1, 9),
        help="Example number to run (1-8)",
    )

    args = parser.parse_args()

    examples = {
        1: ("Basic Component Eval", example_1_basic_component_eval),
        2: ("Custom Eval Config", example_2_custom_eval_config),
        3: ("Compare Prompt Versions", example_3_compare_prompt_versions),
        4: ("Multi-Model Comparison", example_4_multi_model_comparison),
        5: ("System-Level Eval", example_5_system_eval),
        6: ("Analyze Report", example_6_analyze_report),
        7: ("CI/CD Integration", example_7_ci_cd_integration),
        8: ("Custom Prompt Testing", example_8_custom_prompt_testing),
    }

    if args.example:
        # Run specific example
        name, func = examples[args.example]
        print(f"\nRunning Example {args.example}: {name}")
        func()
    else:
        # Show all examples
        print("\nAvailable Examples:")
        print("="*60)
        for num, (name, _) in examples.items():
            print(f"{num}. {name}")
        print("\nRun with: python evals/example_usage.py <example_number>")
        print("Example: python evals/example_usage.py 1")
