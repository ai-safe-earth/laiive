"""The write path's answer to a waking Aura: rebuild the driver, retry once.

A driver that built its routing table while Aura was paused keeps failing
after Aura is back — on 2026-09-12 the pusher stayed not_ready through a
whole flap recovery and needed a process restart. write_event now heals that
in-process; these pin the retry to transient errors only.
"""

from unittest.mock import MagicMock

from laiive_shared import EventDraft
from laiive_shared.neo4j_writer import WriteResult

from agent import graph

FLAP = WriteResult(status="error", message="Unable to retrieve routing information")
OK = WriteResult(status="created", uid="e-1", name="X")


def test_transient_error_rebuilds_the_driver_and_retries(monkeypatch):
    calls = []

    def fake_shared(session, draft, **kwargs):
        calls.append(draft)
        return FLAP if len(calls) == 1 else OK

    poisoned = MagicMock(name="poisoned")
    fresh = MagicMock(name="fresh")
    monkeypatch.setattr(graph, "_shared_write_event", fake_shared)
    monkeypatch.setattr(graph, "_driver", poisoned)
    monkeypatch.setattr(graph, "_build_driver", lambda: fresh)

    result = graph.write_event(EventDraft())

    assert result.status == "created"
    assert len(calls) == 2
    poisoned.close.assert_called_once()
    assert graph._driver is fresh


def test_a_real_error_is_not_retried(monkeypatch):
    broken = WriteResult(status="error", message="constraint violation")
    calls = []

    def fake_shared(session, draft, **kwargs):
        calls.append(draft)
        return broken

    driver = MagicMock()
    monkeypatch.setattr(graph, "_shared_write_event", fake_shared)
    monkeypatch.setattr(graph, "_driver", driver)

    result = graph.write_event(EventDraft())

    assert result.status == "error"
    assert len(calls) == 1
    driver.close.assert_not_called()


def test_transient_signatures_match_what_the_driver_actually_says():
    assert graph.is_transient_graph_error("Unable to retrieve routing information")
    assert graph.is_transient_graph_error("No write service currently available")
    assert graph.is_transient_graph_error(
        "SessionExpired: Failed to obtain connection towards 'READ' server."
    )
    assert not graph.is_transient_graph_error("constraint violation")
