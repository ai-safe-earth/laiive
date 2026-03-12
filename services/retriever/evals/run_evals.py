#!/usr/bin/env python3
"""
Main evaluation runner script.

Usage:
    # Run all component evals
    python evals/run_evals.py --component all

    # Run specific component
    python evals/run_evals.py --component query_builder

    # Run system evals
    python evals/run_evals.py --system

    # Run with specific models
    python evals/run_evals.py --component query_builder --models gpt-4o gpt-4o-mini

    # Run with specific prompt versions
    python evals/run_evals.py --component query_builder --prompts v1.0 v1.1

    # Compare prompt versions
    python evals/run_evals.py --component query_builder --compare-prompts
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.runners.component_eval import run_component_eval
from evals.runners.system_eval import run_system_eval
from evals.config import (
    COMPONENT_EVALS,
    SYSTEM_EVALS,
    EVAL_MODELS,
    ModelConfig,
    QUERY_BUILDER_PROMPTS,
    DECISION_PROMPTS,
)


def run_component_evals(component: str, models=None, prompt_versions=None):
    """Run component evaluations."""
    if component == "all":
        components = list(COMPONENT_EVALS.keys())
    else:
        components = [component]

    for comp in components:
        if comp not in COMPONENT_EVALS:
            print(f"Unknown component: {comp}")
            continue

        eval_config = COMPONENT_EVALS[comp]

        # Override models if specified
        if models:
            eval_config.models = [m for m in EVAL_MODELS if m.name in models]

        # Override prompt versions if specified
        if prompt_versions:
            eval_config.prompt_versions = prompt_versions

        print(f"\n{'#'*60}")
        print(f"# Running {comp} evaluation")
        print(f"{'#'*60}")

        run_component_eval(eval_config)


def run_system_evals(eval_name: str = "end_to_end"):
    """Run system evaluations."""
    if eval_name not in SYSTEM_EVALS:
        print(f"Unknown system eval: {eval_name}")
        return

    eval_config = SYSTEM_EVALS[eval_name]

    print(f"\n{'#'*60}")
    print(f"# Running {eval_name} system evaluation")
    print(f"{'#'*60}")

    run_system_eval(eval_config)


def compare_prompts(component: str):
    """Compare different prompt versions for a component."""
    print(f"\n{'='*60}")
    print(f"Comparing Prompt Versions for {component}")
    print(f"{'='*60}\n")

    if component == "query_builder":
        prompts = QUERY_BUILDER_PROMPTS
    elif component == "orchestrator":
        prompts = DECISION_PROMPTS
    else:
        print(f"Prompt comparison not supported for {component}")
        return

    # Show available prompt versions
    print("Available prompt versions:")
    for version, prompt in prompts.list_versions().items():
        print(f"\n  {version}: {prompt.name}")
        print(f"    Description: {prompt.description}")
        print(f"    Created: {prompt.created_at}")

    # Run eval with all prompt versions
    eval_config = COMPONENT_EVALS[component]
    eval_config.prompt_versions = list(prompts.list_versions().keys())

    print(f"\nRunning evaluation with all prompt versions...")
    run_component_eval(eval_config)


def main():
    parser = argparse.ArgumentParser(description="Run retriever agent evaluations")

    parser.add_argument(
        "--component",
        choices=["all", "query_builder", "intent_classification", "safety_guard"],
        help="Component to evaluate",
    )

    parser.add_argument(
        "--system",
        action="store_true",
        help="Run system-level end-to-end evaluations",
    )

    parser.add_argument(
        "--models",
        nargs="+",
        choices=[m.name for m in EVAL_MODELS],
        help="Models to evaluate (default: all configured models)",
    )

    parser.add_argument(
        "--prompts",
        nargs="+",
        help="Prompt versions to evaluate (e.g., v1.0 v1.1)",
    )

    parser.add_argument(
        "--compare-prompts",
        action="store_true",
        help="Compare all available prompt versions",
    )

    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="List available prompt versions",
    )

    args = parser.parse_args()

    # List prompts
    if args.list_prompts:
        print("\nQuery Builder Prompts:")
        for version, prompt in QUERY_BUILDER_PROMPTS.items():
            print(f"  {version}: {prompt.name} - {prompt.description}")

        print("\nDecision Prompts:")
        for version, prompt in DECISION_PROMPTS.items():
            print(f"  {version}: {prompt.name} - {prompt.description}")
        return

    # Compare prompts
    if args.compare_prompts:
        if not args.component or args.component == "all":
            print("Please specify a component to compare prompts")
            return
        compare_prompts(args.component)
        return

    # Run component evals
    if args.component:
        run_component_evals(args.component, args.models, args.prompts)

    # Run system evals
    if args.system:
        run_system_evals()

    # If no args, show help
    if not args.component and not args.system:
        parser.print_help()


if __name__ == "__main__":
    main()
