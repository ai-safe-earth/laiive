"""Retrieval recall over the frozen graph.

The roadmap's `retrieval` suite (docs/roadmap/01-program.md §3). What separates
it from `test_executor.py` is the thing underneath: those tests hand the
executor a `Mock` whose `execute_read` returns whatever it was told to, which
can say that a row maps to a card but nothing at all about whether the query
finds the event. Here the query runs against eighteen real events in a real
Neo4j, and the case says which ones must come back.

Marked `graph`, not `integration`: it needs a database but no OpenAI key and no
Aura, so CI can hold it as a service container. `make test-graph-up` starts it
locally; without it the cases skip rather than fail.

The ceiling, stated once: green here means the retrieval *code* is right, not
that production answers well. The fixture has no bad geocodes, no duplicate
venues and no missing genres, which is exactly what the real graph does have.
That stays the Aura tier's question.
"""

import json
from datetime import datetime, timedelta

import pytest

from agent.classifier import Constraints
from agent.executor import Executor
from agent.router import ExecutionPlan, PlanKind
from tests.graph_fixture import DATASET, _FrozenGeocoder

CASES = json.loads((DATASET / "test_cases.json").read_text(encoding="utf-8"))[
    "test_cases"
]
LEGS = {"template": PlanKind.TEMPLATE, "nearby": PlanKind.NEARBY}

pytestmark = pytest.mark.graph


def _constraints(case: dict) -> Constraints:
    """The case's constraints, with the date window resolved against now.

    A window is written in days because the graph is seeded relative to the
    moment the fixture ran; a literal date in the dataset would drift out of
    the corpus within a week.
    """
    raw = dict(case["constraints"])
    window = raw.pop("date_window_days", None)
    if window:
        now = datetime.now()
        start = (now + timedelta(days=window[0])).date()
        end = (now + timedelta(days=window[1])).date()
        raw["date_from"] = f"{start.isoformat()}T00:00:00"
        raw["date_to"] = f"{end.isoformat()}T00:00:00"
    return Constraints(**raw)


@pytest.fixture(scope="module")
def executor(frozen_graph):
    client, _ = frozen_graph
    # The embedder is never called on these legs; the vector cases live in
    # test_retrieval_vector_cases.py, which has frozen question vectors.
    return Executor(
        client,
        embed_fn=lambda text: (_ for _ in ()).throw(
            AssertionError("no leg here should embed")
        ),
        query_builder=None,
        geocoder=_FrozenGeocoder(),
    )


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_recall_case(case, executor, frozen_graph):
    _, uids = frozen_graph
    hint_of = {uid: hint for hint, uid in uids.items()}

    plan = ExecutionPlan(LEGS[case["leg"]], _constraints(case))
    outcome = executor.execute(plan, case.get("location"))

    assert not outcome.error, outcome.error
    got = [hint_of.get(card.uid, card.uid) for card in outcome.cards]

    # Exact, not a superset: on a filter leg an extra event is as wrong as a
    # missing one — it is a constraint that did not hold.
    assert sorted(got) == sorted(case["expect"]), (
        f"{case['id']} ({case['why']})\n"
        f"  missing: {sorted(set(case['expect']) - set(got))}\n"
        f"  unexpected: {sorted(set(got) - set(case['expect']))}"
    )
    for hint in case.get("forbidden", []):
        assert hint not in got, f"{case['id']}: returned {hint}"


def test_the_cancelled_and_past_events_are_unreachable(executor, frozen_graph):
    """The two rows every case is implicitly about.

    Asserted once over every case rather than per case: a leg that started
    returning cancelled events would otherwise only be caught by whichever
    case happened to list it as forbidden.
    """
    _, uids = frozen_graph
    hint_of = {uid: hint for hint, uid in uids.items()}

    seen: set[str] = set()
    for case in CASES:
        outcome = executor.execute(
            ExecutionPlan(LEGS[case["leg"]], _constraints(case)), case.get("location")
        )
        seen.update(hint_of.get(card.uid, card.uid) for card in outcome.cards)

    assert "mad-cancelled-1" not in seen
    assert "mad-past-1" not in seen


def test_the_corpus_covers_both_legs():
    legs = {case["leg"] for case in CASES}
    assert legs == {"template", "nearby"}, legs
    assert len(CASES) == 10
