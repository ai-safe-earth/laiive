"""Card ordering inside a turn — no Neo4j, no OpenAI, just the sort."""

from laiive_shared import EventCard

from agent.pipeline import known_context, many_results_note, verified_first


def card(uid: str, source: str) -> EventCard:
    return EventCard(uid=uid, name=uid, artists=[], source=source)


def test_promoter_submissions_lead():
    cards = [card("a", "admin_search"), card("b", "pro_submission"), card("c", "seed")]
    verified_first(cards)
    assert [c.uid for c in cards] == ["b", "a", "c"]


def test_the_sort_is_stable_inside_each_group():
    """Each leg's own ORDER BY has to survive: only the two groups move."""
    cards = [
        card("a", "admin_search"),
        card("b", "seed"),
        card("c", "pro_submission"),
        card("d", "admin_search"),
        card("e", "pro_submission"),
    ]
    verified_first(cards)
    assert [c.uid for c in cards] == ["c", "e", "a", "b", "d"]


def test_it_sorts_in_place():
    """run_turn yields the same list object it filled, and api.py reads it after."""
    cards = [card("a", "seed"), card("b", "pro_submission")]
    same = cards
    verified_first(cards)
    assert same is cards
    assert same[0].uid == "b"


def test_a_long_list_is_counted_and_a_very_long_one_suggests_narrowing():
    assert many_results_note(10, capped=False) is None
    assert many_results_note(14, capped=False).startswith("14 events matched")
    assert "narrowing" not in many_results_note(14, capped=False)
    note = many_results_note(50, capped=True)
    assert note.startswith("50+ events matched") and "genre, distance or price" in note


def test_the_composer_always_knows_place_day_and_hour():
    shared = known_context({"latitude": 45.7, "longitude": 9.7}, "Europe/Rome")
    assert "location is shared" in shared and ":" in shared
    assert "not shared" in known_context(None, None)
