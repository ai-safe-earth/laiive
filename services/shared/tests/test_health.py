"""Liveness must never depend on anything; readiness must not become load."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from laiive_shared.health import register_health


def build(check, cache_seconds=20.0):
    app = FastAPI()
    register_health(app, service="test", ready_check=check, cache_seconds=cache_seconds)
    return TestClient(app)


def test_livez_answers_without_touching_the_check():
    calls = []

    def check():
        calls.append(1)
        return True

    client = build(check)
    response = client.get("/livez")
    assert response.status_code == 200
    assert response.json()["service"] == "test"
    # The whole point: a wedged dependency must not restart a healthy process.
    assert calls == []


def test_livez_answers_even_when_the_dependency_is_down():
    def check():
        raise ConnectionError("neo4j is gone")

    client = build(check)
    assert client.get("/livez").status_code == 200
    assert client.get("/readyz").status_code == 503


def test_readyz_503s_on_a_false_or_raising_check():
    assert build(lambda: False).get("/readyz").status_code == 503

    def raising():
        raise TimeoutError("aura is paused")

    body = build(raising).get("/readyz").json()
    assert body["status"] == "not_ready"
    assert "TimeoutError" in body["reason"]


def test_a_ready_result_is_cached():
    """N replicas probing every 30s must not become traffic of their own."""
    calls = []

    def check():
        calls.append(1)
        return True

    client = build(check)
    for _ in range(5):
        assert client.get("/readyz").status_code == 200
    assert len(calls) == 1


def test_a_failure_is_not_cached_so_recovery_is_immediate():
    outcomes = [False, False, True]
    client = build(lambda: outcomes.pop(0), cache_seconds=60.0)

    assert client.get("/readyz").status_code == 503
    assert client.get("/readyz").status_code == 503
    # Recovered on the very next probe, not up to a cache window later.
    assert client.get("/readyz").status_code == 200
