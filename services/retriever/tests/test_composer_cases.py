"""The answer-quality set — eleven replies, checked by rule rather than by judge.

The roadmap's `answer quality` suite (docs/roadmap/01-program.md §3) asked for a
judge rubric at two calls per case. Most of that rubric turns out not to need
one: "1-3 short sentences", "never list events, dates, venues or prices", "one
question, never a list" and "answer in the conversation's language" are all
things a rule reads off the text, and a rule does not have a bad day. Grounding
is the part that would need judgement, and for the two situations where the
composer is most likely to invent — zero results and smalltalk — it reduces to a
rule too: nothing from a fixture it was never given may appear in the reply.

So the judge is deferred, not dropped. It earns its keep on tone ("light, a bit
jazzy, warm"), which no rule reads, and that is worth doing when tone is what is
being changed.

`test_composer_moments.py` already pins the wiring with mocks — which situation
is derived, what reaches the prompt. This asserts what the model writes.
"""

import json
import re
from pathlib import Path

import pytest
from laiive_shared import EventCard
from laiive_shared.language import detect_language

from agent.classifier import Classification
from agent.composer import COMPOSER_PROMPT_VERSION, Composer
from agent.utils.llm_utils import get_openai_client
from config import settings

CASES_FILE = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "evals"
        / "datasets"
        / "answer_quality"
        / "test_cases.json"
    ).read_text(encoding="utf-8")
)
CASES = CASES_FILE["test_cases"]
FIXTURES = CASES_FILE["cards"]

# Same convention as the classifier set: a `known_gap` is a label the live run
# disagreed with and the label won. Kept red, xfailed non-strict, so a weekly
# run reports a regression and a prompt fix reads as XPASS.
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

MONTHS = {
    "10": ["october", "octubre", "ottobre"],
}
# Names no case is ever given. A reply that contains one did not read its ground
# truth — which is the only fabrication a rule can catch without a judge.
DECOYS = ["Razzmatazz", "Wizink", "Primavera Sound", "Rosalía", "Klangfeld"]


def _cards(case) -> list[EventCard]:
    raw = case["cards"]
    rows = FIXTURES[raw] if isinstance(raw, str) else raw
    return [EventCard(**row) for row in rows]


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[.!?…]+", text) if s.strip()]


def _leaks(text: str, cards: list[EventCard]) -> list[str]:
    """What the cards say next to the text, and the text must not repeat.

    Deliberately literal: event name, venue, the time at the door, the month of
    the date and the price. A paraphrase ("the first one, on the Saturday") is
    not caught, and that is the known ceiling of a rule — it catches the
    enumeration the prompt actually forbids.
    """
    lowered = text.lower()
    found = []
    for card in cards:
        for value in (card.name, card.venue):
            if value and value.lower() in lowered:
                found.append(value)
        if card.start_at:
            clock = card.start_at[11:16]  # "21:30"
            if clock and clock in lowered:
                found.append(clock)
            for month in MONTHS.get(card.start_at[5:7], []):
                if month in lowered:
                    found.append(month)
        for price in (card.price_min, card.price_max):
            if price and re.search(rf"\b{int(price)}\b", lowered):
                found.append(str(price))
    return found


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_every_case_names_a_situation_and_a_rule(case):
    """Deterministic: a case with no `expect` would pass by asserting nothing."""
    assert case["expect"].get("max_sentences"), case["id"]
    assert case["expect"].get("language"), case["id"]
    assert case["classification"]["query_type"], case["id"]
    _cards(case)  # the fixture name resolves and the rows are valid cards


def test_the_known_gap_is_counted_and_explained():
    """None open since prompt v3 — pinned so xfailing a case is a decision
    taken here and not a quiet way to stay green."""
    gaps = [case["id"] for case in CASES if case.get("known_gap")]
    assert gaps == [], gaps


def test_the_corpus_matches_the_live_prompt_version():
    assert CASES_FILE["prompt_version"] == COMPOSER_PROMPT_VERSION, (
        f"corpus describes prompt {CASES_FILE['prompt_version']}, composer.py is "
        f"on {COMPOSER_PROMPT_VERSION} - re-read the {len(CASES)} cases, then "
        f"restamp prompt_version"
    )


@pytest.mark.integration
@pytest.mark.parametrize("case", PARAMS)
def test_composed_reply_case(case):
    expect = case["expect"]
    cards = _cards(case)
    client = get_openai_client()

    text = "".join(
        Composer(client).compose_stream(
            case["message"],
            case.get("history"),
            Classification(**case["classification"]),
            cards,
            unsafe=case.get("unsafe", False),
            notes=case.get("notes"),
        )
    )

    wrong: list[str] = []
    if not text.strip():
        wrong.append("empty reply")

    sentences = _sentences(text)
    if len(sentences) > expect["max_sentences"]:
        wrong.append(f"{len(sentences)} sentences > {expect['max_sentences']}")

    questions = text.count("?") + text.count("¿")
    if "questions_min" in expect and questions < expect["questions_min"]:
        wrong.append(f"{questions} questions < {expect['questions_min']}")
    if "questions_max" in expect and questions > expect["questions_max"]:
        wrong.append(f"{questions} questions > {expect['questions_max']}")

    if expect.get("no_list_markers") and re.search(r"(\n\s*[-*\d]|; )", text):
        wrong.append("reads as a list")

    if expect.get("no_leakage"):
        leaked = _leaks(text, cards)
        if leaked:
            wrong.append(f"leaks the cards: {leaked}")

    if expect.get("invents_nothing"):
        invented = [name for name in DECOYS if name.lower() in text.lower()]
        if invented:
            wrong.append(f"invents: {invented}")

    if "mentions_any" in expect and not any(
        word in text.lower() for word in expect["mentions_any"]
    ):
        wrong.append(f"mentions none of {expect['mentions_any']}")

    # Last, because it is the one check that costs a second call. Skippable
    # per case: the detector reads a short English reply carrying "Malasana"
    # and "bossa" as Spanish, and that is a fact about the detector.
    if case.get("check_language", True):
        language = detect_language(client, settings.classifier_model, text)
        if language != expect["language"]:
            wrong.append(f"answered in {language}, not {expect['language']}")

    assert not wrong, f"{case['id']}: " + "; ".join(wrong) + f"\nreply: {text!r}"
