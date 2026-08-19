"""Make the repair sweep look at named venues again.

The sweep skips a venue it has already stamped `venue` until GEOCODE_RETRY_DAYS
have passed, which is right for a nightly schedule and wrong the moment the
geocoder itself improves: the pin that a fix would correct is exactly the one
the selector no longer offers. This clears the stamp on the venues named and
runs a bounded backfill, so the new chain gets its second chance.

Writes to Aura. Run it deliberately, not on a schedule.

    cd services/search
    uv run --no-sync python scripts/recheck_venue.py "Sant Jordi Club"
"""

import sys
from pathlib import Path

# Scripts run from the service root ("uv run python scripts/x.py"), where only
# scripts/ is on sys.path -- so the service's own packages have to be added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.graph import _driver, run_backfill
from config import settings


def clear_stamps(names: list[str]) -> int:
    with _driver.session(database=settings.neo4j_database) as session:
        record = session.run(
            """
            MATCH (v:Venue)
            WHERE v.name IN $names
            REMOVE v.geocode_checked_at, v.geocode_precision
            RETURN count(v) AS cleared
            """,
            names=names,
        ).single()
    return record["cleared"] if record else 0


def main() -> int:
    names = sys.argv[1:]
    if not names:
        print(__doc__)
        return 2

    cleared = clear_stamps(names)
    if not cleared:
        print(f"No venue matched {names} — names must match exactly.")
        return 1

    print(f"Cleared {cleared} stamp(s); re-running the sweep.")
    # Bounded well above the number cleared: the sweep orders misplaced venues
    # first, so anything else it picks up was overdue anyway.
    print(run_backfill(max_venues=max(5, cleared * 2)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
