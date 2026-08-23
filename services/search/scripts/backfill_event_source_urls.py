"""Give already-approved discovered events the page they were read off.

`Candidate.source_url` has been on every sweep candidate since discovery
existed, and approve dropped it: it read `candidate["draft"]` and nothing else.
So every event written by an approve before that was fixed sits in the graph
with no way back to its listing, while the card's own copy promises "we found
this listing with our own web search".

The URLs are not lost — they are still in `search_reports.candidates` in
Supabase. This re-joins them to the graph on the identity the writer itself
dedups by: normalised name + calendar day + normalised venue. That triple is
what `write_event`'s own duplicate probe treats as one event, so a match here
is a match by the same rule that created the row.

Events whose report has since been deleted keep an empty source_url. That is
correct and must stay renderable: the card decides which mark to show from
`source`, never from the URL.

    cd services/search
    uv run --no-sync python scripts/backfill_event_source_urls.py
    uv run --no-sync python scripts/backfill_event_source_urls.py --write
"""

import sys
from pathlib import Path

# Scripts run from the service root ("uv run python scripts/x.py"), where only
# scripts/ is on sys.path -- so the service's own packages have to be added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import reports
from agent.graph import _driver
from config import settings
from laiive_shared.normalize import norm, source_domain
from neo4j import READ_ACCESS, WRITE_ACCESS

UNSOURCED = """
MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)
WHERE e.source = 'admin_search' AND coalesce(e.source_url, '') = ''
RETURN e.uid AS uid, e.name AS name, e.name_norm AS name_norm,
       v.name_norm AS venue_norm, toString(date(e.start_at)) AS day
ORDER BY day
"""

STAMP = """
UNWIND $rows AS row
MATCH (e:Event {uid: row.uid})
SET e.source_url = row.source_url, e.source_domain = row.source_domain,
    e.updated_at = datetime()
RETURN count(e) AS stamped
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


def fetch_all_reports() -> list[dict]:
    """Every report's candidates. `list_reports` deliberately omits them."""
    response = reports._http.get(
        reports._url(),
        headers=reports._headers(),
        params={"select": "id,city,candidates", "order": "created_at.desc"},
    )
    if response.status_code != 200:
        raise reports.ReportStoreError(
            f"Could not read the reports ({response.status_code})"
        )
    return response.json()


def index_by_identity(rows: list[dict]) -> dict[tuple[str, str, str], str]:
    """(name_norm, day, venue_norm) -> source_url, newest report winning.

    Reports come back newest first and `setdefault` keeps the first seen, so a
    re-swept event resolves to the most recent page that listed it.
    """
    index: dict[tuple[str, str, str], str] = {}
    for report in rows:
        for candidate in report.get("candidates") or []:
            url = (candidate.get("source_url") or "").strip()
            draft = candidate.get("draft") or {}
            name, venue, start = (
                draft.get("name"),
                draft.get("venue"),
                draft.get("start_at"),
            )
            if not (url and name and venue and start):
                continue
            index.setdefault((norm(name), start[:10], norm(venue)), url)
    return index


def main() -> int:
    write = "--write" in sys.argv[1:]

    index = index_by_identity(fetch_all_reports())
    print(f"{len(index)} candidate(s) with a source URL across all reports.\n")

    with open_session(write) as session:
        events = [dict(r) for r in session.run(UNSOURCED)]
        if not events:
            print("Every discovered event already names its source.")
            return 0

        updates, unmatched = [], []
        for event in events:
            url = index.get(
                (event["name_norm"], event["day"], event["venue_norm"] or "")
            )
            if not url:
                unmatched.append(event)
                continue
            updates.append(
                {
                    "uid": event["uid"],
                    "source_url": url,
                    "source_domain": source_domain(url),
                }
            )
            print(
                f"  {event['day']}  {(event['name'] or '')[:38]:<38} {source_domain(url)}"
            )

        for event in unmatched:
            print(f"  NO REPORT  {event['day']}  {(event['name'] or '')[:38]}")

        if not write:
            print(
                f"\nDry run. {len(updates)} event(s) would be stamped, "
                f"{len(unmatched)} have no surviving report; pass --write."
            )
            return 0

        record = session.run(STAMP, rows=updates).single()
        print(f"\nStamped {record['stamped']} event(s).")
        if unmatched:
            print(f"{len(unmatched)} left without a source — no surviving report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
