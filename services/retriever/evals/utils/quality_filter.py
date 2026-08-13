"""
Quality filtering and scoring for extracted logs.

Automatically evaluate which logs are good examples for evaluation datasets.
Uses both heuristic rules and LLM-based evaluation to determine conversation quality.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from agent.utils.llm_utils import get_openai_client

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class QualityScore:
    """Quality score for a query or conversation."""

    overall_score: float  # 0.0 to 1.0
    is_good_example: bool
    confidence: float  # How confident we are in the score
    signals: Dict[str, Any]  # Individual quality signals
    reasoning: str  # Why this score was assigned


class ConversationQualityEvaluator:
    """Evaluate conversation quality using multiple signals."""

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        if use_llm:
            self.client = get_openai_client()

    def evaluate_single_query(self, query_data: Dict) -> QualityScore:
        """
        Evaluate a single query for dataset quality.

        Args:
            query_data: Query with metadata (from log extraction)

        Returns:
            QualityScore with assessment
        """
        signals = {}
        score_components = []

        # Signal 1: Query has actual content
        query_text = query_data.get("user_query", "").strip()
        signals["has_content"] = len(query_text) > 0
        signals["query_length"] = len(query_text)
        signals["is_reasonable_length"] = 5 < len(query_text.split()) < 100

        if signals["has_content"] and signals["is_reasonable_length"]:
            score_components.append(0.3)

        # Signal 2: System successfully processed it
        action = query_data.get("action")
        signals["has_action"] = action is not None
        signals["action"] = action

        # Good actions indicate successful processing
        good_actions = ["QUERY_DB", "NEEDS_INFO"]
        if action in good_actions:
            score_components.append(0.2)
            signals["successful_action"] = True
        elif action == "OUT_OF_SCOPE":
            # Out of scope is OK if intentional (for negative examples)
            score_components.append(0.1)
            signals["successful_action"] = False
        else:
            signals["successful_action"] = False

        # Signal 3: Query executed and returned results (if applicable)
        if action == "QUERY_DB":
            result_count = query_data.get("result_count", 0)
            signals["returned_results"] = result_count > 0
            signals["result_count"] = result_count

            # Good: returned 1-50 results
            if 1 <= result_count <= 50:
                score_components.append(0.3)
            # OK: returned many results (might be too broad)
            elif result_count > 50:
                score_components.append(0.15)
            # Bad: no results (might be broken query)
            else:
                score_components.append(0.0)

        # Signal 4: Latency is reasonable (not timeout/error)
        latency = query_data.get("latency_ms", 0)
        signals["latency_ms"] = latency
        if 0 < latency < 5000:  # Less than 5 seconds
            score_components.append(0.1)
            signals["reasonable_latency"] = True
        else:
            signals["reasonable_latency"] = False

        # Signal 5: No errors
        error = query_data.get("error")
        signals["has_error"] = error is not None
        if not error:
            score_components.append(0.1)

        # Calculate score
        overall_score = sum(score_components)
        confidence = 0.8  # Heuristic confidence

        # Decision threshold
        is_good_example = overall_score >= 0.5

        # Generate reasoning
        reasoning_parts = []
        if signals.get("successful_action"):
            reasoning_parts.append(f"Successfully processed as {action}")
        if signals.get("returned_results"):
            reasoning_parts.append(f"Returned {signals['result_count']} results")
        if signals.get("has_error"):
            reasoning_parts.append("Had errors")
        if not signals.get("is_reasonable_length"):
            reasoning_parts.append("Query length unusual")

        reasoning = (
            "; ".join(reasoning_parts)
            if reasoning_parts
            else "Basic quality checks passed"
        )

        return QualityScore(
            overall_score=overall_score,
            is_good_example=is_good_example,
            confidence=confidence,
            signals=signals,
            reasoning=reasoning,
        )

    def evaluate_conversation(self, conversation: List[Dict]) -> QualityScore:
        """
        Evaluate a multi-turn conversation for quality.

        Args:
            conversation: List of turns in conversation

        Returns:
            QualityScore for the entire conversation
        """
        if not conversation:
            return QualityScore(
                overall_score=0.0,
                is_good_example=False,
                confidence=1.0,
                signals={"empty": True},
                reasoning="Empty conversation",
            )

        signals = {}
        score_components = []

        # Signal 1: Conversation length
        num_turns = len(conversation)
        signals["num_turns"] = num_turns
        signals["is_multi_turn"] = num_turns >= 2

        if 2 <= num_turns <= 10:
            score_components.append(0.2)
        elif num_turns == 1:
            score_components.append(0.1)

        # Signal 2: Successful query execution
        query_turns = [t for t in conversation if t.get("action") == "QUERY_DB"]
        signals["num_query_turns"] = len(query_turns)
        signals["has_successful_query"] = len(query_turns) > 0

        if signals["has_successful_query"]:
            score_components.append(0.3)

        # Signal 3: Context-dependent queries (shows user engagement)
        context_indicators = [
            "that",
            "those",
            "it",
            "them",
            "also",
            "too",
            "what about",
        ]
        context_dependent_turns = sum(
            1
            for t in conversation
            if any(ind in t.get("user_query", "").lower() for ind in context_indicators)
        )
        signals["context_dependent_turns"] = context_dependent_turns

        if context_dependent_turns > 0:
            score_components.append(0.2)

        # Signal 4: No excessive errors
        error_turns = sum(1 for t in conversation if t.get("error"))
        signals["error_turns"] = error_turns
        signals["error_rate"] = error_turns / num_turns if num_turns > 0 else 0

        if signals["error_rate"] < 0.3:  # Less than 30% errors
            score_components.append(0.2)

        # Signal 5: Conversation progression (not just repeating)
        unique_queries = len(set(t.get("user_query", "") for t in conversation))
        signals["unique_queries"] = unique_queries
        signals["has_progression"] = unique_queries > 1

        if signals["has_progression"]:
            score_components.append(0.1)

        overall_score = sum(score_components)
        confidence = 0.75

        # Use LLM for additional evaluation if enabled
        if self.use_llm and num_turns >= 2:
            llm_score = self._llm_evaluate_conversation(conversation)
            if llm_score is not None:
                # Blend heuristic and LLM scores
                overall_score = (overall_score * 0.6) + (llm_score.overall_score * 0.4)
                confidence = (confidence * 0.5) + (llm_score.confidence * 0.5)
                signals["llm_evaluation"] = llm_score.signals

        is_good_example = overall_score >= 0.6

        reasoning = self._generate_conversation_reasoning(signals)

        return QualityScore(
            overall_score=overall_score,
            is_good_example=is_good_example,
            confidence=confidence,
            signals=signals,
            reasoning=reasoning,
        )

    def _llm_evaluate_conversation(
        self, conversation: List[Dict]
    ) -> Optional[QualityScore]:
        """Use LLM to evaluate conversation quality and user satisfaction."""
        try:
            # Format conversation for LLM
            conversation_text = self._format_conversation_for_llm(conversation)

            prompt = f"""Evaluate this conversation between a user and a live music event search assistant.

Conversation:
{conversation_text}

Analyze the conversation and determine:
1. User satisfaction: Was the user satisfied with the results? (0-10)
2. Conversation success: Did the assistant successfully help the user? (0-10)
3. User engagement: Did the user actively engage and refine their search? (0-10)
4. Example quality: Would this be a good example for training/evaluation? (0-10)

Look for signals like:
- User asking follow-up questions (positive engagement)
- User thanking or expressing satisfaction (positive)
- User getting frustrated or repeating questions (negative)
- Successful query execution with results (positive)
- Assistant asking clarifying questions (good interaction)
- User abruptly ending or switching topics (might be negative)

Respond in JSON format:
{{
  "user_satisfaction": <0-10>,
  "conversation_success": <0-10>,
  "user_engagement": <0-10>,
  "example_quality": <0-10>,
  "is_good_example": <true/false>,
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>",
  "positive_signals": ["signal1", "signal2", ...],
  "negative_signals": ["signal1", "signal2", ...]
}}"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for cost efficiency
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            # Convert to QualityScore
            overall_score = result.get("example_quality", 5) / 10.0

            return QualityScore(
                overall_score=overall_score,
                is_good_example=result.get("is_good_example", overall_score >= 0.6),
                confidence=result.get("confidence", 0.7),
                signals={
                    "user_satisfaction": result.get("user_satisfaction"),
                    "conversation_success": result.get("conversation_success"),
                    "user_engagement": result.get("user_engagement"),
                    "positive_signals": result.get("positive_signals", []),
                    "negative_signals": result.get("negative_signals", []),
                },
                reasoning=result.get("reasoning", "LLM evaluation"),
            )

        except Exception as e:
            print(f"LLM evaluation failed: {e}")
            return None

    def _format_conversation_for_llm(self, conversation: List[Dict]) -> str:
        """Format conversation for LLM evaluation."""
        formatted = []
        for i, turn in enumerate(conversation, 1):
            user_msg = turn.get("user_query", "")
            action = turn.get("action", "UNKNOWN")
            results = turn.get("result_count", 0)

            formatted.append(f"Turn {i}:")
            formatted.append(f"  User: {user_msg}")
            formatted.append(f"  System Action: {action}")

            if action == "QUERY_DB":
                if results > 0:
                    formatted.append(f"  System Result: Found {results} events")
                else:
                    formatted.append("  System Result: No events found")
            elif action == "NEEDS_INFO":
                formatted.append("  System Result: Asked for more information")
            elif action == "OUT_OF_SCOPE":
                formatted.append("  System Result: Query out of scope")

            if turn.get("error"):
                formatted.append(f"  Error: {turn['error']}")

            formatted.append("")

        return "\n".join(formatted)

    def _generate_conversation_reasoning(self, signals: Dict) -> str:
        """Generate human-readable reasoning for conversation score."""
        parts = []

        if signals.get("is_multi_turn"):
            parts.append(f"{signals['num_turns']} turn conversation")

        if signals.get("has_successful_query"):
            parts.append(f"{signals['num_query_turns']} successful queries")

        if signals.get("context_dependent_turns", 0) > 0:
            parts.append("shows context awareness")

        if signals.get("error_rate", 0) > 0:
            parts.append(f"{signals['error_rate']:.0%} error rate")

        if signals.get("has_progression"):
            parts.append("conversation progresses")

        if signals.get("llm_evaluation"):
            llm_sigs = signals["llm_evaluation"]
            if "positive_signals" in llm_sigs:
                parts.append(
                    f"LLM detected: {', '.join(llm_sigs['positive_signals'][:2])}"
                )

        return "; ".join(parts) if parts else "Basic quality checks"

    def batch_evaluate(
        self, queries: List[Dict], min_score: float = 0.5, min_confidence: float = 0.6
    ) -> Tuple[List[Dict], List[QualityScore]]:
        """
        Evaluate a batch of queries and filter for quality.

        Args:
            queries: List of queries to evaluate
            min_score: Minimum score to include (0.0-1.0)
            min_confidence: Minimum confidence to include (0.0-1.0)

        Returns:
            Tuple of (filtered_queries, all_scores)
        """
        print(f"\nEvaluating {len(queries)} queries for quality...")

        scores = []
        filtered = []

        for i, query in enumerate(queries):
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(queries)}...", end="\r")

            score = self.evaluate_single_query(query)
            scores.append(score)

            if score.overall_score >= min_score and score.confidence >= min_confidence:
                filtered.append(query)

        print(
            f"\n✓ Filtered: {len(filtered)}/{len(queries)} queries passed quality checks"
        )
        if scores:
            print(
                f"  Average score: {sum(s.overall_score for s in scores) / len(scores):.2f}"
            )
            print(
                f"  Average confidence: {sum(s.confidence for s in scores) / len(scores):.2f}"
            )
        else:
            print("  No queries to evaluate")

        return filtered, scores

    def batch_evaluate_conversations(
        self,
        conversations: List[List[Dict]],
        min_score: float = 0.6,
        use_llm_for_all: bool = False,
    ) -> Tuple[List[List[Dict]], List[QualityScore]]:
        """
        Evaluate and filter conversations for quality.

        Args:
            conversations: List of conversations (each is list of turns)
            min_score: Minimum score threshold
            use_llm_for_all: Use LLM evaluation for all (slower but more accurate)

        Returns:
            Tuple of (filtered_conversations, all_scores)
        """
        print(f"\nEvaluating {len(conversations)} conversations for quality...")

        # For efficiency: use heuristics for initial filter, then LLM for borderline cases
        scores = []
        filtered = []

        for i, conversation in enumerate(conversations):
            if (i + 1) % 5 == 0:
                print(f"  Processed {i + 1}/{len(conversations)}...", end="\r")

            # Always evaluate with heuristics
            score = self.evaluate_conversation(conversation)
            scores.append(score)

            # If borderline and LLM available, get second opinion
            if (
                not use_llm_for_all
                and 0.4 <= score.overall_score < 0.7
                and self.use_llm
            ):
                llm_score = self._llm_evaluate_conversation(conversation)
                if llm_score:
                    score = llm_score
                    scores[-1] = llm_score

            if score.overall_score >= min_score:
                filtered.append(conversation)

        print(
            f"\n✓ Filtered: {len(filtered)}/{len(conversations)} conversations passed"
        )
        print(
            f"  Average score: {sum(s.overall_score for s in scores) / len(scores):.2f}"
        )

        return filtered, scores

    def generate_quality_report(
        self,
        queries: List[Dict],
        scores: List[QualityScore],
        output_file: Optional[str] = None,
    ):
        """Generate a detailed quality report."""
        report = {
            "total_queries": len(queries),
            "good_examples": sum(1 for s in scores if s.is_good_example),
            "average_score": sum(s.overall_score for s in scores) / len(scores),
            "average_confidence": sum(s.confidence for s in scores) / len(scores),
            "score_distribution": self._score_distribution(scores),
            "common_issues": self._identify_common_issues(queries, scores),
            "top_examples": self._get_top_examples(queries, scores, n=10),
            "bottom_examples": self._get_bottom_examples(queries, scores, n=10),
        }

        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n✓ Quality report saved to: {output_file}")

        # Print summary
        self._print_quality_summary(report)

        return report

    def _score_distribution(self, scores: List[QualityScore]) -> Dict:
        """Calculate score distribution."""
        ranges = {
            "excellent (0.8-1.0)": sum(1 for s in scores if s.overall_score >= 0.8),
            "good (0.6-0.8)": sum(1 for s in scores if 0.6 <= s.overall_score < 0.8),
            "fair (0.4-0.6)": sum(1 for s in scores if 0.4 <= s.overall_score < 0.6),
            "poor (0.0-0.4)": sum(1 for s in scores if s.overall_score < 0.4),
        }
        return ranges

    def _identify_common_issues(
        self, queries: List[Dict], scores: List[QualityScore]
    ) -> Dict[str, int]:
        """Identify common quality issues."""
        issues = {}

        for query, score in zip(queries, scores):
            if not score.is_good_example:
                # Categorize issues
                if score.signals.get("has_error"):
                    issues["has_errors"] = issues.get("has_errors", 0) + 1

                if not score.signals.get("is_reasonable_length"):
                    issues["bad_length"] = issues.get("bad_length", 0) + 1

                if not score.signals.get("successful_action"):
                    issues["failed_processing"] = issues.get("failed_processing", 0) + 1

                if score.signals.get("action") == "QUERY_DB" and not score.signals.get(
                    "returned_results"
                ):
                    issues["no_results"] = issues.get("no_results", 0) + 1

        return issues

    def _get_top_examples(
        self, queries: List[Dict], scores: List[QualityScore], n: int = 10
    ) -> List[Dict]:
        """Get top N queries by score."""
        sorted_pairs = sorted(
            zip(queries, scores), key=lambda x: x[1].overall_score, reverse=True
        )
        return [
            {
                "query": q.get("user_query"),
                "score": s.overall_score,
                "reasoning": s.reasoning,
            }
            for q, s in sorted_pairs[:n]
        ]

    def _get_bottom_examples(
        self, queries: List[Dict], scores: List[QualityScore], n: int = 10
    ) -> List[Dict]:
        """Get bottom N queries by score."""
        sorted_pairs = sorted(zip(queries, scores), key=lambda x: x[1].overall_score)
        return [
            {
                "query": q.get("user_query"),
                "score": s.overall_score,
                "reasoning": s.reasoning,
            }
            for q, s in sorted_pairs[:n]
        ]

    def _print_quality_summary(self, report: Dict):
        """Print quality report summary."""
        print(f"\n{'='*70}")
        print("QUALITY ASSESSMENT SUMMARY")
        print(f"{'='*70}")

        print("\nOverall Stats:")
        print(f"  Total queries: {report['total_queries']}")
        print(
            f"  Good examples: {report['good_examples']} ({report['good_examples']/report['total_queries']:.1%})"
        )
        print(f"  Average score: {report['average_score']:.2f}")
        print(f"  Average confidence: {report['average_confidence']:.2f}")

        print("\nScore Distribution:")
        for range_name, count in report["score_distribution"].items():
            percentage = count / report["total_queries"] * 100
            print(f"  {range_name}: {count} ({percentage:.1f}%)")

        if report["common_issues"]:
            print("\nCommon Issues:")
            for issue, count in sorted(
                report["common_issues"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {issue}: {count}")

        print("\nTop 3 Examples:")
        for i, ex in enumerate(report["top_examples"][:3], 1):
            print(f"  {i}. {ex['query'][:60]}... (score: {ex['score']:.2f})")

        print(f"{'='*70}\n")


if __name__ == "__main__":
    # Example usage
    print("Quality filter module ready. Import and use in your extraction pipeline.")
