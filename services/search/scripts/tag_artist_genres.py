"""Give untagged artists a genre, so their events answer a genre query.

The retriever reaches a genre through the event's tag or through its artists.
Measured on the live graph: 13 of 43 artists carry neither, which leaves 14
events invisible to the most common query in the product even though all but
one of them is a single named artist the model knows cold.

Dry by default -- it prints what it would write and exits. `--write` performs
the Aura write, through laiive_shared's writer like everything else.

    cd services/search
    uv run --no-sync python scripts/tag_artist_genres.py
    uv run --no-sync python scripts/tag_artist_genres.py --write
"""

import sys
from pathlib import Path

# Scripts run from the service root ("uv run python scripts/x.py"), where only
# scripts/ is on sys.path -- so the service's own packages have to be added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import genre_lookup
from agent.graph import _driver
from config import settings
from neo4j import READ_ACCESS, WRITE_ACCESS
from laiive_shared.neo4j_writer import tag_artist_genres

UNTAGGED = """
MATCH (a:Artist)
WHERE NOT EXISTS { (a)-[:HAS_GENRE]->(:Genre) }
RETURN a.name AS name,
       size([(a)-[:PERFORMS_AT]->(e:Event) | e]) AS events
ORDER BY events DESC, name
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
        artists = [dict(r) for r in session.run(UNTAGGED)]
        if not artists:
            print("Every artist already carries a genre.")
            return 0

        print(f"{len(artists)} artists with no genre; asking the model.")
        resolved = genre_lookup.resolve_genres([a["name"] for a in artists])

        for artist in artists:
            genre = resolved.get(artist["name"])
            # An unrecognised artist is reported, not guessed at: the gap is
            # worth seeing, and a wrong genre would be written silently.
            print(
                f"  {artist['name'][:38]:<40}{genre or '-- not recognised':<20}"
                f"{artist['events']} event(s)"
            )

        if not write:
            print(f"\nDry run. {len(resolved)} would be tagged; pass --write to apply.")
            return 0

        tagged = tag_artist_genres(session, resolved)
        print(f"\nTagged {tagged} artist(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
