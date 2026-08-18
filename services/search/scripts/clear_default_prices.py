"""Remove the "free" that discovered events never actually claimed.

48 of 57 swept events carry price_min = 0, which the card renders as "free" --
Billy Corgan at the Palacio Vistalegre, CA7RIEL at the Palau Sant Jordi,
Diljit Dosanjh at the Uber Arena. 43 of them link to a ticket shop. The zero
came from an empty string in the extraction reply being read as free, and from
a prompt that offered "0 for free events" without saying what to do when no
price is stated. Both are fixed for new writes; these rows predate the fix.

The rule here is blunt because the data leaves no better one: a stated "gratis"
and a defaulted empty string both ended up as 0.0, and nothing recorded which
was which. So every admin_search zero is cleared, and a genuinely free night
loses its "free" badge until the next sweep reads the page again. That is the
cheap direction of the error -- the expensive one tells someone a 60-euro
stadium show costs nothing.

Promoter submissions are untouched: a person who typed free meant free.

    cd services/search
    uv run --no-sync python scripts/clear_default_prices.py
    uv run --no-sync python scripts/clear_default_prices.py --write
"""

import sys
from pathlib import Path

# Scripts run from the service root ("uv run python scripts/x.py"), where only
# scripts/ is on sys.path -- so the service's own packages have to be added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.graph import _driver
from config import settings
from neo4j import READ_ACCESS, WRITE_ACCESS

FREE_CLAIMS = """
MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)
WHERE e.source = 'admin_search' AND e.price_min = 0
RETURN e.uid AS uid, e.name AS name, v.name AS venue,
       e.ticket_url <> '' AS sells_tickets
ORDER BY sells_tickets DESC, e.name
"""

CLEAR = """
UNWIND $uids AS uid
MATCH (e:Event {uid: uid})
SET e.price_min = null, e.price_max = null
RETURN count(e) AS cleared
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


def main() -> int:
    write = "--write" in sys.argv[1:]

    with open_session(write) as session:
        rows = [dict(r) for r in session.run(FREE_CLAIMS)]
        if not rows:
            print("No discovered event claims to be free.")
            return 0

        for row in rows:
            ticket = "has a ticket link" if row["sells_tickets"] else ""
            print(f"  {row['name'][:40]:<42}{row['venue'][:24]:<26}{ticket}")

        selling = sum(1 for r in rows if r["sells_tickets"])
        print(f"\n{len(rows)} events shown as free, {selling} of them selling tickets.")

        if not write:
            print("Dry run. Pass --write to clear the price on all of them.")
            return 0

        record = session.run(CLEAR, uids=[r["uid"] for r in rows]).single()
        print(f"Cleared the price on {record['cleared']} event(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
