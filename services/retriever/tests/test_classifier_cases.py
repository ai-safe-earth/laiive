"""The classifier golden set — twenty messages, labelled by intent.

The roadmap's `classifier` suite (docs/roadmap/01-program.md §3). Labels say
what a reader of the message would expect, not what the model answered when the
set was written, so a red case here is a finding about the prompt and not a
stale fixture to restamp.

Integration-only: every case is one live classification. That is what makes it
worth having — `test_classifier.py` already pins the wiring with a mock, which
proves nothing about whether "free concerts in Bilbao" reaches `price_max: 0`.
The weekly workflow (.github/workflows/evals-weekly.yml) is what runs it.

Neo4j is not needed: `Classifier` takes an OpenAI client and a prompt, and
nothing here touches the graph.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from agent.classifier import CLASSIFIER_PROMPT_VERSION, Classifier, now_in
from agent.utils.llm_utils import get_openai_client

# Every case is read on this clock, so "tonight" and "tomorrow" are a fixed
# thing to assert rather than whatever zone the runner happens to sit in.
TIMEZONE = "Europe/Madrid"

CASES_FILE = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "evals"
        / "datasets"
        / "classifier"
        / "test_cases.json"
    ).read_text(encoding="utf-8")
)
CASES = CASES_FILE["test_cases"]

# A `known_gap` is a label the first live run disagreed with and the label won:
# the case stays red on purpose, xfailed so a weekly run reports a *regression*
# rather than re-reporting six holes somebody already knows about. Not strict,
# because the prompt getting fixed should turn the case green (XPASS) without
# anyone having to edit the dataset in the same commit.
PARAMS = [
    pytest.param(
        case,
        id=case["id"],
        marks=pytest.mark.xfail(reason=case["known_gap"], strict=False)
        if "known_gap" in case
        else (),
    )
    for case in CASES
]


def test_the_corpus_matches_the_live_prompt_version():
    """Same machine link as the query-generation set: a prompt bump has to be
    read against these twenty cases rather than silently outdating them."""
    assert CASES_FILE["prompt_version"] == CLASSIFIER_PROMPT_VERSION, (
        f"corpus describes prompt {CASES_FILE['prompt_version']}, classifier.py "
        f"is on {CLASSIFIER_PROMPT_VERSION} - re-read the {len(CASES)} cases "
        f"against the new prompt, then restamp prompt_version"
    )


def test_every_case_asserts_something():
    """A case with an empty `expect` passes by doing nothing."""
    assert len(CASES) == 20
    ids = [case["id"] for case in CASES]
    assert len(set(ids)) == len(ids), "duplicate case id"
    for case in CASES:
        assert case["expect"], case["id"]


def test_the_known_gaps_are_counted_and_explained():
    """None open since prompt v3 (all six closed). Pinned so that xfailing a case
    is a decision somebody makes here rather than a quiet way to go green."""
    gaps = [case["id"] for case in CASES if case.get("known_gap")]
    assert len(gaps) == 0, gaps
    for case in CASES:
        if "known_gap" in case:
            assert len(case["known_gap"]) > 40, case["id"]


def _matches(actual, expected) -> bool:
    """The dataset's three-value vocabulary, plus the two date words.

    `null` means empty, `"any"` means filled, anything else is an equality —
    case-insensitive for strings, because a city is a name and not a token.
    """
    if expected is None:
        return not actual
    if expected == "any":
        return bool(actual)
    if expected in ("today", "tomorrow"):
        if not actual:
            return False
        day = now_in(TIMEZONE).date()
        if expected == "tomorrow":
            day += timedelta(days=1)
        return str(actual).startswith(day.isoformat())
    if isinstance(expected, str) and isinstance(actual, str):
        return actual.strip().lower() == expected.strip().lower()
    return actual == expected


@pytest.mark.integration
@pytest.mark.parametrize("case", PARAMS)
def test_classifier_case(case):
    expect = case["expect"]
    result = Classifier(get_openai_client()).classify(
        case["message"],
        case.get("history"),
        has_location=case.get("has_location", False),
        timezone=TIMEZONE,
    )

    # Collected rather than asserted one at a time: a case that gets the city
    # right and the date wrong should say so in one line, since the point of
    # the run is reading what the prompt does across twenty messages.
    wrong: list[str] = []
    for field in ("query_type", "moment", "language", "clarification"):
        if field in expect and not _matches(getattr(result, field), expect[field]):
            wrong.append(f"{field}: {getattr(result, field)!r} != {expect[field]!r}")

    if "sub_query_count" in expect:
        if len(result.sub_queries) != expect["sub_query_count"]:
            wrong.append(
                f"sub_queries: {len(result.sub_queries)} != {expect['sub_query_count']}"
            )

    # Constraints are asserted against *any* sub-query, not the first: a
    # two-city ask is one intent split in two, and which half comes back first
    # is not something the label should pin.
    for field, want in expect.get("constraints", {}).items():
        if not any(_matches(getattr(c, field), want) for c in result.sub_queries):
            got = [getattr(c, field) for c in result.sub_queries]
            wrong.append(f"{field}: {got!r} has no {want!r}")

    assert not wrong, f"{case['id']}: " + "; ".join(wrong)
