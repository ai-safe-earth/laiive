#!/usr/bin/env python3
"""
Demo: Extract queries from logs and create evaluation datasets.

This is a runnable demo showing how to use the log extraction tools.
"""
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.utils.log_to_dataset import LogToDatasetConverter


def create_example_logs():
    """Create example log file to demonstrate extraction."""
    example_logs = [
        {
            "timestamp": "2026-01-22T10:30:00",
            "message": "Find jazz concerts in Berlin this weekend",
            "action": "QUERY_DB",
            "cypher": "MATCH (e:Event)-[:LOCATED_IN]->(c:City {name: 'Berlin'}) WHERE e.genre = 'jazz' RETURN e",
            "result_count": 5,
            "latency_ms": 450,
        },
        {
            "timestamp": "2026-01-22T10:31:00",
            "message": "What about tomorrow?",
            "action": "QUERY_DB",
            "result_count": 3,
            "latency_ms": 380,
        },
        {
            "timestamp": "2026-01-22T10:32:00",
            "message": "Show me concerts",
            "action": "NEEDS_INFO",
            "result_count": 0,
            "latency_ms": 250,
        },
        {
            "timestamp": "2026-01-22T10:33:00",
            "message": "Are there any Radiohead concerts?",
            "action": "QUERY_DB",
            "cypher": "MATCH (a:Artist {name: 'Radiohead'})-[:PERFORMS_AT]->(e:Event) RETURN e",
            "result_count": 2,
            "latency_ms": 420,
        },
        {
            "timestamp": "2026-01-22T10:34:00",
            "message": "What's the weather like?",
            "action": "OUT_OF_SCOPE",
            "result_count": 0,
            "latency_ms": 200,
        },
        {
            "timestamp": "2026-01-22T10:35:00",
            "message": "Thanks, goodbye!",
            "action": "BYE_MESSAGE",
            "result_count": 0,
            "latency_ms": 180,
        },
        {
            "timestamp": "2026-01-22T11:00:00",
            "message": "techno events in Berlin under 20 euros this Friday night",
            "action": "QUERY_DB",
            "cypher": "MATCH (e:Event)-[:LOCATED_IN]->(c:City {name: 'Berlin'}) WHERE e.genre = 'techno' AND e.price_amount < 20 RETURN e",
            "result_count": 8,
            "latency_ms": 520,
        },
        {
            "timestamp": "2026-01-22T11:15:00",
            "message": "What events are happening at Berghain next month?",
            "action": "QUERY_DB",
            "cypher": "MATCH (v:Venue {name: 'Berghain'})<-[:HOSTED_AT]-(e:Event) RETURN e",
            "result_count": 12,
            "latency_ms": 490,
        },
    ]

    # Create temp log file
    log_file = NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)

    for log_entry in example_logs:
        log_file.write(json.dumps(log_entry) + "\n")

    log_file.close()
    return log_file.name


def main():
    print("="*70)
    print("DEMO: Extract Queries from Logs & Create Eval Datasets")
    print("="*70)

    # Step 1: Create example logs
    print("\n[Step 1] Creating example log file...")
    log_file = create_example_logs()
    print(f"✓ Created: {log_file}")

    # Show log contents
    print("\nExample log entries:")
    with open(log_file) as f:
        for i, line in enumerate(f, 1):
            if i <= 3:
                log = json.loads(line)
                print(f"  {i}. {log['message']} → {log['action']}")
    print(f"  ... (8 total entries)")

    # Step 2: Extract queries
    print("\n[Step 2] Extracting queries from logs...")
    converter = LogToDatasetConverter(output_dir="evals/datasets_demo")
    queries = converter.extract_from_api_logs(log_file, log_format="jsonl")

    print(f"✓ Extracted {len(queries)} queries")

    # Step 3: Create query generation dataset
    print("\n[Step 3] Creating query generation dataset...")
    qg_path = converter.create_query_generation_dataset(
        queries,
        output_file="query_generation/demo_queries.json",
        auto_categorize=True
    )

    # Step 4: Create intent classification dataset
    print("\n[Step 4] Creating intent classification dataset...")
    ic_path = converter.create_intent_classification_dataset(
        queries,
        output_file="intent_classification/demo_queries.json"
    )

    # Step 5: Sample queries
    print("\n[Step 5] Demonstrating sampling strategies...")

    print("\nDiverse sampling (5 queries):")
    diverse = converter.sample_queries(queries, n=5, strategy="diverse")
    for q in diverse:
        print(f"  - {q['user_query']}")

    # Step 6: Show what was created
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    print(f"\n✓ Created datasets:")
    print(f"  1. Query Generation: {qg_path}")
    print(f"  2. Intent Classification: {ic_path}")

    # Show sample test case
    print(f"\nExample test case from query generation dataset:")
    with open(qg_path) as f:
        dataset = json.load(f)
        test_case = dataset["test_cases"][0]
        print(f"  ID: {test_case['id']}")
        print(f"  Query: {test_case['user_query']}")
        print(f"  Category: {test_case['category']}")
        print(f"  Expected patterns: {test_case['expected_patterns']}")
        if test_case.get("actual_cypher_generated"):
            print(f"  Ground truth: YES (Cypher from logs included)")

    # Next steps
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("\n1. Review and annotate the generated datasets:")
    print(f"   python evals/utils/manual_annotation.py {qg_path}")

    print("\n2. Run evaluations with your datasets:")
    print("   python evals/run_evals.py --component query_builder")

    print("\n3. For your actual production logs:")
    print("   python -c \"")
    print("   from evals.utils.log_to_dataset import LogToDatasetConverter")
    print("   converter = LogToDatasetConverter()")
    print("   queries = converter.extract_from_api_logs('path/to/your/logs.jsonl')")
    print("   converter.create_query_generation_dataset(queries)")
    print("   \"")

    print("\n4. Read the guides:")
    print("   - evals/QUICK_START.md - Quick reference")
    print("   - evals/DATASET_GUIDE.md - Detailed guide")

    print("\n" + "="*70)

    # Clean up temp file
    import os
    os.unlink(log_file)


if __name__ == "__main__":
    main()
