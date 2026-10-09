"""The one fake Neo4j session every service's tests replay the writer against.

It answers by matching on the RETURN columns of `neo4j_writer.py` (and search's
read-only probes), so it lives next to the writer: when a RETURN changes, this is
the one place to follow it. It used to be hand-copied into three conftests and
the copies drifted silently.
"""


class FakeResult:
    def __init__(self, single=None, rows=None):
        self._single = single
        self._rows = rows or []

    def single(self):
        return self._single

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    """Answers the venue-by-uid resolve, the dedup probe, the write, updates,
    search's probes and the backfill queries. Every knob is a public attribute
    so a test can set it on a session a fixture already built."""

    def __init__(
        self,
        dedup_hit=None,
        venue_node=None,
        artist_uids=None,
        update_node=None,
        vector_hit=None,
    ):
        self.queries: list[tuple[str, dict]] = []
        self.dedup_hit = dedup_hit
        self.venue_node = venue_node
        # Override what the write RETURNs for the event's artists. A uid the
        # writer did not propose is an artist that already existed and kept
        # its own, which is exactly what MERGE does.
        self.artist_uids = artist_uids
        # What an update's load-current-node query reads back (cur_* columns).
        self.update_node = update_node
        # search's advisory nearest-event probe.
        self.vector_hit = vector_hit

    def run(self, query, **params):
        self.queries.append((query, params))
        # The update branches come first: an update's venue load and SET both
        # contain "MATCH (v:Venue {uid: $uid})", which the resolve branch
        # below would otherwise swallow.
        if "AS cur_name" in query:  # an update's load of the current node
            return FakeResult(single=self.update_node)
        if "AS updated_uid" in query:  # an update's SET write
            return FakeResult(single={"updated_uid": params["uid"]})
        if "FOREACH (tag IN $genres" in query:  # genre replace on an artist
            return FakeResult(rows=[])
        if "MATCH (v:Venue {uid: $uid})" in query:
            return FakeResult(single=self.venue_node)
        # Two probes read the dedup hit and they are not the same query:
        # search's own advisory check and the writer's dedup, which also reads
        # owner_id to decide adoption. Matched on the columns rather than on the
        # whole RETURN line: adding one used to slip past these branches
        # silently, and the fake then answered the write with an empty row.
        if "RETURN e.uid AS uid, e.name AS name LIMIT 1" in query:
            return FakeResult(single=self.dedup_hit)
        if "e.owner_id AS owner_id" in query:
            return FakeResult(single=self.dedup_hit)
        if "db.index.vector.queryNodes" in query:
            return FakeResult(single=self.vector_hit)
        if "AS artist_uids" in query:  # the write, creating or adopting
            return FakeResult(
                single={
                    "uid": params["event_uid"],
                    "name": params["name"],
                    "venue": params["venue"],
                    "city": params["city"],
                    # What the real MERGE returns: a picked venue keeps its own
                    # uid, an unpicked one is created and carries the uuid this
                    # write proposed. The writer reads creation off that
                    # difference, so the fake has to reproduce it.
                    "venue_uid": params["picked_uid"] or params["venue_uid"],
                    # Every artist here is new, which is what MERGE does to a
                    # graph this fake starts empty.
                    "artist_uids": (
                        self.artist_uids
                        if self.artist_uids is not None
                        else [a["uid"] for a in params["artists"]]
                    ),
                }
            )
        if "MERGE (a)-[:HAS_GENRE]->(g)" in query:
            return FakeResult(single={"tagged": len(params["rows"])})
        if "RETURN 1" in query:  # search's readiness ping
            return FakeResult(single={"1": 1})
        return FakeResult(rows=[])  # backfill selects — nothing to embed

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None
