"""The frozen graph: start it, wipe it, seed it, hand it to a test.

Eighteen events from `evals/datasets/retrieval/graph.json`, written through
`laiive_shared.neo4j_writer.write_event` — the same path the pusher and the
search service use. Seeding through the writer rather than through hand-rolled
MERGEs is the point: uid derivation, `name_norm`, genre families, timezone
resolution and the `start_time_known` flag all come out exactly as they do in
production, and cannot drift from it as the writer changes.

Two collaborators are replaced, because both would otherwise reach the network:

* the geocoder, by `_FrozenGeocoder` — the fixture's own coordinates, which is
  what makes the nearby leg's metres assertable;
* the embedder, by `frozen_embeddings()` — vectors computed once by
  `evals/freeze_embeddings.py` and stored in the dataset, keyed by a
  hash of the exact text embedded. A text that changes misses its key and the
  seed fails loudly rather than silently embedding nothing.

Connection is `NEO4J_TEST_URI`, a setting of its own and never `NEO4J_URI`:
this module's first act is `MATCH (n) DETACH DELETE n`, and the root `.env`
points `NEO4J_URI` at production Aura.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from laiive_shared import EventDraft
from laiive_shared.geocode import GeocodeResult
from laiive_shared.neo4j_writer import backfill_embeddings, write_event
from neo4j import GraphDatabase

DATASET = Path(__file__).resolve().parents[1] / "evals" / "datasets" / "retrieval"
GRAPH = json.loads((DATASET / "graph.json").read_text(encoding="utf-8"))
EMBEDDING_MODEL = "text-embedding-3-small"

# The one thing in a fixture text that changes by itself — see text_key.
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

TEST_URI = os.getenv("NEO4J_TEST_URI", "bolt://localhost:7689")
TEST_DATABASE = os.getenv("NEO4J_TEST_DATABASE", "neo4j")
TEST_AUTH = (
    os.getenv("NEO4J_TEST_USERNAME", "neo4j"),
    os.getenv("NEO4J_TEST_PASSWORD", "laiive-test-graph"),  # pragma: allowlist secret
)


def text_key(text: str) -> str:
    """How a frozen vector is looked up: the sha1 of the text embedded, with
    dates masked out first.

    The mask is the whole reason this works. Fixture dates are offsets from the
    seed moment, so the composite text carries a different date every day the
    suite runs — and a key over the raw text missed every vector the day after
    the freeze, taking the whole vector tier down with a loud KeyError. Masking
    `YYYY-MM-DD` makes the key depend on the wording, which is what a re-freeze
    is actually for. The stored vector was computed from the text as it read on
    freeze day: the date it carries is a few characters of a sentence about a
    gig, and the cases assert ranking between events that all shift together.
    """
    return hashlib.sha1(_DATE.sub("<date>", text).encode("utf-8")).hexdigest()[:16]


def frozen_embeddings():
    """The frozen embedder, or None when the file has not been generated.

    Returned as a function of the same shape as the real batch embedder, so the
    writer cannot tell the difference.
    """
    path = DATASET / "embeddings.json"
    if not path.exists():
        return None
    vectors = json.loads(path.read_text(encoding="utf-8"))["vectors"]

    def embed_texts(texts: list[str]) -> list[list[float]]:
        missing = [t for t in texts if text_key(t) not in vectors]
        if missing:
            raise KeyError(
                f"{len(missing)} text(s) have no frozen vector — the fixture "
                f"changed since evals/freeze_embeddings.py last ran. "
                f"First: {missing[0][:120]!r}"
            )
        return [vectors[text_key(t)] for t in texts]

    return embed_texts


class _FrozenGeocoder:
    """The fixture's own coordinates, with the real geocoder's two methods.

    Country codes go out upper-case because that is what `NominatimGeocoder`
    does (geocode.py:273) before the writer stores them unchanged, and the
    reader's country filter compares against `.upper()`. A fake that lowercased
    them produced a graph where "events in Italy" matched nothing — a fixture
    bug, but exactly the shape of the production bug the case is there to
    catch, so it is worth naming here.
    """

    def geocode(self, query: str) -> GeocodeResult | None:
        city = GRAPH["cities"].get(query)
        if not city:
            return None
        return GeocodeResult(
            lat=city["lat"],
            lng=city["lng"],
            country_code=city["country_code"].upper(),
            display_name=query,
        )

    def geocode_venue(self, venue, address=None, city=None, **kwargs):
        row = GRAPH["venues"].get(venue)
        if not row:
            return None
        parent = GRAPH["cities"][row["city"]]
        return GeocodeResult(
            lat=row["lat"],
            lng=row["lng"],
            country_code=parent["country_code"].upper(),
            display_name=f"{venue}, {row['city']}",
        )


def _draft(event: dict, now: datetime) -> EventDraft:
    """One fixture row as the draft the writer takes.

    Dates are offsets rather than timestamps: every leg filters on upcoming
    events, so a fixture of fixed dates would quietly stop testing anything the
    week after it was written.
    """
    venue = GRAPH["venues"][event["venue"]]
    day = (now + timedelta(days=event["in_days"])).date()
    return EventDraft(
        name=event["name"],
        artists=event["artists"],
        start_at=f"{day.isoformat()}T{event['at']}:00",
        venue=event["venue"],
        venue_type=venue["venue_type"],
        address=venue["address"],
        city=venue["city"],
        price_min=event["price_min"],
        price_currency="EUR",
        genre=event.get("genre"),
        description=event.get("description"),
    )


def seed(session, *, now: datetime | None = None, embed_texts=None) -> dict[str, str]:
    """Wipe and re-seed. Returns {uid_hint: real uid}.

    Cases name events by their hint ("mad-jazz-1"), never by a uid — the writer
    mints those, and a dataset carrying them would have to be regenerated every
    time the fixture is re-seeded.
    """
    now = now or datetime.now()
    session.run("MATCH (n) DETACH DELETE n")

    uids: dict[str, str] = {}
    for event in GRAPH["events"]:
        result = write_event(
            session,
            _draft(event, now),
            source="seed",
            geocoder=_FrozenGeocoder(),
        )
        if result.status != "created":
            raise RuntimeError(
                f"{event['uid_hint']}: writer said {result.status} — "
                f"{result.message} {result.missing}"
            )
        uids[event["uid_hint"]] = result.uid
        # The writer only ever writes scheduled events, which is correct: a
        # cancelled listing is an edit, not a publication. The fixture needs one
        # anyway, to assert that no leg returns it.
        if event.get("status") and event["status"] != "scheduled":
            session.run(
                "MATCH (e:Event {uid: $uid}) SET e.status = $status",
                uid=result.uid,
                status=event["status"],
            )

    # Events only. The vector leg queries the event index, and embedding the
    # artists and venues as well would triple the frozen file for vectors
    # nothing here reads.
    embed_texts = embed_texts or frozen_embeddings()
    if embed_texts is not None:
        backfill_embeddings(
            session, embed_texts, EMBEDDING_MODEL, uids=list(uids.values())
        )
    return uids


def apply_schema(session) -> list[str]:
    """Production's DDL, minus what Community cannot run. Returns what it skipped.

    The statements come from `agent.scripts.setup_schema`, not a copy of them,
    so the fixture's schema follows production's by construction. Two kinds do
    not survive the Community image: property-existence constraints and the
    City NODE KEY, both Enterprise-only. Neither changes what a read returns —
    they stop bad *writes*, and the only writer here is the seed — so the trade
    is a fixture that runs on the free image against a schema that is otherwise
    the real one. An Enterprise test image would close the gap at the cost of a
    licence question for one node key.
    """
    from agent.scripts import setup_schema

    skipped = []
    for statement in (
        setup_schema.constraints + setup_schema.indexes + setup_schema.vector_indexes
    ):
        try:
            session.run(statement)
        except Exception as e:
            if "Enterprise Edition" not in str(e):
                raise
            skipped.append(statement)
    return skipped


def driver():
    return GraphDatabase.driver(TEST_URI, auth=TEST_AUTH)


def read_client(test_driver):
    """The retriever's own Neo4jClient, pointed at the fixture.

    Its constructor reads `settings` and builds a driver to Aura, so the driver
    is swapped in rather than passed — what matters is that `execute_read` is
    the real one, retry ladder and Neo4j type conversion included, since that
    conversion is part of what the rows a card is built from look like.
    """
    from agent.clients.neo4j_client import Neo4jClient

    client = Neo4jClient.__new__(Neo4jClient)
    client._driver = test_driver
    return client


def reachable() -> bool:
    """Whether the container is up — the tests skip rather than fail when not."""
    try:
        with driver() as d:
            d.verify_connectivity()
        return True
    except Exception:
        return False
