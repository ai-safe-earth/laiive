"""The weekly feedback read: the parts that need no Supabase and no model."""

from agent.scripts.feedback import assign, build_turns, remember, signals, worth_reading


def _log(rid, messages, status=200, route="/api/chat/stream"):
    return {
        "request_id": rid,
        "route": route,
        "status": status,
        "payload": {"messages": messages},
        "created_at": "2026-10-01T20:00:00Z",
    }


Q1 = [{"role": "user", "content": "jazz in Bergamo"}]
A1 = {"role": "assistant", "content": "Two jazz nights."}
Q2 = [*Q1, A1, {"role": "user", "content": "other ones?"}]


def test_turns_join_answer_and_thumbs_and_skip_other_routes():
    turns = build_turns(
        [_log("a", Q1), _log("b", Q2), _log("c", Q1, route="/api/publish")],
        [
            {
                "request_id": "b",
                "final_text": "Same two.",
                "query_type": "event_search",
                "row_count": 0,
                "errors": None,
            }
        ],
        [
            {"request_id": "b", "rating": "down", "reason": None},
            {"request_id": "b", "rating": "down", "reason": "same events again"},
        ],
    )
    assert [t["id"] for t in turns] == ["a", "b"]
    a, b = turns
    # No eval record for "a": its answer is read from the next turn's history.
    assert a["answer"] == "Two jazz nights." and a["rating"] is None
    assert b["answer"] == "Same two." and b["earlier_turns"] == 1
    assert (b["rating"], b["reason"]) == ("down", "same events again")
    assert signals(b) == ["no-events"] and worth_reading(b)
    assert not worth_reading(a)


def test_graph_errors_and_refusals_are_labelled_in_code():
    t = build_turns(
        [_log("x", Q1, status=502)],
        [
            {
                "request_id": "x",
                "final_text": "",
                "query_type": "event_search",
                "row_count": 0,
                "errors": ["ServiceUnavailable: no route"],
            }
        ],
        [],
    )[0]
    assert signals(t) == ["graph-down", "http-502", "no-events", "answer-not-recorded"]


def test_every_turn_lands_in_exactly_one_thread():
    threads = [{"name": "dupes", "kind": "failure", "description": "d"}]
    out = assign(threads, {"0": "dupes", "2": "not-a-listed-name"}, 3)
    assert {th["name"]: th["ids"] for th in out} == {"dupes": [0], "unsorted": [1, 2]}


def test_the_saved_file_keeps_counts_not_user_text():
    known = {"old": {"kind": "failure", "description": "x", "last_count": 4}}
    out = remember(
        [{"name": "dupes", "kind": "failure", "description": "d", "ids": [0, 1]}],
        known,
        "2026-10-09",
    )
    assert out["old"]["last_count"] == 0
    assert out["dupes"] == {
        "kind": "failure",
        "description": "d",
        "last_count": 2,
        "last_run": "2026-10-09",
    }
