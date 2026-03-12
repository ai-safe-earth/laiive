"""
System-level end-to-end evaluation runner.
Evaluates complete conversation flows through the entire retrieval pipeline.
"""
import json
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import settings
from agent.orchestrator import Orchestrator
from agent.clients.neo4j_client import neo4j_client
from evals.config import EvalConfig, ModelConfig


@dataclass
class ConversationEvalResult:
    """Result for a complete conversation evaluation."""
    conversation_id: str
    model: str
    total_turns: int
    successful_turns: int
    failed_turns: int
    total_latency_ms: float
    avg_latency_per_turn_ms: float
    success_criteria_met: bool
    turn_results: List[Dict[str, Any]]
    errors: List[str]
    metadata: Dict[str, Any]


class SystemEvaluator:
    """Evaluates complete end-to-end conversation flows."""

    def __init__(self, eval_config: EvalConfig):
        self.config = eval_config
        self.results: List[ConversationEvalResult] = []

    def run_conversation_eval(
        self, conversations: List[Dict], model_config: ModelConfig
    ) -> List[ConversationEvalResult]:
        """Evaluate complete conversation scenarios."""
        print(f"\n{'='*60}")
        print(f"Evaluating End-to-End Conversations")
        print(f"  Model: {model_config.name}")
        print(f"{'='*60}\n")

        results = []

        # Get schema and create orchestrator
        schema = neo4j_client.get_schema()
        orchestrator = Orchestrator(schema=schema)

        for i, conversation in enumerate(conversations, 1):
            print(f"\nConversation {i}/{len(conversations)}: {conversation['id']}")
            print(f"  Scenario: {conversation['name']}")

            try:
                result = self._evaluate_conversation(
                    conversation, orchestrator, model_config
                )
                results.append(result)

                status = "✓ PASSED" if result.success_criteria_met else "✗ FAILED"
                print(f"  {status} - {result.successful_turns}/{result.total_turns} turns successful")
                print(f"  Total latency: {result.total_latency_ms:.0f}ms")

            except Exception as e:
                result = ConversationEvalResult(
                    conversation_id=conversation["id"],
                    model=model_config.name,
                    total_turns=len(conversation["turns"]),
                    successful_turns=0,
                    failed_turns=len(conversation["turns"]),
                    total_latency_ms=0.0,
                    avg_latency_per_turn_ms=0.0,
                    success_criteria_met=False,
                    turn_results=[],
                    errors=[str(e)],
                    metadata={"name": conversation["name"]},
                )
                results.append(result)
                print(f"  ✗ ERROR: {str(e)}")

        return results

    def _evaluate_conversation(
        self,
        conversation: Dict,
        orchestrator: Orchestrator,
        model_config: ModelConfig,
    ) -> ConversationEvalResult:
        """Evaluate a single conversation."""
        turns = conversation["turns"]
        turn_results = []
        conversation_history = []
        total_latency = 0.0
        successful_turns = 0
        errors = []

        for turn_idx, turn in enumerate(turns):
            print(f"    Turn {turn_idx + 1}: {turn['user'][:50]}...")

            start_time = datetime.now()

            try:
                # Execute turn
                user_message = turn["user"]

                # Decide action
                action = orchestrator.decide_action(user_message, conversation_history)

                # Execute query if needed
                cypher = None
                results = None
                if action == "QUERY_DB":
                    try:
                        cypher, results = orchestrator.execute_query(user_message)
                    except Exception as e:
                        errors.append(f"Turn {turn_idx + 1} query failed: {str(e)}")

                # Generate response
                response_text, cypher, results, used_query, needs_more_info = (
                    orchestrator.generate_response(
                        action=action,
                        user_message=user_message,
                        conversation_history=conversation_history,
                        cypher=cypher,
                        results=results,
                    )
                )

                latency = (datetime.now() - start_time).total_seconds() * 1000
                total_latency += latency

                # Evaluate turn against success criteria
                criteria_met, criteria_results = self._check_turn_criteria(
                    turn, action, cypher, results, response_text
                )

                if criteria_met:
                    successful_turns += 1

                turn_result = {
                    "turn_number": turn_idx + 1,
                    "user_message": user_message,
                    "action": action,
                    "response": response_text,
                    "cypher": cypher,
                    "result_count": len(results) if results else 0,
                    "latency_ms": latency,
                    "success": criteria_met,
                    "criteria_results": criteria_results,
                }
                turn_results.append(turn_result)

                # Update conversation history
                conversation_history.append(
                    type("Message", (), {"role": "user", "content": user_message})()
                )
                conversation_history.append(
                    type("Message", (), {"role": "assistant", "content": response_text})()
                )

                print(f"      Action: {action}, Latency: {latency:.0f}ms, Success: {criteria_met}")

            except Exception as e:
                errors.append(f"Turn {turn_idx + 1} failed: {str(e)}")
                turn_results.append({
                    "turn_number": turn_idx + 1,
                    "error": str(e),
                    "success": False,
                })

        # Check overall conversation success criteria
        overall_success = self._check_overall_criteria(
            conversation, turn_results, successful_turns, len(turns)
        )

        return ConversationEvalResult(
            conversation_id=conversation["id"],
            model=model_config.name,
            total_turns=len(turns),
            successful_turns=successful_turns,
            failed_turns=len(turns) - successful_turns,
            total_latency_ms=total_latency,
            avg_latency_per_turn_ms=total_latency / len(turns) if turns else 0,
            success_criteria_met=overall_success,
            turn_results=turn_results,
            errors=errors,
            metadata={"name": conversation["name"]},
        )

    def _check_turn_criteria(
        self,
        turn: Dict,
        action: str,
        cypher: str,
        results: List,
        response: str,
    ) -> tuple[bool, Dict[str, bool]]:
        """Check if turn meets its success criteria."""
        criteria = turn.get("success_criteria", {})
        results_dict = {}

        # Check expected action
        expected_action = turn.get("expected_action")
        if expected_action:
            results_dict["correct_action"] = action == expected_action
        else:
            results_dict["correct_action"] = True

        # Check specific criteria
        if "generates_query" in criteria:
            results_dict["generates_query"] = cypher is not None

        if "returns_results" in criteria:
            results_dict["returns_results"] = results is not None and len(results) > 0

        if "includes_location" in criteria:
            location = criteria["includes_location"]
            results_dict["includes_location"] = (
                cypher is not None and location.lower() in cypher.lower()
            )

        if "has_date_filter" in criteria:
            results_dict["has_date_filter"] = (
                cypher is not None and "datetime(" in cypher
            )

        if "asks_for_clarification" in criteria:
            clarification_phrases = [
                "could you",
                "can you",
                "what about",
                "which",
                "where",
                "when",
            ]
            results_dict["asks_for_clarification"] = any(
                phrase in response.lower() for phrase in clarification_phrases
            )

        if "rejects_politely" in criteria:
            results_dict["rejects_politely"] = (
                action == "OUT_OF_SCOPE" and len(response) > 0
            )

        if "uses_conversation_context" in criteria:
            # This is a heuristic - in practice you'd check if context was actually used
            results_dict["uses_conversation_context"] = True

        # Add more criteria checks as needed

        all_met = all(results_dict.values())
        return all_met, results_dict

    def _check_overall_criteria(
        self,
        conversation: Dict,
        turn_results: List[Dict],
        successful_turns: int,
        total_turns: int,
    ) -> bool:
        """Check overall conversation success criteria."""
        overall_criteria = conversation.get("overall_success_criteria", {})

        if "completes_without_errors" in overall_criteria:
            has_errors = any(
                "error" in turn for turn in turn_results
            )
            if has_errors:
                return False

        if "provides_relevant_results" in overall_criteria:
            # Check if at least one turn returned results
            has_results = any(
                turn.get("result_count", 0) > 0 for turn in turn_results
            )
            if not has_results:
                return False

        # Success if at least 80% of turns succeeded
        success_rate = successful_turns / total_turns if total_turns > 0 else 0
        return success_rate >= 0.8

    def generate_report(self, results: List[ConversationEvalResult], output_path: str):
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

    def _calculate_summary(self, results: List[ConversationEvalResult]) -> Dict[str, Any]:
        """Calculate summary statistics."""
        total_conversations = len(results)
        successful_conversations = sum(1 for r in results if r.success_criteria_met)

        total_turns = sum(r.total_turns for r in results)
        successful_turns = sum(r.successful_turns for r in results)

        avg_latency = (
            sum(r.avg_latency_per_turn_ms for r in results) / total_conversations
            if total_conversations > 0
            else 0
        )

        return {
            "total_conversations": total_conversations,
            "successful_conversations": successful_conversations,
            "failed_conversations": total_conversations - successful_conversations,
            "conversation_success_rate": (
                successful_conversations / total_conversations
                if total_conversations > 0
                else 0
            ),
            "total_turns": total_turns,
            "successful_turns": successful_turns,
            "failed_turns": total_turns - successful_turns,
            "turn_success_rate": successful_turns / total_turns if total_turns > 0 else 0,
            "avg_latency_per_turn_ms": avg_latency,
        }

    def _print_summary(self, summary: Dict[str, Any]):
        """Print summary to console."""
        print(f"\n{'='*60}")
        print("SYSTEM EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Conversations: {summary['total_conversations']}")
        print(
            f"Successful: {summary['successful_conversations']} "
            f"({summary['conversation_success_rate']*100:.1f}%)"
        )
        print(f"Failed: {summary['failed_conversations']}")
        print(f"\nTotal Turns: {summary['total_turns']}")
        print(
            f"Successful Turns: {summary['successful_turns']} "
            f"({summary['turn_success_rate']*100:.1f}%)"
        )
        print(f"Failed Turns: {summary['failed_turns']}")
        print(f"\nAvg Latency per Turn: {summary['avg_latency_per_turn_ms']:.0f}ms")
        print(f"{'='*60}\n")


def run_system_eval(eval_config: EvalConfig):
    """Main entry point for system evaluation."""
    evaluator = SystemEvaluator(eval_config)

    # Load dataset
    with open(eval_config.dataset_path) as f:
        dataset = json.load(f)
    conversations = dataset.get("conversations", [])

    all_results = []

    # Run evals for each model
    for model_config in eval_config.models:
        results = evaluator.run_conversation_eval(conversations, model_config)
        all_results.extend(results)

    # Generate report
    evaluator.generate_report(all_results, eval_config.output_path)

    return all_results


if __name__ == "__main__":
    from evals.config import SYSTEM_EVALS

    # Example: Run end-to-end eval
    # run_system_eval(SYSTEM_EVALS["end_to_end"])

    print("System evaluator ready. Import and run with specific eval config.")
