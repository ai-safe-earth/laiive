"""
Manual test script for SafetyGuardTool improvements.
Run with: python test_safety_manual.py
"""

import json
import sys
from agent.tools.safety_guard import SafetyGuardTool


def test_cypher_validation():
    """Test Cypher query validation."""
    print("\n=== Testing Cypher Query Validation ===\n")

    tool = SafetyGuardTool()

    # Test cases
    test_cases = [
        ("MATCH (n:Event) RETURN n LIMIT 10", True, "Safe read query"),
        ("CREATE (n:Event {name: 'Test'}) RETURN n", False, "CREATE operation"),
        ("MATCH (n) DELETE n", False, "DELETE operation"),
        ("MATCH (n) SET n.name = 'Test' RETURN n", False, "SET operation"),
        ("MERGE (n:Event {id: 1}) RETURN n", False, "MERGE operation"),
        ("MATCH (n) REMOVE n.property RETURN n", False, "REMOVE operation"),
        ("DROP INDEX event_index", False, "DROP operation"),
        ("MATCH (n) DETACH DELETE n", False, "DETACH DELETE"),
        ("// CREATE comment\nMATCH (n) RETURN n", True, "Keyword in comment"),
        ("MATCH (n) WHERE n.name = 'CREATE' RETURN n", True, "Keyword in string"),
        ("CALL apoc.export.csv.all('file.csv', {})", False, "Dangerous APOC"),
    ]

    passed = 0
    failed = 0

    for query, expected_safe, description in test_cases:
        result_json = tool.run(query)
        result = json.loads(result_json)
        is_safe = result["is_safe"]

        status = "✓ PASS" if is_safe == expected_safe else "✗ FAIL"
        if is_safe == expected_safe:
            passed += 1
        else:
            failed += 1

        print(f"{status}: {description}")
        print(f"  Query: {query[:60]}...")
        print(
            f"  Expected: {'safe' if expected_safe else 'unsafe'}, Got: {'safe' if is_safe else 'unsafe'}"
        )
        if not is_safe:
            print(f"  Violations: {result['violations']}")
        print()

    print(f"\n{'='*60}")
    print(f"Cypher Validation Tests: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return failed == 0


def test_enhanced_features():
    """Test enhanced features like comment/string removal."""
    print("\n=== Testing Enhanced Features ===\n")

    tool = SafetyGuardTool()

    # Test comment removal
    query_with_comment = """
    // This comment has CREATE and DELETE
    /* Another comment with MERGE */
    MATCH (n:Event)
    WHERE n.name = 'Test'
    RETURN n
    """

    result_json = tool.run(query_with_comment)
    result = json.loads(result_json)

    print(f"Comment/String Filtering Test:")
    print(f"  Query has keywords in comments")
    print(f"  Is Safe: {result['is_safe']} (expected: True)")
    print(f"  Violations: {result['violations']}")

    # Test regex word boundary
    query_with_partial = "MATCH (n:Event) WHERE n.created_at > datetime() RETURN n"
    result_json = tool.run(query_with_partial)
    result = json.loads(result_json)

    print(f"\nWord Boundary Test:")
    print(f"  Query: 'created_at' contains 'CREATE'")
    print(f"  Is Safe: {result['is_safe']} (expected: True)")
    print(f"  Violations: {result['violations']}")

    print()
    return True


def test_error_messages():
    """Test that error messages are descriptive."""
    print("\n=== Testing Error Messages ===\n")

    tool = SafetyGuardTool()

    unsafe_query = "CREATE (n:Event) SET n.name = 'Test' DELETE n"
    result_json = tool.run(unsafe_query)
    result = json.loads(result_json)

    print(f"Multiple Violations Test:")
    print(f"  Message: {result['message']}")
    print(f"  Violations: {result['violations']}")
    print(f"  Should list all violations: CREATE, SET, DELETE")

    has_all = all(v in result["violations"] for v in ["CREATE", "SET", "DELETE"])
    print(f"  ✓ PASS" if has_all else "  ✗ FAIL")

    print()
    return has_all


def main():
    """Run all manual tests."""
    print("\n" + "=" * 60)
    print("SafetyGuardTool - Manual Test Suite")
    print("=" * 60)

    try:
        results = []
        results.append(test_cypher_validation())
        results.append(test_enhanced_features())
        results.append(test_error_messages())

        print("\n" + "=" * 60)
        if all(results):
            print("✓ ALL TESTS PASSED")
        else:
            print("✗ SOME TESTS FAILED")
        print("=" * 60 + "\n")

        return 0 if all(results) else 1

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
