"""
Utility to convert user logs/queries into evaluation datasets.

This helps you build comprehensive eval datasets from real production usage.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class LogToDatasetConverter:
    """Convert user logs to evaluation datasets."""

    def __init__(self, output_dir: str = "evals/datasets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_from_api_logs(
        self, log_file: str, log_format: str = "json"
    ) -> List[Dict[str, Any]]:
        """
        Extract queries from API logs.

        Args:
            log_file: Path to log file
            log_format: Format of logs ("json", "text", "jsonl")

        Returns:
            List of extracted queries with metadata
        """
        queries = []

        with open(log_file, "r") as f:
            if log_format == "jsonl":
                for line in f:
                    try:
                        log_entry = json.loads(line)
                        query = self._extract_query_from_log_entry(log_entry)
                        if query:
                            queries.append(query)
                    except json.JSONDecodeError:
                        continue

            elif log_format == "json":
                try:
                    logs = json.load(f)
                    for log_entry in logs:
                        query = self._extract_query_from_log_entry(log_entry)
                        if query:
                            queries.append(query)
                except json.JSONDecodeError:
                    print(f"Error parsing JSON log file: {log_file}")

            elif log_format == "text":
                # Simple text format: one query per line
                for line in f:
                    query = line.strip()
                    if query:
                        queries.append(
                            {
                                "user_query": query,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

        print(f"Extracted {len(queries)} queries from {log_file}")
        return queries

    def _extract_query_from_log_entry(self, log_entry: Dict) -> Optional[Dict]:
        """Extract relevant query info from a log entry."""
        # Adapt this to your log structure
        # Example structures:

        # Structure 1: FastAPI logs with message field
        if "message" in log_entry or "user_message" in log_entry:
            return {
                "user_query": log_entry.get("message") or log_entry.get("user_message"),
                "timestamp": log_entry.get("timestamp", datetime.now().isoformat()),
                "action": log_entry.get("action"),
                "cypher": log_entry.get("cypher"),
                "result_count": log_entry.get("result_count", 0),
                "latency_ms": log_entry.get("latency_ms"),
            }

        # Structure 2: Request/response format
        if "request" in log_entry:
            request = log_entry["request"]
            response = log_entry.get("response", {})
            return {
                "user_query": request.get("message", ""),
                "timestamp": log_entry.get("timestamp", datetime.now().isoformat()),
                "action": response.get("action"),
                "cypher": response.get("cypher"),
                "success": response.get("success", True),
                "error": response.get("error"),
            }

        return None

    def create_query_generation_dataset(
        self,
        queries: List[Dict],
        output_file: str = "query_generation/user_queries.json",
        auto_categorize: bool = True,
    ):
        """
        Create a query generation eval dataset from extracted queries.

        Args:
            queries: List of query dicts from extract_from_api_logs
            output_file: Output file path (relative to output_dir)
            auto_categorize: Automatically categorize queries by type
        """
        test_cases = []

        for i, query_data in enumerate(queries):
            query = query_data.get("user_query", "")
            if not query:
                continue

            # Auto-categorize if enabled
            category = "general"
            expected_patterns = []
            metadata = {"difficulty": "unknown", "source": "production_logs"}

            if auto_categorize:
                category, expected_patterns = self._auto_categorize_query(query)
                metadata["auto_categorized"] = True

            test_case = {
                "id": f"qg_user_{i+1:03d}",
                "category": category,
                "user_query": query,
                "expected_patterns": expected_patterns,
                "should_not_contain": ["DELETE", "CREATE", "MERGE", "SET"],
                "metadata": metadata,
            }

            # Add actual execution data if available
            if "cypher" in query_data and query_data["cypher"]:
                test_case["actual_cypher_generated"] = query_data["cypher"]
                test_case["metadata"]["has_ground_truth"] = True

            if "action" in query_data and query_data["action"]:
                test_case["metadata"]["actual_action"] = query_data["action"]

            test_cases.append(test_case)

        # Save dataset
        dataset = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "description": "Test cases generated from production user logs",
            "source": "production_logs",
            "test_cases": test_cases,
        }

        output_path = self.output_dir / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(dataset, f, indent=2)

        print(f"\nCreated query generation dataset: {output_path}")
        print(f"  Total test cases: {len(test_cases)}")
        self._print_category_breakdown(test_cases)

        return output_path

    def create_intent_classification_dataset(
        self,
        queries: List[Dict],
        output_file: str = "intent_classification/user_queries.json",
    ):
        """Create intent classification dataset from logs."""
        test_cases = []

        for i, query_data in enumerate(queries):
            query = query_data.get("user_query", "")
            if not query:
                continue

            # Infer expected action from logs if available
            expected_action = query_data.get("action")

            # If no action in logs, try to infer
            if not expected_action:
                expected_action = self._infer_action(query)

            test_case = {
                "id": f"ic_user_{i+1:03d}",
                "user_message": query,
                "expected_action": expected_action or "UNKNOWN",
                "conversation_history": [],
                "reasoning": "Extracted from production logs",
                "metadata": {
                    "source": "production_logs",
                    "needs_manual_review": not query_data.get("action"),
                },
            }

            if "action" in query_data:
                test_case["metadata"]["has_ground_truth"] = True

            test_cases.append(test_case)

        dataset = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "description": "Intent classification test cases from production logs",
            "test_cases": test_cases,
        }

        output_path = self.output_dir / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(dataset, f, indent=2)

        print(f"\nCreated intent classification dataset: {output_path}")
        print(f"  Total test cases: {len(test_cases)}")

        # Show action distribution
        actions = [tc["expected_action"] for tc in test_cases]
        action_counts = Counter(actions)
        print("\nAction distribution:")
        for action, count in action_counts.most_common():
            print(f"  {action}: {count}")

        # Warn about cases needing review
        needs_review = sum(
            1 for tc in test_cases if tc["metadata"].get("needs_manual_review")
        )
        if needs_review > 0:
            print(
                f"\n⚠️  {needs_review} cases need manual review (action was inferred, not from logs)"
            )

        return output_path

    def create_end_to_end_dataset(
        self,
        conversation_logs: List[Dict],
        output_file: str = "end_to_end/user_conversations.json",
    ):
        """
        Create end-to-end conversation dataset from multi-turn conversations.

        Args:
            conversation_logs: List of conversations, each with multiple turns
            output_file: Output file path
        """
        conversations = []

        for i, conv_log in enumerate(conversation_logs):
            turns = []

            for turn_data in conv_log.get("turns", []):
                turn = {
                    "user": turn_data.get("user_message", ""),
                    "expected_action": turn_data.get("action", "QUERY_DB"),
                    "success_criteria": {},
                }

                # Add success criteria based on what happened
                if turn_data.get("generated_query"):
                    turn["success_criteria"]["generates_query"] = True

                if turn_data.get("returned_results"):
                    turn["success_criteria"]["returns_results"] = True

                turns.append(turn)

            if turns:
                conversation = {
                    "id": f"e2e_user_{i+1:03d}",
                    "name": conv_log.get("name", f"user_conversation_{i+1}"),
                    "turns": turns,
                    "overall_success_criteria": {
                        "completes_without_errors": True,
                        "provides_relevant_results": True,
                    },
                    "metadata": {
                        "source": "production_logs",
                        "original_session_id": conv_log.get("session_id"),
                    },
                }
                conversations.append(conversation)

        dataset = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "description": "End-to-end conversation scenarios from production",
            "conversations": conversations,
        }

        output_path = self.output_dir / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(dataset, f, indent=2)

        print(f"\nCreated end-to-end dataset: {output_path}")
        print(f"  Total conversations: {len(conversations)}")
        print(f"  Total turns: {sum(len(c['turns']) for c in conversations)}")

        return output_path

    def _auto_categorize_query(self, query: str) -> tuple[str, List[str]]:
        """Automatically categorize a query and suggest expected patterns."""
        query_lower = query.lower()

        # Artist-specific queries
        if any(word in query_lower for word in ["by ", "artist", "band", "musician"]):
            return "artist_query", ["MATCH.*Artist", "PERFORMS_AT"]

        # Venue-specific
        if any(
            word in query_lower for word in ["at ", "venue", "club", "arena", "hall"]
        ):
            return "venue_query", ["Venue", "HOSTED_AT"]

        # Date/time queries
        if any(
            word in query_lower
            for word in [
                "today",
                "tonight",
                "tomorrow",
                "weekend",
                "week",
                "month",
                "date",
            ]
        ):
            return "date_query", ["datetime\\(e\\.start_at\\)"]

        # Location queries
        if any(
            word in query_lower
            for word in ["in ", "near", "city", "berlin", "london", "paris", "york"]
        ):
            return "location_query", ["City", "LOCATED_IN"]

        # Genre queries
        if any(
            word in query_lower
            for word in [
                "jazz",
                "rock",
                "pop",
                "electronic",
                "classical",
                "hip hop",
                "techno",
            ]
        ):
            return "genre_query", ["genre"]

        # Price queries
        if any(
            word in query_lower
            for word in ["cheap", "free", "under", "price", "$", "€", "£"]
        ):
            return "price_query", ["price_amount"]

        return "general", []

    def _infer_action(self, query: str) -> str:
        """Infer expected action from query text."""
        query_lower = query.lower()

        # Goodbye messages
        if any(
            word in query_lower for word in ["bye", "goodbye", "thanks", "thank you"]
        ):
            return "BYE_MESSAGE"

        # Out of scope
        if any(
            word in query_lower
            for word in ["weather", "directions", "book", "buy ticket", "restaurant"]
        ):
            return "OUT_OF_SCOPE"

        # Very vague
        if query_lower in ["concerts", "events", "shows", "music"]:
            return "NEEDS_INFO"

        # Likely valid queries
        return "QUERY_DB"

    def _print_category_breakdown(self, test_cases: List[Dict]):
        """Print breakdown of test cases by category."""
        categories = [tc["category"] for tc in test_cases]
        category_counts = Counter(categories)

        print("\nCategory breakdown:")
        for category, count in category_counts.most_common():
            print(f"  {category}: {count}")

    def sample_queries(
        self, queries: List[Dict], n: int = 50, strategy: str = "random"
    ):
        """
        Sample a subset of queries for manual annotation.

        Args:
            queries: Full list of queries
            n: Number to sample
            strategy: "random", "diverse", or "recent"

        Returns:
            Sampled queries
        """
        import random

        if strategy == "random":
            return random.sample(queries, min(n, len(queries)))

        elif strategy == "recent":
            # Sort by timestamp and take most recent
            sorted_queries = sorted(
                queries, key=lambda q: q.get("timestamp", ""), reverse=True
            )
            return sorted_queries[:n]

        elif strategy == "diverse":
            # Try to get diverse examples
            categorized = {}
            for query in queries:
                category, _ = self._auto_categorize_query(query.get("user_query", ""))
                if category not in categorized:
                    categorized[category] = []
                categorized[category].append(query)

            # Sample evenly from categories
            samples = []
            per_category = max(1, n // len(categorized))

            for category_queries in categorized.values():
                samples.extend(
                    random.sample(
                        category_queries, min(per_category, len(category_queries))
                    )
                )

            return samples[:n]

        return queries[:n]


def example_usage():
    """Example of how to use the converter."""
    converter = LogToDatasetConverter()

    # Example 1: Extract from JSON logs
    print("=" * 60)
    print("Example 1: Extract from JSON logs")
    print("=" * 60)

    # This would be your actual log file
    example_logs = [
        {
            "timestamp": "2026-01-22T10:30:00",
            "message": "Find jazz concerts in Berlin this weekend",
            "action": "QUERY_DB",
            "cypher": "MATCH (e:Event)...",
            "result_count": 5,
        },
        {
            "timestamp": "2026-01-22T10:31:00",
            "message": "What about tomorrow?",
            "action": "QUERY_DB",
            "result_count": 3,
        },
        {
            "timestamp": "2026-01-22T10:32:00",
            "message": "Show me concerts",
            "action": "NEEDS_INFO",
        },
    ]

    # Save example logs to file
    example_log_file = "/tmp/example_logs.jsonl"
    with open(example_log_file, "w") as f:
        for log in example_logs:
            f.write(json.dumps(log) + "\n")

    # Extract queries
    queries = converter.extract_from_api_logs(example_log_file, log_format="jsonl")

    # Create datasets
    converter.create_query_generation_dataset(queries)
    converter.create_intent_classification_dataset(queries)

    print("\n✓ Datasets created successfully!")


if __name__ == "__main__":
    example_usage()
