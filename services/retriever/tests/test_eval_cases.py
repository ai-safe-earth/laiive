"""The quarantined eval cases, wired to the code they were written for.

Twelve hand-labelled cases sat in ``evals/datasets/`` with nothing to run them:
seven safety cases for ``agent/tools/safety_guard.py`` and five Cypher-generation
cases for ``agent/tools/query_builder.py``. This is the loader (eval phase 2).

Two tiers, because the cases are not equally cheap:

* **Deterministic** (default run) - the six safety cases that are pure regex,
  plus the mutation gate below. No network, so CI can hold them.
* **Integration** (``-m integration``) - the one safety case that needs OpenAI's
  moderation verdict, and the five Cypher cases, which need a real generation.

``should_not_contain`` is the corpus's real gate, so it is asserted in *both*
tiers rather than only where a live model is available: offline as "a generated
mutation never reaches the driver", online as "the generator did not emit one".
``expected_patterns`` is xfailed - regex over generated Cypher asserts shape,
not whether the query answers the question, and execute-and-compare replaces it
in phase 4. The patterns are still kept current so the xfail means "wrong
instrument", not "stale data".
"""

import json
import re
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from agent.tools.query_builder import QUERY_BUILDER_PROMPT_VERSION, QueryBuilderTool
from agent.tools.safety_guard import SafetyGuardTool

DATASETS = Path(__file__).resolve().parents[1] / "evals" / "datasets"


def _dataset(dataset: str) -> dict:
    path = DATASETS / dataset / "test_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


SAFETY = _dataset("safety")["test_cases"]
QUERY_GEN_FILE = _dataset("query_generation")
QUERY_GEN = QUERY_GEN_FILE["test_cases"]


def _checked(check: str) -> list[dict]:
    return [case for case in SAFETY if case["check"] == check]


def _ids(cases: list[dict]) -> list[str]:
    return [case["id"] for case in cases]


CYPHER_GUARD = _checked("cypher_guard")
INJECTION = _checked("injection")
MODERATION = _checked("moderation")


def _is_unsafe(case: dict) -> bool:
    return case["expected_verdict"] == "unsafe"


# ── the corpus itself ───────────────────────────────────────────────────────


def test_every_safety_case_is_claimed_by_a_check():
    """A case whose `check` nobody parametrizes over is a silent skip.

    That is how the set went quarantined in the first place: the labels named a
    taxonomy (mutation_detected, injection_pattern) that no function produced,
    so there was nothing to call. A typo here would recreate that quietly.
    """
    claimed = len(CYPHER_GUARD) + len(INJECTION) + len(MODERATION)
    assert claimed == len(SAFETY) == 7, [c["id"] for c in SAFETY]


def test_every_query_gen_case_carries_a_gate():
    """expected_patterns may be xfailed; should_not_contain may not be empty."""
    assert len(QUERY_GEN) == 5
    for case in QUERY_GEN:
        assert case["should_not_contain"], case["id"]
        assert case["expected_patterns"], case["id"]


def test_query_gen_corpus_matches_the_live_prompt_version():
    """A prompt bump must not be able to invalidate these cases quietly.

    Every expected_patterns list in v1 was stale against v2 and nobody found
    out for five months, because the corpus described the prompt only in prose.
    This is the machine link: bump QUERY_BUILDER_PROMPT_VERSION and this fails
    until someone re-reads the five cases and restamps the dataset.
    """
    assert QUERY_GEN_FILE["prompt_version"] == QUERY_BUILDER_PROMPT_VERSION, (
        f"corpus describes prompt {QUERY_GEN_FILE['prompt_version']}, "
        f"query_builder.py is on {QUERY_BUILDER_PROMPT_VERSION} - re-check the "
        f"5 cases against the new prompt, then restamp prompt_version"
    )


# ── safety: deterministic ───────────────────────────────────────────────────


@pytest.mark.parametrize("case", CYPHER_GUARD, ids=_ids(CYPHER_GUARD))
def test_cypher_guard_case(case):
    is_safe, violations = SafetyGuardTool().validate_read_only(case["input_text"])

    assert is_safe is not _is_unsafe(case), f"{case['id']}: {case['reasoning']}"
    # A superset, not an equality: the case says "at least these keywords", so
    # the guard is free to grow stricter without invalidating the label.
    assert set(case["expected_violations"]) <= set(violations), violations
    if not _is_unsafe(case):
        assert violations == []


@pytest.mark.parametrize("case", INJECTION, ids=_ids(INJECTION))
def test_injection_case(case):
    flagged = SafetyGuardTool().detect_injection(case["input_text"])
    assert flagged is _is_unsafe(case), f"{case['id']}: {case['reasoning']}"


# ── safety: integration ─────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.parametrize("case", MODERATION, ids=_ids(MODERATION))
def test_moderation_case(case):
    """Live OpenAI moderation - the one case of the seven that is not offline.

    Mocking it would assert the mock: moderate() fails open on any exception, so
    a stubbed client proves nothing about whether the endpoint flags the text.
    TestModerationAndInjection in test_safety_guard.py already pins the wiring
    (flagged / not flagged / fails open) with a mock; this pins the verdict.
    """
    flagged = SafetyGuardTool().moderate(case["input_text"])
    assert flagged is _is_unsafe(case), f"{case['id']}: {case['reasoning']}"


# ── query generation: the deterministic half of should_not_contain ──────────

# The alphabetic entries are Cypher write keywords, so the safety guard knows
# them and the gate can run offline. The rest of should_not_contain
# (`date(e.start_at)`, `price_amount`, `datetime(e.start_at)`) are shape
# anti-patterns the guard has no opinion about - only the integration tier sees
# those.
MUTATION_KEYWORDS = sorted(
    {
        token.upper()
        for case in QUERY_GEN
        for token in case["should_not_contain"]
        if token.isalpha()
    }
)


@pytest.mark.parametrize("keyword", MUTATION_KEYWORDS)
def test_generated_mutation_never_reaches_the_driver(keyword):
    """should_not_contain as a gate CI can hold.

    The corpus's forbidden keywords are exactly the guard's write list, and
    QueryBuilderTool.run validates before executing - so the property worth
    pinning is not "this prompt happened not to emit DELETE today" but "a
    generated mutation is refused and never reaches Neo4j", which is true of
    every prompt revision and costs no tokens.
    """
    tool = QueryBuilderTool(neo4j_client=Mock(), schema="", client=Mock())
    cypher = f"MATCH (e:Event) {keyword} (n:Artist {{name: 'x'}}) RETURN e"

    with patch(
        "agent.tools.query_builder.chat_completion_with_retry",
        return_value=Mock(choices=[Mock(message=Mock(content=cypher))]),
    ):
        data = json.loads(tool.run("find concerts by Radiohead"))

    # Asserted first because it is the property that matters: if the guard ever
    # stops recognising the keyword, "the driver was called" is a clearer
    # failure than whatever the executed Mock raises downstream.
    tool.neo4j.execute_read.assert_not_called()
    assert data["status"] == "error"
    assert "safety" in data["error"].lower()
    assert keyword in data["violations"]


# ── query generation: integration ───────────────────────────────────────────

# Enough schema for the model to have something to read: the graph model,
# identity rules and return shape all live in QUERY_BUILDER_PROMPT itself, and
# a static string keeps this tier dependent on OpenAI alone rather than on a
# live Aura that auto-pauses.
STATIC_SCHEMA = """Node properties:
Event {uid: STRING, name: STRING, name_norm: STRING, description: STRING,
       start_at: DATE_TIME, status: STRING, price_min: FLOAT, price_max: FLOAT,
       price_currency: STRING, ticket_url: STRING, source: STRING}
Artist {uid: STRING, name: STRING, name_norm: STRING}
Venue {uid: STRING, name: STRING, name_norm: STRING, venue_type: STRING,
       location: POINT}
City {uid: STRING, name: STRING, name_norm: STRING, country_code: STRING}
Genre {slug: STRING, name: STRING}
Relationships:
(:Artist)-[:PERFORMS_AT]->(:Event)
(:Event)-[:HOSTED_AT]->(:Venue)
(:Venue)-[:LOCATED_IN]->(:City)
(:Artist)-[:BASED_IN]->(:City)
(:Event)-[:HAS_GENRE]->(:Genre)
(:Artist)-[:HAS_GENRE]->(:Genre)"""


@pytest.fixture(scope="module")
def generated() -> dict[str, str]:
    """One generation per case, shared by both assertions below.

    _generate_cypher rather than run(): the question is what the model emits,
    and run() would drag Neo4j in to execute it.
    """
    tool = QueryBuilderTool(schema=STATIC_SCHEMA)
    return {case["id"]: tool._generate_cypher(case["user_query"]) for case in QUERY_GEN}


@pytest.mark.integration
@pytest.mark.parametrize("case", QUERY_GEN, ids=_ids(QUERY_GEN))
def test_generated_cypher_avoids_forbidden_shapes(case, generated):
    """The hard gate: mutations, and the shapes prompt v2 bans."""
    cypher = generated[case["id"]]
    # The guard's own normalisation, so a venue called "Sunset" in a string
    # literal cannot trip the SET check. Reused rather than reimplemented -
    # a copied validator is a test that cannot fail when the real one breaks.
    stripped = SafetyGuardTool._remove_comments_and_strings(cypher).lower()

    for token in case["should_not_contain"]:
        assert token.lower() not in stripped, f"{case['id']} emitted {token}:\n{cypher}"

    is_safe, violations = SafetyGuardTool().validate_read_only(cypher)
    assert is_safe, f"{case['id']} generated an unsafe query {violations}:\n{cypher}"


@pytest.mark.integration
@pytest.mark.xfail(
    reason="regex over generated Cypher asserts shape, not whether the query "
    "answers the question; execute-and-compare replaces it in phase 4",
    strict=False,
)
@pytest.mark.parametrize("case", QUERY_GEN, ids=_ids(QUERY_GEN))
def test_generated_cypher_matches_expected_patterns(case, generated):
    cypher = generated[case["id"]]
    missing = [
        pattern
        for pattern in case["expected_patterns"]
        if not re.search(pattern, cypher, re.IGNORECASE)
    ]
    assert not missing, f"{case['id']} missing {missing}:\n{cypher}"
