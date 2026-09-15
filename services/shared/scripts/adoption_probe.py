"""Probe the writer's adoption path against the real graph.

write_event's adoption behaviour (an unowned swept listing taken over by the
promoter who confirms it) is unit-tested against a fake session; this runs
the six promises that have never met live Aura, with probe-named nodes that
cannot collide with real ones, and deletes everything it made:

  1. created_at untouched by adoption
  2. ticket_url and source_url survive a promoter who omits them
  3. no duplicate node (the uid is adopted, not copied)
  4. the artist is attached on the adoption write
  5. a second sweep of a now-owned event is refused
  6. another promoter is refused

Read-only by default: reports leftover probe nodes and exits. --write runs
the probe (writes to Aura, cleans up after itself, leftovers included).

    cd services/shared
    uv run --no-sync python scripts/adoption_probe.py --write
"""

import os
import socket
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from neo4j import READ_ACCESS, WRITE_ACCESS, GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laiive_shared.cards import EventDraft  # noqa: E402
from laiive_shared.neo4j_writer import write_event  # noqa: E402
from laiive_shared.normalize import norm  # noqa: E402

EVENT = "Laiive Adoption Probe Night"
VENUE = "Laiive Probe Venue"
CITY = "Laiive Probe City"
ARTIST = "Laiive Probe Artist"
TICKET_URL = "https://probe.example/tickets"
SOURCE_URL = "https://probe.example/listing"


def drafts() -> tuple[EventDraft, EventDraft]:
    day = (date.today() + timedelta(days=30)).isoformat()
    sweep = EventDraft(
        name=EVENT,
        start_at=f"{day}T21:00",
        venue=VENUE,
        city=CITY,
        ticket_url=TICKET_URL,
    )
    adopt = EventDraft(
        name=EVENT,
        artists=[ARTIST],
        start_at=f"{day}T22:00",
        venue=VENUE,
        address="Probe Street 1",
        city=CITY,
        price_min=10.0,
        # ticket_url deliberately absent: the swept one must survive
    )
    return sweep, adopt


def env() -> tuple[str, tuple[str, str], str]:
    # No python-dotenv in this service's lockfile; same parser as
    # explain_write_queries.py.
    for line in (
        (Path(__file__).resolve().parents[3] / ".env")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    return (
        os.environ["NEO4J_URI"],
        (os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        os.getenv("NEO4J_DATABASE", "neo4j"),
    )


def prewarm(uri: str) -> bool:
    # DNS here flaps; pre-warming turns an intermittent getaddrinfo failure
    # into a retry rather than a driver that never gets built.
    host = uri.split("//", 1)[-1].split(":")[0]
    for attempt in range(5):
        try:
            socket.gethostbyname(host)
            return True
        except OSError as e:
            print(f"dns attempt {attempt + 1}: {e}")
            time.sleep(2 * (attempt + 1))
    return False


def patient_write(fn):
    # A just-resumed Aura has no write service yet: a wait, not a verdict.
    result = fn()
    for _ in range(6):
        if not (result.status == "error" and "write service" in result.message.lower()):
            break
        print("waiting for the write service...")
        time.sleep(10)
        result = fn()
    return result


def leftovers(session) -> list[dict]:
    return session.run(
        """
        MATCH (n)
        WHERE n.name STARTS WITH 'Laiive Probe'
           OR n.name STARTS WITH 'Laiive Adoption Probe'
        RETURN labels(n)[0] AS label, n.name AS name, n.uid AS uid
        """
    ).data()


def cleanup(session) -> int:
    # Event and artists first, then the venue, then the city if the probe
    # was its only tenant. No genre is ever set here, so none is created.
    deleted = 0
    for query in (
        """MATCH (e:Event) WHERE e.name STARTS WITH 'Laiive Adoption Probe'
           DETACH DELETE e""",
        """MATCH (a:Artist) WHERE a.name STARTS WITH 'Laiive Probe'
           DETACH DELETE a""",
        """MATCH (v:Venue) WHERE v.name STARTS WITH 'Laiive Probe'
           DETACH DELETE v""",
        """MATCH (c:City) WHERE c.name STARTS WITH 'Laiive Probe'
           AND NOT (c)<-[:LOCATED_IN]-() DETACH DELETE c""",
    ):
        deleted += session.run(query).consume().counters.nodes_deleted
    return deleted


def main() -> int:
    uri, auth, database = env()
    if not prewarm(uri):
        print("could not resolve the Aura host")
        return 2

    checks: list[tuple[str, bool]] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        checks.append((label, ok))
        suffix = f"  ({detail})" if detail else ""
        print(f"{'PASS' if ok else 'FAIL'}  {label}{suffix}")

    sweep, adopt = drafts()
    write = "--write" in sys.argv
    with GraphDatabase.driver(uri, auth=auth) as driver:
        with driver.session(
            database=database,
            # A paused Aura wakes with reads on a follower long before the
            # write service is back; a read must not route as a write.
            default_access_mode=WRITE_ACCESS if write else READ_ACCESS,
        ) as session:
            if not write:
                left = leftovers(session)
                for row in left:
                    print(f"leftover: {row['label']} {row['name']} {row['uid']}")
                print(
                    f"{len(left)} leftover probe node(s). "
                    "Pass --write to run the probe (writes to Aura)."
                )
                return 0

            try:
                # A dead earlier run leaves an unowned probe event the dedup
                # would answer "duplicate" to - start from a clean slate. This
                # is also what deletes the orphan probe artist.
                stale = cleanup(session)
                if stale:
                    print(f"pre-clean: {stale} stale probe node(s) deleted")

                # -- the sweep writes an unowned listing --
                swept = patient_write(
                    lambda: write_event(
                        session,
                        sweep.model_copy(),
                        source="admin_search",
                        owner_id=None,
                        source_url=SOURCE_URL,
                    )
                )
                if swept.status != "created":
                    print(f"setup failed: {swept.status} {swept.message}")
                    return 2
                before = session.run(
                    "MATCH (e:Event {uid: $uid}) RETURN e.created_at AS c",
                    uid=swept.uid,
                ).single()

                # -- the promoter adopts it --
                adopted = write_event(
                    session,
                    adopt.model_copy(),
                    source="pro_submission",
                    owner_id="laiive-probe-promoter-1",
                )
                check(
                    "adoption happened",
                    adopted.status == "adopted",
                    adopted.message,
                )
                check("uid kept", adopted.uid == swept.uid)

                after = session.run(
                    """MATCH (e:Event {uid: $uid})
                       OPTIONAL MATCH (a:Artist {name_norm: $artist})
                           -[:PERFORMS_AT]->(e)
                       RETURN e.created_at AS c, e.ticket_url AS t,
                              e.source_url AS s, a.uid AS artist_uid""",
                    uid=swept.uid,
                    artist=norm(ARTIST),
                ).single()
                check("created_at untouched", after["c"] == before["c"])
                check(
                    "ticket_url survived",
                    after["t"] == TICKET_URL,
                    str(after["t"]),
                )
                check(
                    "source_url survived",
                    after["s"] == SOURCE_URL,
                    str(after["s"]),
                )
                check("artist attached", after["artist_uid"] is not None)
                count = session.run(
                    "MATCH (e:Event {name_norm: $n}) RETURN count(e) AS c",
                    n=norm(EVENT),
                ).single()["c"]
                check("no duplicate", count == 1, f"count={count}")

                # -- a second sweep is refused --
                resweep = write_event(
                    session,
                    sweep.model_copy(),
                    source="admin_search",
                    owner_id=None,
                    source_url=SOURCE_URL,
                )
                check(
                    "second sweep refused",
                    resweep.status == "duplicate",
                    resweep.message,
                )

                # -- another promoter is refused --
                rival = write_event(
                    session,
                    adopt.model_copy(),
                    source="pro_submission",
                    owner_id="laiive-probe-promoter-2",
                )
                check(
                    "other promoter refused",
                    rival.status == "duplicate",
                    rival.message,
                )
            finally:
                deleted = cleanup(session)
                print(f"cleanup: {deleted} probe node(s) deleted")

    failed = sum(1 for _, ok in checks if not ok)
    print(f"{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
