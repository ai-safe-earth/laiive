"""Re-read every pre-timezone start time in the venue's own zone.

Every event written before the writer resolved timezones stored a wall-clock
reading as UTC. A promoter in Bergamo typing 22:00 got `2026-08-22T22:00:00Z`,
which is midnight the next day at the door -- the card answered a query for
"today" with a date of tomorrow. All 41 timed rows in the graph are shifted by
their venue's offset: one hour in winter, two in summer, across ES, DE and IT.

The repair is to keep the wall-clock reading, which was always the true one,
and attach the zone it was read in: 22:00Z becomes 22:00+02:00.

Date-only rows are deliberately left alone. Their 00:00 is a parser default
rather than a stated time (see flag_dateless_events.py), so there is no
wall-clock reading to preserve -- and localising midnight would move the
calendar date the card prints, which is the one thing those rows do claim.

Rows whose venue has no pin are skipped and listed: without a coordinate there
is no zone, and guessing one from the country is what this is fixing.

    cd services/search
    uv run --no-sync python scripts/localize_event_start_times.py
    uv run --no-sync python scripts/localize_event_start_times.py --write
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Scripts run from the service root ("uv run python scripts/x.py"), where only
# scripts/ is on sys.path -- so the service's own packages have to be added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.graph import _driver
from config import settings
from laiive_shared.neo4j_writer import resolve_timezone
from neo4j import READ_ACCESS, WRITE_ACCESS

# An empty or absent `timezone` is the mark of a row written before the fix.
# The venue's pin is preferred over the city's for the same reason the writer
# prefers it, though a zone boundary rarely runs between the two.
# The WHERE sits above the OPTIONAL MATCH on purpose: below it, Cypher reads it
# as part of the optional pattern and nulls the city instead of dropping the
# row, which quietly turned this selection into "every event".
UNZONED = """
MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)
WHERE coalesce(e.timezone, '') = ''
  AND NOT (e.start_at.hour = 0 AND e.start_at.minute = 0 AND e.start_at.second = 0)
  AND coalesce(e.start_time_known, true) = true
OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)
RETURN e.uid AS uid, e.name AS name, toString(e.start_at) AS start_at,
       v.name AS venue, c.name AS city,
       coalesce(v.location.latitude, c.location.latitude) AS lat,
       coalesce(v.location.longitude, c.location.longitude) AS lng
ORDER BY start_at
"""

RESTAMP = """
UNWIND $rows AS row
MATCH (e:Event {uid: row.uid})
SET e.start_at = datetime(row.start_at), e.timezone = row.timezone,
    e.updated_at = datetime()
RETURN count(e) AS restamped
"""


def open_session(write: bool):
    """A dry run gets a read-only session, so "dry" is enforced, not promised.

    It also routes around the Aura free tier, which drops its WRITE server
    while paused: a read-only session connects when a write one cannot.
    """
    return _driver.session(
        database=settings.neo4j_database,
        default_access_mode=WRITE_ACCESS if write else READ_ACCESS,
    )


def relocalise(start_at: str, zone: str) -> str:
    """Keep the wall-clock reading, replace the zone it is read in."""
    return (
        datetime.fromisoformat(start_at)
        .replace(tzinfo=None, microsecond=0)
        .replace(tzinfo=ZoneInfo(zone))
        .isoformat()
    )


def main() -> int:
    write = "--write" in sys.argv[1:]

    with open_session(write) as session:
        rows = [dict(r) for r in session.run(UNZONED)]
        if not rows:
            print("Every timed event already carries a timezone.")
            return 0

        updates, skipped = [], []
        for row in rows:
            zone = resolve_timezone(row["lat"], row["lng"])
            if zone is None:
                skipped.append(row)
                continue
            moved = relocalise(row["start_at"], zone)
            updates.append({"uid": row["uid"], "start_at": moved, "timezone": zone})
            print(
                f"  {row['start_at']} -> {moved}  {zone:<16} "
                f"{(row['name'] or '')[:34]} @ {row['city']}"
            )

        for row in skipped:
            print(f"  SKIP (no pin)  {(row['name'] or '')[:34]} @ {row['city']}")

        if not write:
            print(
                f"\nDry run. {len(updates)} event(s) would be re-stamped, "
                f"{len(skipped)} skipped for want of a coordinate; pass --write."
            )
            return 0

        record = session.run(RESTAMP, rows=updates).single()
        print(f"\nRe-stamped {record['restamped']} event(s).")
        if skipped:
            print(f"{len(skipped)} left as UTC — no venue or city coordinate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
