"""EXPLAIN the writer's two event queries against a real Neo4j.

Every unit test fakes the driver by string-matching the query, so a Cypher
syntax error survives a green suite all the way to production. EXPLAIN plans a
query without running it, which is the cheapest way to have the real parser
read what write_event actually sends.

    cd services/shared
    uv run --no-sync python scripts/explain_write_queries.py

Read-only: EXPLAIN executes nothing and writes nothing.
"""

import os
import socket
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laiive_shared.cards import EventDraft  # noqa: E402
from laiive_shared.neo4j_writer import write_event  # noqa: E402

DRAFT = EventDraft(
    name="Jazz Night",
    artists=["Ana Beck Quartet"],
    start_at="2026-09-01T20:00:00",
    venue="Quasimodo",
    address="Kantstrasse 12a",
    city="Berlin",
    price_min=22.0,
    genre="Jazz",
)


class _Capture:
    """Collects the queries write_event would send, answering each one just
    well enough that it reaches the next."""

    def __init__(self, dedup_hit):
        self.queries: list[str] = []
        self._dedup_hit = dedup_hit

    def run(self, query, **params):
        self.queries.append(query)
        outer = self

        class _Result:
            def single(self):
                if "e.owner_id AS owner_id" in query:
                    return outer._dedup_hit
                if "AS artist_uids" in query:
                    return {
                        "uid": params["event_uid"],
                        "name": params["name"],
                        "venue": params["venue"],
                        "city": params["city"],
                        "venue_uid": params["venue_uid"],
                        "artist_uids": [a["uid"] for a in params["artists"]],
                    }
                return None

            def __iter__(self):
                return iter(())

        return _Result()


def capture(dedup_hit) -> str:
    """The event write query for one path — the last one the writer sends."""
    session = _Capture(dedup_hit)
    write_event(session, DRAFT.model_copy(), source="pro_submission", owner_id="u-1")
    return session.queries[-1]


def main() -> int:
    # No python-dotenv in this service's lockfile, and one parser for KEY=value
    # is cheaper than adding a dependency to a throwaway check.
    for line in (
        (Path(__file__).resolve().parents[3] / ".env")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    uri = os.environ["NEO4J_URI"]
    auth = (os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"])

    # DNS here flaps; pre-warming turns an intermittent getaddrinfo failure into
    # a retry rather than a driver that never gets built.
    host = uri.split("//", 1)[-1].split(":")[0]
    for attempt in range(5):
        try:
            socket.gethostbyname(host)
            break
        except OSError as e:
            # Backoff, or five lookups land inside the same flap and all fail.
            print(f"dns attempt {attempt + 1}: {e}")
            time.sleep(2 * (attempt + 1))
    else:
        print("could not resolve the Aura host")
        return 2

    paths = {
        "create": capture(None),
        "adopt": capture(
            {"uid": "existing-uid", "name": "Jazz Night", "owner_id": None}
        ),
    }
    assert "CREATE (e:Event" in paths["create"], "capture picked the wrong query"
    assert (
        "MATCH (e:Event {uid: $event_uid})" in paths["adopt"]
    ), "adoption not captured"

    failed = False
    with GraphDatabase.driver(uri, auth=auth) as driver:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            for label, query in paths.items():
                # A just-resumed Aura routes reads to a follower and has no
                # write service yet, and EXPLAIN of a write query is routed as a
                # write even though it executes nothing. That is a wait, not a
                # syntax verdict, so it is retried rather than reported.
                for attempt in range(6):
                    try:
                        session.run("EXPLAIN " + query, **_PARAMS).consume()
                        print(f"{label}: parses")
                        break
                    except Exception as e:
                        if "WRITE" in str(e) or "write service" in str(e):
                            print(f"{label}: waiting for the write service…")
                            time.sleep(10)
                            continue
                        failed = True
                        print(f"{label}: FAILED\n{e}\n")
                        break
                else:
                    failed = True
                    print(f"{label}: never reached a write server")
    return 1 if failed else 0


# EXPLAIN still type-checks parameters, so every one the query names must be
# present. The values are irrelevant — nothing is executed.
_PARAMS = {
    "picked_uid": None,
    "city": "Berlin",
    "city_norm": "berlin",
    "country_code": "DE",
    "city_lat": 52.52,
    "city_lng": 13.40,
    "venue": "Quasimodo",
    "venue_norm": "quasimodo",
    "venue_uid": "v-1",
    "venue_type": "venue",
    "address": "Kantstrasse 12a",
    "venue_lat": 52.51,
    "venue_lng": 13.44,
    "geocode_precision": "venue",
    "event_uid": "e-1",
    "name": "Jazz Night",
    "name_norm": "jazz night",
    "description": "",
    "start_at": "2026-09-01T20:00:00",
    "timezone": "Europe/Berlin",
    "start_time_known": True,
    "price_min": 22.0,
    "price_max": 22.0,
    "price_currency": "EUR",
    "ticket_url": "",
    "genre": "jazz",
    "genre_name": "Jazz",
    "artists": [
        {"name": "Ana Beck Quartet", "name_norm": "ana beck quartet", "uid": "a-1"}
    ],
    "source": "pro_submission",
    "owner_id": "u-1",
    "source_url": "",
    "source_domain": "",
}


if __name__ == "__main__":
    raise SystemExit(main())
