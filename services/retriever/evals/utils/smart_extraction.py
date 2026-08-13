"""
Smart log extraction with automatic quality filtering.

This module combines log extraction with quality evaluation to automatically
filter for good examples.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evals.utils.log_to_dataset import LogToDatasetConverter
from evals.utils.quality_filter import ConversationQualityEvaluator


class SmartLogExtractor:
    """Extract logs with automatic quality filtering."""

    def __init__(
        self,
        use_llm_evaluation: bool = True,
        min_score: float = 0.5,
        min_confidence: float = 0.6,
    ):
        """
        Initialize smart extractor.

        Args:
            use_llm_evaluation: Use LLM for quality evaluation (more accurate but slower/costs)
            min_score: Minimum quality score (0.0-1.0)
            min_confidence: Minimum confidence threshold (0.0-1.0)
        """
        self.converter = LogToDatasetConverter()
        self.evaluator = ConversationQualityEvaluator(use_llm=use_llm_evaluation)
        self.min_score = min_score
        self.min_confidence = min_confidence

    def extract_and_filter(
        self, log_file: str, log_format: str = "jsonl", output_report: bool = True
    ) -> Dict[str, any]:
        """
        Extract queries from logs and filter for quality.

        Args:
            log_file: Path to log file
            log_format: Format of logs
            output_report: Generate quality report

        Returns:
            Dict with filtered queries, scores, and stats
        """
        print(f"\n{'='*70}")
        print("SMART LOG EXTRACTION WITH QUALITY FILTERING")
        print(f"{'='*70}")

        # Step 1: Extract raw queries
        print("\n[Step 1] Extracting queries from logs...")
        all_queries = self.converter.extract_from_api_logs(log_file, log_format)

        if not all_queries:
            print("No queries found in logs")
            return {
                "filtered_queries": [],
                "scores": [],
                "stats": {
                    "total_extracted": 0,
                    "passed_filter": 0,
                    "filter_rate": 0,
                    "average_score": 0,
                },
            }

        # Step 2: Evaluate quality
        print(f"\n[Step 2] Evaluating quality (min_score: {self.min_score})...")
        filtered_queries, scores = self.evaluator.batch_evaluate(
            all_queries, min_score=self.min_score, min_confidence=self.min_confidence
        )

        # Step 3: Generate report
        stats = {
            "total_extracted": len(all_queries),
            "passed_filter": len(filtered_queries),
            "filter_rate": (
                len(filtered_queries) / len(all_queries) if all_queries else 0
            ),
            "average_score": (
                sum(s.overall_score for s in scores) / len(scores) if scores else 0
            ),
        }

        if output_report:
            print("\n[Step 3] Generating quality report...")
            self.evaluator.generate_quality_report(
                all_queries,
                scores,
                output_file="evals/reports/extraction_quality_report.json",
            )

        return {
            "filtered_queries": filtered_queries,
            "all_queries": all_queries,
            "scores": scores,
            "stats": stats,
        }

    def extract_filter_and_create_datasets(
        self,
        log_file: str,
        log_format: str = "jsonl",
        sample_size: Optional[int] = None,
        sampling_strategy: str = "diverse",
    ) -> Dict[str, Path]:
        """
        Complete pipeline: extract, filter, sample, create datasets.

        Args:
            log_file: Path to log file
            log_format: Format of logs
            sample_size: Optional limit on number of queries
            sampling_strategy: "diverse", "recent", or "random"

        Returns:
            Dict with paths to created datasets
        """
        # Extract and filter
        result = self.extract_and_filter(log_file, log_format, output_report=True)
        filtered_queries = result["filtered_queries"]

        if not filtered_queries:
            print("\n⚠️  No queries passed quality filter!")
            return {}

        # Sample if needed
        if sample_size and len(filtered_queries) > sample_size:
            print(
                f"\n[Step 4] Sampling {sample_size} queries (strategy: {sampling_strategy})..."
            )
            filtered_queries = self.converter.sample_queries(
                filtered_queries, n=sample_size, strategy=sampling_strategy
            )

        # Create datasets
        print("\n[Step 5] Creating evaluation datasets...")
        qg_path = self.converter.create_query_generation_dataset(
            filtered_queries,
            output_file="query_generation/filtered_queries.json",
            auto_categorize=True,
        )

        ic_path = self.converter.create_intent_classification_dataset(
            filtered_queries, output_file="intent_classification/filtered_queries.json"
        )

        return {"query_generation": qg_path, "intent_classification": ic_path}


def extract_with_quality_tiers(
    log_file: str, log_format: str = "jsonl"
) -> Dict[str, List[Dict]]:
    """
    Extract queries and separate into quality tiers.

    Useful for creating different difficulty levels in your eval dataset.

    Args:
        log_file: Path to log file
        log_format: Format of logs

    Returns:
        Dict with queries organized by quality tier
    """
    print(f"\n{'='*70}")
    print("EXTRACTING WITH QUALITY TIERS")
    print(f"{'='*70}")

    converter = LogToDatasetConverter()
    evaluator = ConversationQualityEvaluator(use_llm=False)  # Fast heuristic mode

    # Extract
    all_queries = converter.extract_from_api_logs(log_file, log_format)

    # Evaluate
    print(f"\nEvaluating {len(all_queries)} queries...")
    scores = [evaluator.evaluate_single_query(q) for q in all_queries]

    # Separate into tiers
    tiers = {
        "excellent": [],  # 0.8+: Use for production evals
        "good": [],  # 0.6-0.8: Use for regression tests
        "fair": [],  # 0.4-0.6: Review manually, might be edge cases
        "poor": [],  # <0.4: Skip or use as negative examples
    }

    for query, score in zip(all_queries, scores):
        if score.overall_score >= 0.8:
            tiers["excellent"].append(query)
        elif score.overall_score >= 0.6:
            tiers["good"].append(query)
        elif score.overall_score >= 0.4:
            tiers["fair"].append(query)
        else:
            tiers["poor"].append(query)

    # Print summary
    print("\nQuality Tiers:")
    print(f"  Excellent (0.8+): {len(tiers['excellent'])} queries")
    print(f"  Good (0.6-0.8): {len(tiers['good'])} queries")
    print(f"  Fair (0.4-0.6): {len(tiers['fair'])} queries")
    print(f"  Poor (<0.4): {len(tiers['poor'])} queries")

    return tiers


def extract_with_llm_selection(
    log_file: str, log_format: str = "jsonl", target_count: int = 50
) -> List[Dict]:
    """
    Use LLM to intelligently select the most useful examples.

    More expensive but very high quality - use for your core eval dataset.

    Args:
        log_file: Path to log file
        log_format: Format of logs
        target_count: Target number of examples to select

    Returns:
        List of selected high-quality queries
    """
    print(f"\n{'='*70}")
    print(f"LLM-POWERED SMART SELECTION (Target: {target_count} examples)")
    print(f"{'='*70}")

    # Step 1: Quick heuristic filter to reduce LLM calls
    print("\n[Step 1] Initial filtering with heuristics...")
    extractor = SmartLogExtractor(use_llm_evaluation=False, min_score=0.4)
    result = extractor.extract_and_filter(log_file, log_format, output_report=False)
    candidates = result["filtered_queries"]

    print(f"  Filtered to {len(candidates)} candidates")

    # Step 2: If we have too many, sample diverse examples
    if len(candidates) > target_count * 3:
        print("\n[Step 2] Sampling diverse subset for LLM evaluation...")
        converter = LogToDatasetConverter()
        candidates = converter.sample_queries(
            candidates, n=target_count * 3, strategy="diverse"
        )

    # Step 3: LLM evaluation of candidates
    print(f"\n[Step 3] LLM evaluation of {len(candidates)} candidates...")
    print("  (This may take a moment...)")

    evaluator = ConversationQualityEvaluator(use_llm=True)
    scores = [evaluator.evaluate_single_query(q) for q in candidates]

    # Step 4: Select top N by LLM score
    print(f"\n[Step 4] Selecting top {target_count} examples...")
    scored_pairs = sorted(
        zip(candidates, scores), key=lambda x: x[1].overall_score, reverse=True
    )

    selected = [q for q, s in scored_pairs[:target_count]]

    print(f"\n✓ Selected {len(selected)} high-quality examples")
    print(
        f"  Score range: {scored_pairs[-1][1].overall_score:.2f} - {scored_pairs[0][1].overall_score:.2f}"
    )

    return selected


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Smart log extraction with quality filtering"
    )
    parser.add_argument("log_file", help="Path to log file")
    parser.add_argument(
        "--format",
        choices=["json", "jsonl", "text"],
        default="jsonl",
        help="Log format",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "balanced", "llm"],
        default="balanced",
        help="Extraction mode (fast=heuristics only, balanced=selective LLM, llm=full LLM)",
    )
    parser.add_argument("--sample", type=int, help="Sample size (optional)")

    args = parser.parse_args()

    if args.mode == "fast":
        extractor = SmartLogExtractor(use_llm_evaluation=False)
        result = extractor.extract_filter_and_create_datasets(
            args.log_file, args.format, sample_size=args.sample
        )

    elif args.mode == "balanced":
        extractor = SmartLogExtractor(use_llm_evaluation=True, min_score=0.6)
        result = extractor.extract_filter_and_create_datasets(
            args.log_file, args.format, sample_size=args.sample
        )

    elif args.mode == "llm":
        queries = extract_with_llm_selection(
            args.log_file, args.format, target_count=args.sample or 50
        )
        converter = LogToDatasetConverter()
        converter.create_query_generation_dataset(queries)
        converter.create_intent_classification_dataset(queries)

    print("\n✓ Smart extraction complete!")
