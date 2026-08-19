"""The internal-key layer must fail closed — and must not lock out the kubelet."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from laiive_shared.health import register_health
from laiive_shared.internal_auth import HEADER, install_internal_auth

KEY = "s3cret-shared-with-the-gateway"


def build(key: str) -> TestClient:
    app = FastAPI()
    register_health(app, service="test", ready_check=lambda: True)

    @app.post("/chat")
    def chat():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    install_internal_auth(app, expected=key)
    return TestClient(app)


def test_a_request_without_the_key_is_refused():
    client = build(KEY)
    response = client.post("/chat")
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


def test_a_request_with_a_wrong_key_is_refused():
    assert build(KEY).post("/chat", headers={HEADER: "not-the-key"}).status_code == 403


def test_a_request_with_the_key_passes_through():
    response = build(KEY).post("/chat", headers={HEADER: KEY})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_probes_answer_without_the_key():
    """The kubelet cannot authenticate; gating the probes would kill every pod."""
    client = build(KEY)
    assert client.get("/livez").status_code == 200
    assert client.get("/readyz").status_code == 200
    # /health is the operator's window into a service whose key may be wrong.
    assert client.get("/health").status_code == 200


def test_no_key_configured_is_a_no_op():
    """Local runs, compose and every existing test must behave as before."""
    client = build("")
    assert client.post("/chat").status_code == 200
