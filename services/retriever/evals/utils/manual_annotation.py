"""
Interactive tool for manually annotating test cases.

Use this to review and correct auto-generated test cases or annotate new ones.
"""

import json
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class ManualAnnotator:
    """Interactive CLI tool for annotating test cases."""

    def __init__(self, dataset_file: str):
        self.dataset_file = Path(dataset_file)
        self.dataset = self._load_dataset()
        self.changes_made = 0

    def _load_dataset(self) -> Dict:
        """Load dataset from file."""
        with open(self.dataset_file, "r") as f:
            return json.load(f)

    def _save_dataset(self):
        """Save dataset back to file."""
        backup_path = self.dataset_file.with_suffix(".backup.json")

        # Create backup
        with open(backup_path, "w") as f:
            json.dump(self.dataset, f, indent=2)

        # Save updated dataset
        with open(self.dataset_file, "w") as f:
            json.dump(self.dataset, f, indent=2)

        print(f"\n✓ Dataset saved (backup: {backup_path})")

    def annotate_query_generation(self):
        """Annotate query generation test cases."""
        test_cases = self.dataset.get("test_cases", [])

        print(f"\n{'='*60}")
        print("Annotating Query Generation Dataset")
        print(f"File: {self.dataset_file}")
        print(f"Total cases: {len(test_cases)}")
        print(f"{'='*60}\n")

        # Focus on cases needing review
        needs_review = [
            tc
            for tc in test_cases
            if tc.get("metadata", {}).get("needs_manual_review")
            or not tc.get("expected_patterns")
        ]

        if needs_review:
            print(f"Found {len(needs_review)} cases that need review\n")
        else:
            print("All cases have been reviewed. Showing all cases.\n")
            needs_review = test_cases

        for i, test_case in enumerate(needs_review):
            print(f"\n--- Case {i+1}/{len(needs_review)}: {test_case['id']} ---")
            print(f"Query: {test_case['user_query']}")
            print(f"Category: {test_case.get('category', 'unknown')}")

            if test_case.get("actual_cypher_generated"):
                print(
                    f"\nActual Cypher generated:\n{test_case['actual_cypher_generated']}"
                )

            print(
                f"\nCurrent expected patterns: {test_case.get('expected_patterns', [])}"
            )

            # Prompt for updates
            print("\nOptions:")
            print("  1. Keep as is (press Enter)")
            print("  2. Update expected patterns")
            print("  3. Update category")
            print("  4. Add difficulty level")
            print("  5. Skip this case")
            print("  6. Delete this case")
            print("  s. Save and exit")
            print("  q. Quit without saving")

            choice = input("\nChoice: ").strip()

            if choice == "s":
                self._save_dataset()
                print(f"\nAnnotated {self.changes_made} cases")
                break

            elif choice == "q":
                print("\nExiting without saving")
                break

            elif choice == "1" or choice == "":
                # Mark as reviewed
                if "metadata" not in test_case:
                    test_case["metadata"] = {}
                test_case["metadata"]["needs_manual_review"] = False
                test_case["metadata"]["manually_reviewed"] = True
                self.changes_made += 1
                continue

            elif choice == "2":
                patterns = []
                print("\nEnter expected patterns (one per line, empty line to finish):")
                while True:
                    pattern = input("  Pattern: ").strip()
                    if not pattern:
                        break
                    patterns.append(pattern)

                if patterns:
                    test_case["expected_patterns"] = patterns
                    test_case["metadata"]["needs_manual_review"] = False
                    test_case["metadata"]["manually_reviewed"] = True
                    self.changes_made += 1

            elif choice == "3":
                categories = [
                    "artist_query",
                    "venue_query",
                    "date_query",
                    "location_query",
                    "genre_query",
                    "price_query",
                    "complex_multi_constraint",
                    "general",
                ]
                print("\nAvailable categories:")
                for idx, cat in enumerate(categories, 1):
                    print(f"  {idx}. {cat}")

                cat_choice = input("Choose category (number): ").strip()
                try:
                    cat_idx = int(cat_choice) - 1
                    if 0 <= cat_idx < len(categories):
                        test_case["category"] = categories[cat_idx]
                        self.changes_made += 1
                except ValueError:
                    print("Invalid choice")

            elif choice == "4":
                difficulty = input("Difficulty (easy/medium/hard): ").strip().lower()
                if difficulty in ["easy", "medium", "hard"]:
                    test_case["metadata"]["difficulty"] = difficulty
                    self.changes_made += 1

            elif choice == "5":
                continue

            elif choice == "6":
                confirm = input("Delete this case? (yes/no): ").strip().lower()
                if confirm == "yes":
                    test_cases.remove(test_case)
                    self.changes_made += 1
                    print("Case deleted")

        # Final save
        if self.changes_made > 0:
            save_choice = (
                input(f"\nSave {self.changes_made} changes? (yes/no): ").strip().lower()
            )
            if save_choice == "yes":
                self._save_dataset()
                print(f"✓ Saved {self.changes_made} changes")
            else:
                print("Changes discarded")

    def annotate_intent_classification(self):
        """Annotate intent classification test cases."""
        test_cases = self.dataset.get("test_cases", [])

        print(f"\n{'='*60}")
        print("Annotating Intent Classification Dataset")
        print(f"File: {self.dataset_file}")
        print(f"Total cases: {len(test_cases)}")
        print(f"{'='*60}\n")

        actions = ["QUERY_DB", "NEEDS_INFO", "OUT_OF_SCOPE", "BYE_MESSAGE"]

        # Focus on cases needing review
        needs_review = [
            tc
            for tc in test_cases
            if tc.get("metadata", {}).get("needs_manual_review")
            or tc.get("expected_action") == "UNKNOWN"
        ]

        if not needs_review:
            needs_review = test_cases

        for i, test_case in enumerate(needs_review):
            print(f"\n--- Case {i+1}/{len(needs_review)}: {test_case['id']} ---")
            print(f"Message: {test_case['user_message']}")
            print(f"Current action: {test_case.get('expected_action', 'UNKNOWN')}")

            print("\nActions:")
            for idx, action in enumerate(actions, 1):
                print(f"  {idx}. {action}")
            print("  5. Keep current")
            print("  6. Skip")
            print("  s. Save and exit")

            choice = input("\nChoice: ").strip()

            if choice == "s":
                self._save_dataset()
                break

            elif choice == "5" or choice == "":
                if "metadata" not in test_case:
                    test_case["metadata"] = {}
                test_case["metadata"]["needs_manual_review"] = False
                test_case["metadata"]["manually_reviewed"] = True
                self.changes_made += 1

            elif choice == "6":
                continue

            else:
                try:
                    action_idx = int(choice) - 1
                    if 0 <= action_idx < len(actions):
                        test_case["expected_action"] = actions[action_idx]
                        test_case["metadata"]["needs_manual_review"] = False
                        test_case["metadata"]["manually_reviewed"] = True
                        self.changes_made += 1
                except ValueError:
                    print("Invalid choice")

        # Final save
        if self.changes_made > 0:
            save_choice = (
                input(f"\nSave {self.changes_made} changes? (yes/no): ").strip().lower()
            )
            if save_choice == "yes":
                self._save_dataset()

    def add_new_case(self, case_type: str = "query_generation"):
        """Add a new test case interactively."""
        print(f"\n{'='*60}")
        print(f"Adding New {case_type.replace('_', ' ').title()} Case")
        print(f"{'='*60}\n")

        if case_type == "query_generation":
            user_query = input("User query: ").strip()
            category = input("Category: ").strip() or "general"

            patterns = []
            print("\nExpected patterns (one per line, empty to finish):")
            while True:
                pattern = input("  Pattern: ").strip()
                if not pattern:
                    break
                patterns.append(pattern)

            difficulty = input("Difficulty (easy/medium/hard): ").strip() or "medium"

            # Generate ID
            existing_ids = [tc["id"] for tc in self.dataset.get("test_cases", [])]
            new_id = f"qg_manual_{len(existing_ids) + 1:03d}"

            new_case = {
                "id": new_id,
                "category": category,
                "user_query": user_query,
                "expected_patterns": patterns,
                "should_not_contain": ["DELETE", "CREATE", "MERGE", "SET"],
                "metadata": {
                    "difficulty": difficulty,
                    "manually_created": True,
                },
            }

            self.dataset.setdefault("test_cases", []).append(new_case)
            self.changes_made += 1
            print(f"\n✓ Added case {new_id}")

        elif case_type == "intent_classification":
            user_message = input("User message: ").strip()

            actions = ["QUERY_DB", "NEEDS_INFO", "OUT_OF_SCOPE", "BYE_MESSAGE"]
            print("\nExpected action:")
            for idx, action in enumerate(actions, 1):
                print(f"  {idx}. {action}")

            action_choice = int(input("Choice: ").strip()) - 1
            expected_action = actions[action_choice]

            reasoning = input("Reasoning: ").strip()

            # Generate ID
            existing_ids = [tc["id"] for tc in self.dataset.get("test_cases", [])]
            new_id = f"ic_manual_{len(existing_ids) + 1:03d}"

            new_case = {
                "id": new_id,
                "user_message": user_message,
                "expected_action": expected_action,
                "conversation_history": [],
                "reasoning": reasoning,
                "metadata": {
                    "manually_created": True,
                },
            }

            self.dataset.setdefault("test_cases", []).append(new_case)
            self.changes_made += 1
            print(f"\n✓ Added case {new_id}")


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Manually annotate test cases")
    parser.add_argument("dataset_file", help="Path to dataset JSON file")
    parser.add_argument(
        "--type",
        choices=["query_generation", "intent_classification"],
        default="query_generation",
        help="Type of dataset to annotate",
    )
    parser.add_argument(
        "--add",
        action="store_true",
        help="Add new test case instead of annotating existing",
    )

    args = parser.parse_args()

    if not Path(args.dataset_file).exists():
        print(f"Error: Dataset file not found: {args.dataset_file}")
        sys.exit(1)

    annotator = ManualAnnotator(args.dataset_file)

    if args.add:
        annotator.add_new_case(args.type)
    elif args.type == "query_generation":
        annotator.annotate_query_generation()
    elif args.type == "intent_classification":
        annotator.annotate_intent_classification()


if __name__ == "__main__":
    main()
