"""The gateway's id is adopted; a direct call gets its own.

Two lines of behaviour, but they are the join key for every telemetry table, so
they get pinned in the shared package rather than in whichever service happened
to implement them — which is exactly how the pusher and the retriever came to
disagree about this in the first place.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from laiive_shared import request_id_from

app = FastAPI()


@app.get("/echo")
def echo(raw: Request):
    return {"request_id": request_id_from(raw)}


client = TestClient(app)


def test_the_gateways_header_wins():
    body = client.get("/echo", headers={"x-request-id": "from-the-gateway"}).json()
    assert body["request_id"] == "from-the-gateway"


def test_header_lookup_is_case_insensitive():
    """Starlette lowercases, but the contract is HTTP's, not Starlette's."""
    body = client.get("/echo", headers={"X-Request-ID": "shouty"}).json()
    assert body["request_id"] == "shouty"


def test_no_header_mints_one():
    first = client.get("/echo").json()["request_id"]
    second = client.get("/echo").json()["request_id"]
    assert first and second and first != second


def test_an_empty_header_is_not_adopted():
    """`or` rather than a presence check: an empty id joins nothing and would
    collide with every other empty one."""
    body = client.get("/echo", headers={"x-request-id": ""}).json()
    assert body["request_id"]
