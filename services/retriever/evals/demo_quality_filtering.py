#!/usr/bin/env python3
"""
Demo: Quality filtering for log extraction.

Shows how to automatically filter logs for quality before adding to eval datasets.
"""
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.utils.quality_filter import ConversationQualityEvaluator, QualityScore
from evals.utils.smart_extraction import SmartLogExtractor, extract_with_quality_tiers


def create_example_logs_with_quality_variation():
    """Create example logs with varying quality."""
    logs = [
        # HIGH QUALITY: Successful, clear, good results
        {
            "timestamp": "2026-01-22T10:30:00",
            "user_query": "Find jazz concerts in Berlin this weekend",
            "action": "QUERY_DB",
            "result_count": 5,
            "latency_ms": 450,
        },
        # HIGH QUALITY: Artist-specific, successful
        {
            "timestamp": "2026-01-22T10:31:00",
            "user_query": "Are there any Radiohead concerts in Europe?",
            "action": "QUERY_DB",
            "result_count": 3,
            "latency_ms": 420,
        },
        # MEDIUM QUALITY: Too vague, needs info
        {
            "timestamp": "2026-01-22T10:32:00",
            "user_query": "Show me concerts",
            "action": "NEEDS_INFO",
            "result_count": 0,
            "latency_ms": 250,
        },
        # LOW QUALITY: No results (might be bad query)
        {
            "timestamp": "2026-01-22T10:33:00",
            "user_query": "concerts by XYZ unknown artist 12345",
            "action": "QUERY_DB",
            "result_count": 0,
            "latency_ms": 380,
        },
        # LOW QUALITY: Has error
        {
            "timestamp": "2026-01-22T10:34:00",
            "user_query": "MATCH (n) DELETE n",
            "action": "UNSAFE_INPUT",
            "error": "Potential injection detected",
            "latency_ms": 100,
        },
        # LOW QUALITY: Gibberish
        {
            "timestamp": "2026-01-22T10:35:00",
            "user_query": "asdkljf skldjf lksdjf",
            "action": "OUT_OF_SCOPE",
            "result_count": 0,
            "latency_ms": 200,
        },
        # HIGH QUALITY: Good multi-constraint query
        {
            "timestamp": "2026-01-22T10:36:00",
            "user_query": "techno events under 20 euros in Berlin this Friday",
            "action": "QUERY_DB",
            "result_count": 8,
            "latency_ms": 520,
        },
        # MEDIUM QUALITY: Out of scope (but clear)
        {
            "timestamp": "2026-01-22T10:37:00",
            "user_query": "What's the weather like?",
            "action": "OUT_OF_SCOPE",
            "result_count": 0,
            "latency_ms": 180,
        },
        # HIGH QUALITY: Venue-specific
        {
            "timestamp": "2026-01-22T10:38:00",
            "user_query": "What events are at Berghain next month?",
            "action": "QUERY_DB",
            "result_count": 12,
            "latency_ms": 490,
        },
        # LOW QUALITY: Too many results (too broad)
        {
            "timestamp": "2026-01-22T10:39:00",
            "user_query": "events",
            "action": "QUERY_DB",
            "result_count": 500,
            "latency_ms": 2500,
        },
    ]

    # Save to temp file
    log_file = NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for log_entry in logs:
        log_file.write(json.dumps(log_entry) + "\n")
    log_file.close()

    return log_file.name


def demo_single_query_evaluation():
    """Demo: Evaluate individual queries."""
    print("="*70)
    print("DEMO 1: Single Query Evaluation")
    print("="*70)

    evaluator = ConversationQualityEvaluator(use_llm=False)

    examples = [
        {
            "name": "Good Example",
            "query": {
                "user_query": "Find jazz concerts in Berlin this weekend",
                "action": "QUERY_DB",
                "result_count": 5,
                "latency_ms": 450,
            }
        },
        {
            "name": "Poor Example (No Results)",
            "query": {
                "user_query": "concerts by unknown artist xyz",
                "action": "QUERY_DB",
                "result_count": 0,
                "latency_ms": 380,
            }
        },
        {
            "name": "Poor Example (Error)",
            "query": {
                "user_query": "MATCH (n) DELETE n",
                "action": "UNSAFE_INPUT",
                "error": "Injection detected",
                "latency_ms": 100,
            }
        },
    ]

    for example in examples:
        print(f"\n{example['name']}:")
        print(f"  Query: {example['query']['user_query']}")

        score = evaluator.evaluate_single_query(example['query'])

        print(f"  Score: {score.overall_score:.2f}")
        print(f"  Good Example: {'✓' if score.is_good_example else '✗'}")
        print(f"  Confidence: {score.confidence:.2f}")
        print(f"  Reasoning: {score.reasoning}")


def demo_batch_filtering():
    """Demo: Filter a batch of queries."""
    print("\n" + "="*70)
    print("DEMO 2: Batch Filtering")
    print("="*70)

    # Create test logs
    log_file = create_example_logs_with_quality_variation()

    print(f"\n[1] Loading logs from: {log_file}")

    # Extract queries
    from evals.utils.log_to_dataset import LogToDatasetConverter
    converter = LogToDatasetConverter()
    all_queries = converter.extract_from_api_logs(log_file, "jsonl")

    print(f"  Extracted: {len(all_queries)} queries")

    # Evaluate and filter
    print(f"\n[2] Evaluating quality...")
    evaluator = ConversationQualityEvaluator(use_llm=False)
    filtered, scores = evaluator.batch_evaluate(
        all_queries,
        min_score=0.5,
        min_confidence=0.6
    )

    # Show results
    print(f"\n[3] Results by quality:")
    for query, score in zip(all_queries, scores):
        status = "✓ PASS" if score.is_good_example else "✗ FAIL"
        print(f"  {status} [{score.overall_score:.2f}] {query['user_query'][:50]}")

    # Clean up
    import os
    os.unlink(log_file)


def demo_quality_tiers():
    """Demo: Separate queries into quality tiers."""
    print("\n" + "="*70)
    print("DEMO 3: Quality Tiers")
    print("="*70)

    # Create test logs
    log_file = create_example_logs_with_quality_variation()

    print(f"\n[1] Extracting and categorizing by quality...")

    tiers = extract_with_quality_tiers(log_file, "jsonl")

    print(f"\n[2] Quality Tiers:")
    print(f"  Excellent (0.8+): {len(tiers['excellent'])} queries")
    for q in tiers['excellent']:
        print(f"    - {q['user_query'][:60]}")

    print(f"\n  Good (0.6-0.8): {len(tiers['good'])} queries")
    for q in tiers['good']:
        print(f"    - {q['user_query'][:60]}")

    print(f"\n  Fair (0.4-0.6): {len(tiers['fair'])} queries")
    for q in tiers['fair']:
        print(f"    - {q['user_query'][:60]}")

    print(f"\n  Poor (<0.4): {len(tiers['poor'])} queries")
    for q in tiers['poor']:
        print(f"    - {q['user_query'][:60]}")

    print(f"\n[3] Usage:")
    print(f"  - Use 'excellent' tier for your core eval dataset")
    print(f"  - Use 'good' tier for regression tests")
    print(f"  - Review 'fair' tier manually (might contain edge cases)")
    print(f"  - Skip or use 'poor' tier as negative examples")

    # Clean up
    import os
    os.unlink(log_file)


def demo_smart_extraction():
    """Demo: Smart extraction with integrated filtering."""
    print("\n" + "="*70)
    print("DEMO 4: Smart Extraction (Integrated)")
    print("="*70)

    # Create test logs
    log_file = create_example_logs_with_quality_variation()

    print(f"\n[1] Smart extraction with quality filtering...")

    extractor = SmartLogExtractor(
        use_llm_evaluation=False,  # Fast mode for demo
        min_score=0.5
    )

    result = extractor.extract_and_filter(
        log_file,
        output_report=True
    )

    print(f"\n[2] Extraction Stats:")
    print(f"  Total extracted: {result['stats']['total_extracted']}")
    print(f"  Passed filter: {result['stats']['passed_filter']}")
    print(f"  Filter rate: {result['stats']['filter_rate']:.1%}")
    print(f"  Average score: {result['stats']['average_score']:.2f}")

    print(f"\n[3] Filtered queries (good examples):")
    for q in result['filtered_queries']:
        print(f"  ✓ {q['user_query']}")

    # Clean up
    import os
    os.unlink(log_file)


def demo_conversation_evaluation():
    """Demo: Evaluate multi-turn conversations."""
    print("\n" + "="*70)
    print("DEMO 5: Conversation Quality Evaluation")
    print("="*70)

    evaluator = ConversationQualityEvaluator(use_llm=False)

    # Good conversation
    good_conversation = [
        {
            "user_query": "Find concerts in Berlin",
            "action": "QUERY_DB",
            "result_count": 15,
        },
        {
            "user_query": "What about jazz specifically?",
            "action": "QUERY_DB",
            "result_count": 5,
        },
        {
            "user_query": "Thanks, that's perfect!",
            "action": "BYE_MESSAGE",
        }
    ]

    print("\n[1] Good Conversation:")
    for i, turn in enumerate(good_conversation, 1):
        print(f"  Turn {i}: {turn['user_query']}")

    score = evaluator.evaluate_conversation(good_conversation)
    print(f"\n  Score: {score.overall_score:.2f}")
    print(f"  Good Example: {'✓' if score.is_good_example else '✗'}")
    print(f"  Reasoning: {score.reasoning}")

    # Poor conversation
    poor_conversation = [
        {
            "user_query": "show me events",
            "action": "NEEDS_INFO",
            "result_count": 0,
        },
        {
            "user_query": "events",
            "action": "NEEDS_INFO",
            "result_count": 0,
        }
    ]

    print("\n[2] Poor Conversation (Stuck, No Progression):")
    for i, turn in enumerate(poor_conversation, 1):
        print(f"  Turn {i}: {turn['user_query']}")

    score = evaluator.evaluate_conversation(poor_conversation)
    print(f"\n  Score: {score.overall_score:.2f}")
    print(f"  Good Example: {'✓' if score.is_good_example else '✗'}")
    print(f"  Reasoning: {score.reasoning}")


def main():
    print("\n" + "="*70)
    print("QUALITY FILTERING DEMO")
    print("Automatic quality evaluation for evaluation datasets")
    print("="*70)

    # Run all demos
    demo_single_query_evaluation()
    demo_batch_filtering()
    demo_quality_tiers()
    demo_smart_extraction()
    demo_conversation_evaluation()

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("\nQuality filtering helps you:")
    print("  ✓ Automatically filter out low-quality logs")
    print("  ✓ Focus on successful, clear user interactions")
    print("  ✓ Build high-quality evaluation datasets")
    print("  ✓ Save time on manual review")

    print("\nNext steps:")
    print("  1. Read: evals/QUALITY_FILTERING_GUIDE.md")
    print("  2. Try on your logs:")
    print("     from evals.utils.smart_extraction import SmartLogExtractor")
    print("     extractor = SmartLogExtractor()")
    print("     extractor.extract_filter_and_create_datasets('your_logs.jsonl')")
    print("  3. Review quality reports in evals/reports/")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
