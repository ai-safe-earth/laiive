"""Mark events whose midnight start was a default, not a stated time.

30 of the 57 discovered events sit at exactly 00:00 because the listing gave a
day and nothing else, and the card printed that as the start time. New writes
now record `start_time_known` from the text they were parsed from, but these
rows predate it and their original text is gone.

So the rule here is a judgement, and worth stating plainly: an admin_search
event at exactly 00:00:00 is treated as date-only. It can be wrong -- a genuine
midnight set exists -- but every seed event has a real time and none of them is
midnight, while more than half of the swept ones are, which is what a parser
default looks like rather than a scene. Being wrong here costs a card that
shows a day instead of a day and an hour; being wrong the other way tells
someone to turn up twenty hours early.

Promoter submissions are left alone: a person typing a time meant it.

    cd services/search
    uv run --no-sync python scripts/flag_dateless_events.py
    uv run --no-sync python scripts/flag_dateless_events.py --write
"""

import sys
from pathlib import Path

# Scripts run from the service root ("uv run python scripts/x.py"), where only
# scripts/ is on sys.path -- so the service's own packages have to be added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.graph import _driver
from config import settings

MIDNIGHT = """
MATCH (e:Event)
WHERE e.source = 'admin_search'
  AND e.start_at.hour = 0 AND e.start_at.minute = 0 AND e.start_at.second = 0
  AND e.start_time_known IS NULL
RETURN e.uid AS uid, e.name AS name, toString(date(e.start_at)) AS day
ORDER BY day
"""

FLAG = """
UNWIND $uids AS uid
MATCH (e:Event {uid: uid})
SET e.start_time_known = false
RETURN count(e) AS flagged
"""


def main() -> int:
    write = "--write" in sys.argv[1:]

    with _driver.session(database=settings.neo4j_database) as session:
        rows = [dict(r) for r in session.run(MIDNIGHT)]
        if not rows:
            print("No unflagged midnight events.")
            return 0

        for row in rows:
            print(f"  {row['day']}  {row['name'][:56]}")

        if not write:
            print(f"\nDry run. {len(rows)} would be marked date-only; pass --write.")
            return 0

        record = session.run(FLAG, uids=[r["uid"] for r in rows]).single()
        print(f"\nMarked {record['flagged']} event(s) as date-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
