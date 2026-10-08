"""The vector leg, on frozen vectors.

Same frozen graph as `test_retrieval_cases.py`, and still no OpenAI key: both
the event vectors and each case's question vector were computed once by
`evals/freeze_embeddings.py` and checked in. That is what makes a recall number
here reproducible — embedding live would make the same case score differently
on different days, and a moving number is not a measurement.

Scored as recall@k, not as an exact set: the leg ranks by cosine similarity,
so "the right event is in the top five" is the question, except for the last
case, where the right answer is *nothing* and the similarity threshold is what
has to deliver it.
"""

import json

import pytest

from agent.classifier import Constraints
from agent.executor import Executor
from agent.router import ExecutionPlan, PlanKind
from config import settings
from tests.graph_fixture import DATASET, _FrozenGeocoder, frozen_embeddings, text_key

CASES = json.loads((DATASET / "vector_cases.json").read_text(encoding="utf-8"))[
    "test_cases"
]

pytestmark = pytest.mark.graph


@pytest.fixture(scope="module")
def vector_executor(frozen_graph):
    client, _ = frozen_graph
    embed = frozen_embeddings()
    if embed is None:
        pytest.skip("no frozen embeddings — run `python -m evals.freeze_embeddings`")

    def embed_one(text: str) -> list[float]:
        return embed([text])[0]

    return Executor(
        client, embed_fn=embed_one, query_builder=None, geocoder=_FrozenGeocoder()
    )


def test_the_vector_key_ignores_the_date():
    """The bug this guards, found the day after the fixture was written: the
    composite text carries the event's date, fixture dates move with `now`, so
    a key over the raw text expired overnight and took the whole tier down."""
    assert text_key("A gig at Druso. 2026-01-02. Rock.") == text_key(
        "A gig at Druso. 2027-11-30. Rock."
    )


def test_every_question_has_a_frozen_vector():
    """Deterministic, and the failure worth catching early: a case whose text
    was edited without re-running the freeze script would otherwise fail deep
    inside the executor with a KeyError."""
    vectors = json.loads((DATASET / "embeddings.json").read_text(encoding="utf-8"))
    for case in CASES:
        assert text_key(case["free_text"]) in vectors["vectors"], case["id"]
    assert vectors["model"] == settings.embeddings_model


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_vector_recall_case(case, vector_executor, frozen_graph):
    _, uids = frozen_graph
    hint_of = {uid: hint for hint, uid in uids.items()}

    outcome = vector_executor.execute(
        ExecutionPlan(PlanKind.VECTOR, Constraints(free_text=case["free_text"]))
    )
    assert not outcome.error, outcome.error

    ranked = [hint_of.get(card.uid, card.uid) for card in outcome.cards]
    top_k = ranked[: case["k"]]

    if case["expect"]:
        hits = len(set(case["expect"]) & set(top_k))
        recall = hits / len(case["expect"])
        assert recall >= case["min_recall"], (
            f"{case['id']} ({case['why']}): recall@{case['k']} = {recall:.2f} "
            f"< {case['min_recall']}\n  wanted: {case['expect']}\n  got: {top_k}"
        )
    else:
        assert ranked == [], (
            f"{case['id']} ({case['why']}): expected nothing above the "
            f"{settings.vector_score_threshold} threshold, got {ranked}"
        )

    for hint in case.get("forbidden", []):
        assert hint not in ranked, f"{case['id']}: returned {hint}"
