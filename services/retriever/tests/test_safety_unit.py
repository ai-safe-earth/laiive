"""
Unit test for SafetyGuardTool - without requiring settings/config.
Tests the validation logic directly.
"""

import re


# Copy the validation methods for testing without full import
def remove_comments_and_strings(cypher: str) -> str:
    """Remove comments and string literals to avoid false positives."""
    # Remove single-line comments
    cypher = re.sub(r"//.*?$", "", cypher, flags=re.MULTILINE)

    # Remove multi-line comments
    cypher = re.sub(r"/\*.*?\*/", "", cypher, flags=re.DOTALL)

    # Remove string literals (both single and double quotes)
    cypher = re.sub(r"'[^']*'", "''", cypher)
    cypher = re.sub(r'"[^"]*"', '""', cypher)

    return cypher


def validate_read_only(cypher: str) -> tuple[bool, list[str]]:
    """
    Enhanced validation for read-only Cypher queries.
    Returns (is_safe, list_of_violations).
    """
    violations = []

    # Remove comments and strings to avoid false positives
    cleaned_query = remove_comments_and_strings(cypher)
    upper_query = cleaned_query.upper()

    # Check for forbidden write operations with word boundaries
    forbidden_patterns = [
        (r"\bCREATE\b", "CREATE"),
        (r"\bDELETE\b", "DELETE"),
        (r"\bMERGE\b", "MERGE"),
        (r"\bSET\b", "SET"),
        (r"\bREMOVE\b", "REMOVE"),
        (r"\bDROP\b", "DROP"),
        (r"\bDETACH\s+DELETE\b", "DETACH DELETE"),
    ]

    for pattern, keyword in forbidden_patterns:
        if re.search(pattern, upper_query):
            violations.append(keyword)

    # Check for dangerous APOC procedures
    dangerous_apoc = [
        r"apoc\.export",
        r"apoc\.import",
        r"apoc\.trigger",
        r"apoc\.periodic\.commit",
        r"apoc\.cypher\.runFile",
        r"apoc\.load\.driver",
    ]

    for pattern in dangerous_apoc:
        if re.search(pattern, cypher, re.IGNORECASE):
            violations.append(f"Dangerous APOC procedure: {pattern}")

    is_safe = len(violations) == 0
    return is_safe, violations


def test_cypher_validation():
    """Test Cypher query validation."""
    print("\n=== Testing Cypher Query Validation ===\n")

    # Test cases: (query, expected_safe, description)
    test_cases = [
        ("MATCH (n:Event) RETURN n LIMIT 10", True, "Safe read query"),
        (
            "MATCH (e:Event)-[:AT_VENUE]->(v:Venue) WHERE v.city = 'Berlin' RETURN e, v",
            True,
            "Safe query with relationships",
        ),
        ("CREATE (n:Event {name: 'Test'}) RETURN n", False, "CREATE operation"),
        ("MATCH (n) DELETE n", False, "DELETE operation"),
        ("MATCH (n) SET n.name = 'Test' RETURN n", False, "SET operation"),
        ("MERGE (n:Event {id: 1}) RETURN n", False, "MERGE operation"),
        ("MATCH (n) REMOVE n.property RETURN n", False, "REMOVE operation"),
        ("DROP INDEX event_index", False, "DROP operation"),
        ("MATCH (n) DETACH DELETE n", False, "DETACH DELETE"),
        ("// CREATE comment\nMATCH (n) RETURN n", True, "Keyword in comment"),
        ("MATCH (n) WHERE n.name = 'CREATE EVENT' RETURN n", True, "Keyword in string"),
        (
            "MATCH (n:Event) WHERE n.created_at > datetime() RETURN n",
            True,
            "Partial keyword match (created_at)",
        ),
        ("CALL apoc.export.csv.all('file.csv', {})", False, "Dangerous APOC export"),
        ("CALL apoc.import.json('data.json')", False, "Dangerous APOC import"),
        ("RETURN apoc.text.join(['a', 'b'], ',')", True, "Safe APOC procedure"),
        ("CREATE (n) SET n.name = 'Test' DELETE n", False, "Multiple violations"),
        ("", True, "Empty query"),
        ("   \n\t   ", True, "Whitespace only"),
        ("create (n:Event) return n", False, "Lowercase CREATE"),
        ("CrEaTe (n:Event) ReTuRn n", False, "Mixed case CREATE"),
    ]

    passed = 0
    failed = 0

    for query, expected_safe, description in test_cases:
        is_safe, violations = validate_read_only(query)

        status = "[PASS]" if is_safe == expected_safe else "[FAIL]"
        if is_safe == expected_safe:
            passed += 1
        else:
            failed += 1

        print(f"{status}: {description}")
        if len(query) > 60:
            print(f"  Query: {query[:60]}...")
        else:
            print(f"  Query: {query}")
        print(
            f"  Expected: {'safe' if expected_safe else 'unsafe'}, Got: {'safe' if is_safe else 'unsafe'}"
        )
        if not is_safe:
            print(f"  Violations: {violations}")
        print()

    print(f"\n{'='*60}")
    print(f"Cypher Validation Tests: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return failed == 0


def test_comment_string_removal():
    """Test comment and string removal."""
    print("\n=== Testing Comment/String Removal ===\n")

    test_cases = [
        ("// CREATE\nMATCH (n) RETURN n", "MATCH (n) RETURN n", "Single-line comment"),
        (
            "/* CREATE */ MATCH (n) RETURN n",
            " MATCH (n) RETURN n",
            "Multi-line comment",
        ),
        (
            "MATCH (n) WHERE n.name = 'CREATE' RETURN n",
            "MATCH (n) WHERE n.name = '' RETURN n",
            "String literal",
        ),
    ]

    passed = 0
    failed = 0

    for input_query, expected_pattern, description in test_cases:
        cleaned = remove_comments_and_strings(input_query)
        cleaned = " ".join(cleaned.split())  # Normalize whitespace
        expected = " ".join(expected_pattern.split())

        status = "[PASS]" if expected in cleaned or cleaned == expected else "[FAIL]"
        if expected in cleaned or cleaned == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status}: {description}")
        print(f"  Input: {input_query}")
        print(f"  Cleaned: {cleaned}")
        print()

    print(f"{'='*60}")
    print(f"Comment/String Removal: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return failed == 0


def test_multiple_violations():
    """Test queries with multiple violations."""
    print("\n=== Testing Multiple Violations ===\n")

    query = "CREATE (n:Event) SET n.name = 'Test' DELETE n"
    is_safe, violations = validate_read_only(query)

    expected_violations = ["CREATE", "SET", "DELETE"]
    has_all = all(v in violations for v in expected_violations)

    print("Multiple Violations Test:")
    print(f"  Query: {query}")
    print(f"  Violations Found: {violations}")
    print(f"  Expected: {expected_violations}")
    print(f"  {'[PASS]' if has_all else '[FAIL]'}: All violations detected")
    print()

    return has_all


def main():
    """Run all unit tests."""
    print("\n" + "=" * 60)
    print("SafetyGuardTool - Unit Test Suite")
    print("=" * 60)

    try:
        results = []
        results.append(test_cypher_validation())
        results.append(test_comment_string_removal())
        results.append(test_multiple_violations())

        print("\n" + "=" * 60)
        if all(results):
            print("[SUCCESS] ALL TESTS PASSED")
        else:
            print("[FAILURE] SOME TESTS FAILED")
        print("=" * 60 + "\n")

        return 0 if all(results) else 1

    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
