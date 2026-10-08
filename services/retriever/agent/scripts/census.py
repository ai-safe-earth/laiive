"""Read-only census of the live graph: is it reachable, and what can the chat answer?

Counts nodes, upcoming vs past events, upcoming events per city (all and the
next 14 days), events per source and upcoming events per genre. The session is
READ_ACCESS, so it cannot write. A paused Aura shows up as a DNS failure.

Run: cd services/retriever && uv run --no-sync python -m agent.scripts.census
"""

import time

from neo4j import READ_ACCESS, GraphDatabase

from config import settings

QUERIES = {
    "nodes by label": """
        MATCH (n) UNWIND labels(n) AS key RETURN key, count(*) AS n ORDER BY n DESC""",
    "events": """
        MATCH (e:Event)
        RETURN count(e) AS total,
               sum(CASE WHEN e.start_at >= datetime() THEN 1 ELSE 0 END) AS upcoming,
               toString(min(e.start_at)) AS earliest, toString(max(e.start_at)) AS latest""",
    "upcoming events by city": """
        MATCH (e:Event)-[:HOSTED_AT]->(:Venue)-[:LOCATED_IN]->(c:City)
        WHERE e.start_at >= datetime()
        RETURN c.name AS key, count(e) AS n ORDER BY n DESC LIMIT 15""",
    "next 14 days by city": """
        MATCH (e:Event)-[:HOSTED_AT]->(:Venue)-[:LOCATED_IN]->(c:City)
        WHERE e.start_at >= datetime() AND e.start_at < datetime() + duration('P14D')
        RETURN c.name AS key, count(e) AS n ORDER BY n DESC LIMIT 15""",
    "events by source": """
        MATCH (e:Event) RETURN coalesce(e.source, '(none)') AS key, count(*) AS n
        ORDER BY n DESC""",
    "upcoming events by genre": """
        MATCH (e:Event)-[:HAS_GENRE]->(g:Genre) WHERE e.start_at >= datetime()
        RETURN g.slug AS key, count(e) AS n ORDER BY n DESC LIMIT 10""",
}


def main() -> None:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=15,
    )
    # This machine's DNS flaps (docs/dev-box.md): retry the first contact.
    for attempt in range(1, 6):
        try:
            driver.verify_connectivity()
            break
        except Exception as e:  # noqa: BLE001 - report and retry any failure
            print(f"connect attempt {attempt} failed: {e}")
            if attempt == 5:
                raise SystemExit("graph unreachable (Aura paused?)") from e
            time.sleep(4)

    with driver.session(
        database=settings.neo4j_database, default_access_mode=READ_ACCESS
    ) as session:
        for title, cypher in QUERIES.items():
            print(f"\n== {title}")
            for record in session.run(cypher):
                row = dict(record)
                if set(row) == {"key", "n"}:
                    print(f"  {row['n']:>5}  {row['key']}")
                else:
                    print("  " + "  ".join(f"{k}={v}" for k, v in row.items()))
    driver.close()


if __name__ == "__main__":
    main()
