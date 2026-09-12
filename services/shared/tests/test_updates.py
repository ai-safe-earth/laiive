"""Owner edits (Phase E): update_event / update_venue / update_artist.

PATCH semantics against the fake session from test_writer: only fields
present change, explicit None clears, identity fields are untouchable, a
moved dedup key re-probes excluding the node itself, and every bad input
comes back as a typed result — never a raise, never junk in the graph.
"""

import pytest

from laiive_shared.geocode import GeocodeResult
from laiive_shared.neo4j_writer import update_artist, update_event, update_venue

from tests.test_writer import FakeResult, FakeSession

EVENT_NODE = {
    "cur_name": "Jazz Night",
    "cur_start_at": "2026-09-01T20:00:00+02:00",
    "cur_timezone": "Europe/Berlin",
    "cur_price_min": 22.0,
    "cur_price_max": 28.0,
    "cur_price_currency": "EUR",
    "cur_description": "",
    "cur_ticket_url": "https://tix.example/1",
    "cur_status": "scheduled",
    "cur_venue_norm": "quasimodo",
    "cur_venue_lat": 52.52,
    "cur_venue_lng": 13.405,
    "cur_genres": ["jazz"],
}

VENUE_NODE = {
    "cur_name": "Quasimodo",
    "cur_venue_type": "club",
    "cur_address": "Kantstrasse 12a",
    "cur_description": None,
    "cur_capacity": None,
    "cur_city": "Berlin",
    "cur_lat": 52.52,
    "cur_lng": 13.405,
    "cur_precision": "venue",
}

ARTIST_NODE = {
    "cur_name": "Ana Beck Quartet",
    "cur_description": None,
    "cur_genres": ["jazz"],
}


class GoneOnWrite(FakeSession):
    """Node answers the load but is deleted before the SET lands."""

    def run(self, query, **params):
        if "AS updated_uid" in query:
            self.queries.append((query, params))
            return FakeResult(single=None)
        return super().run(query, **params)


class _EditGeocoder:
    """Duck-typed: update_venue only calls geocode and geocode_venue."""

    def __init__(self, venue_result=None):
        self.calls = []
        self._venue = venue_result
        self._city = GeocodeResult(
            lat=52.5, lng=13.4, country_code="DE", display_name="Berlin"
        )

    def geocode(self, query):
        return self._city

    def geocode_venue(self, name, address, city, near=None, address_resolver=None):
        self.calls.append((name, address, city, near))
        return self._venue


class TestUpdateEvent:
    def _session(self, **kw):
        return FakeSession(update_node=dict(EVENT_NODE), **kw)

    def test_unknown_field_is_refused(self):
        session = FakeSession()
        result = update_event(session, "e-1", {"artists": ["X"]})
        assert result.status == "invalid"
        assert "artists" in result.message
        assert len(session.queries) == 0  # refused before any read

    def test_missing_event_is_not_found(self):
        result = update_event(FakeSession(), "e-404", {"price_min": 10})
        assert result.status == "not_found"

    def test_deleted_mid_edit_is_not_found(self):
        session = GoneOnWrite(update_node=dict(EVENT_NODE))
        result = update_event(session, "e-1", {"price_min": 10})
        assert result.status == "not_found"

    def test_price_change_touches_neither_identity_nor_embedding(self):
        session = self._session()
        result = update_event(session, "e-1", {"price_min": 10})
        assert result.status == "updated"
        assert result.changed == {"price_min": {"old": 22.0, "new": 10.0}}
        texts = [q for q, _ in session.queries]
        assert not any("e.uid <> $uid" in q for q in texts)  # no re-probe
        assert not any("embedding = NULL" in q for q in texts)  # not text
        set_query = next(q for q in texts if "AS updated_uid" in q)
        assert "e.price_min" in set_query
        assert "name_norm" not in set_query

    def test_name_change_reprobes_excluding_itself(self):
        session = self._session()
        result = update_event(session, "e-1", {"name": "Jazz Night Special"})
        assert result.status == "updated"
        probe = next(q for q, _ in session.queries if "e.uid <> $uid" in q)
        assert "e.owner_id AS owner_id" in probe
        # name is in the composite text, so the vector must be invalidated
        assert any("embedding = NULL" in q for q, _ in session.queries)

    def test_name_change_landing_on_another_night_is_refused(self):
        session = self._session(
            dedup_hit={
                "uid": "other",
                "name": "Jazz Night Special",
                "owner_id": "u-9",
            }
        )
        result = update_event(session, "e-1", {"name": "Jazz Night Special"})
        assert result.status == "duplicate"
        assert not any("AS updated_uid" in q for q, _ in session.queries)

    def test_start_at_is_read_on_the_venues_clock(self):
        session = self._session()
        result = update_event(session, "e-1", {"start_at": "2026-09-01T22:00"})
        assert result.status == "updated"
        assert result.changed["start_at"]["new"] == "2026-09-01T22:00:00+02:00"
        params = next(p for q, p in session.queries if "AS updated_uid" in q)
        assert params["timezone"] == "Europe/Berlin"
        assert params["start_time_known"] is True

    def test_aware_start_at_keeps_its_instant(self):
        # The historical replace()-on-aware bug shifted stored instants; the
        # edit path re-expresses the stated instant on the venue's clock.
        result = update_event(
            self._session(), "e-1", {"start_at": "2026-09-01T19:00:00+00:00"}
        )
        assert result.changed["start_at"]["new"] == "2026-09-01T21:00:00+02:00"

    def test_status_is_whitelisted(self):
        refused = update_event(self._session(), "e-1", {"status": "deleted"})
        assert refused.status == "invalid"
        result = update_event(self._session(), "e-1", {"status": "cancelled"})
        assert result.changed == {"status": {"old": "scheduled", "new": "cancelled"}}

    def test_clearing_ticket_url_is_possible(self):
        # PATCH semantics: an explicit None clears. Adoption's empty-means-keep
        # coalesce must not apply to an owner's own edit.
        result = update_event(self._session(), "e-1", {"ticket_url": None})
        assert result.changed["ticket_url"] == {
            "old": "https://tix.example/1",
            "new": "",
        }

    def test_genre_edit_replaces_the_edge_in_the_same_query(self):
        session = self._session()
        result = update_event(session, "e-1", {"genre": "Rock"})
        assert result.status == "updated"
        assert result.changed["genre"] == {"old": "jazz", "new": "rock"}
        write = next(q for q, _ in session.queries if "AS updated_uid" in q)
        # one transaction: the SET, the edge DELETE and the re-link together
        assert "DELETE r" in write
        assert "MERGE (e)-[:HAS_GENRE]->(g)" in write
        assert any("embedding = NULL" in q for q, _ in session.queries)

    def test_genre_only_edit_still_detects_a_deleted_node(self):
        session = GoneOnWrite(update_node=dict(EVENT_NODE))
        result = update_event(session, "e-1", {"genre": "Rock"})
        assert result.status == "not_found"

    def test_a_filler_word_is_rejected_not_a_silent_clear(self):
        # genre_slug maps "live" to "" — that is a rejection, and it must not
        # delete the genre the event already has.
        result = update_event(self._session(), "e-1", {"genre": "Live"})
        assert result.status == "invalid"
        cleared = update_event(self._session(), "e-1", {"genre": None})
        assert cleared.status == "updated"
        assert cleared.changed["genre"] == {"old": "jazz", "new": ""}

    def test_noop_edit_changes_nothing(self):
        session = self._session()
        result = update_event(session, "e-1", {"price_min": 22.0})
        assert result.status == "updated"
        assert result.changed == {}
        assert len(session.queries) == 1  # the load, nothing else

    def test_noop_still_surfaces_warnings(self):
        node = dict(EVENT_NODE, cur_venue_lat=None, cur_venue_lng=None)
        session = FakeSession(update_node=node)
        result = update_event(session, "e-1", {"start_at": "2026-09-01T20:00:00+02:00"})
        assert result.status == "updated"
        assert result.changed == {}
        assert any("timezone" in w for w in result.warnings)

    @pytest.mark.parametrize(
        "fields",
        [
            {"name": 123},
            {"start_at": 123},
            {"genre": 5},
            {"description": 123},
            {"ticket_url": ["x"]},
            {"price_min": "nan"},
            {"price_min": True},
            {"price_currency": 3},
        ],
    )
    def test_bad_types_are_invalid_not_a_raise(self, fields):
        result = update_event(self._session(), "e-1", fields)
        assert result.status == "invalid"

    def test_embedding_is_nulled_before_the_scoped_backfill(self):
        session = self._session()
        embedded: list[list[str]] = []

        def embed(texts):
            embedded.append(texts)
            return [[0.1] * 8 for _ in texts]

        update_event(session, "e-1", {"name": "New Name"}, embed_texts=embed)
        texts = [q for q, _ in session.queries]
        null_at = next(i for i, q in enumerate(texts) if "embedding = NULL" in q)
        select_at = next(
            i
            for i, (q, p) in enumerate(session.queries)
            if "embedding IS NULL" in q and p.get("uids") == ["e-1"]
        )
        assert null_at < select_at  # the order the whole mechanism depends on

    def test_graph_failure_is_a_typed_error(self):
        class Flapping(FakeSession):
            def run(self, query, **params):
                raise RuntimeError("Unable to retrieve routing information")

        result = update_event(Flapping(), "e-1", {"price_min": 5})
        assert result.status == "error"


class TestUpdateVenue:
    def test_address_change_regeocodes_and_restamps(self):
        session = FakeSession(update_node=dict(VENUE_NODE))
        geo = _EditGeocoder(
            venue_result=GeocodeResult(
                lat=52.501, lng=13.401, country_code="DE", display_name="Quasimodo"
            )
        )
        result = update_venue(
            session, "v-1", {"address": "Kantstrasse 99"}, geocoder=geo
        )
        assert result.status == "updated"
        assert geo.calls and geo.calls[0][1] == "Kantstrasse 99"
        # the delta carries the writer's own reading of the old pin
        assert result.changed["location"] == {
            "old": {"lat": 52.52, "lng": 13.405},
            "new": {"lat": 52.501, "lng": 13.401},
        }
        assert result.changed["geocode_precision"] == {"old": "venue", "new": "venue"}
        params = next(p for q, p in session.queries if "AS updated_uid" in q)
        assert params["geocode_precision"] == "venue"

    def test_geocode_miss_unstamps_for_the_repair_sweep(self):
        session = FakeSession(update_node=dict(VENUE_NODE))
        result = update_venue(
            session, "v-1", {"address": "Nowhere 1"}, geocoder=_EditGeocoder()
        )
        assert result.status == "updated"
        assert "location" not in result.changed
        assert result.changed["geocode_precision"] == {"old": "venue", "new": None}
        assert any("repair sweep" in w for w in result.warnings)
        set_query = next(q for q, _ in session.queries if "AS updated_uid" in q)
        assert "v.location" not in set_query
        assert "geocode_checked_at = NULL" in set_query

    def test_no_geocoder_also_unstamps(self):
        # An address change with no geocoder wired must not keep a
        # venue-precision stamp for a pin the address no longer matches.
        session = FakeSession(update_node=dict(VENUE_NODE))
        result = update_venue(session, "v-1", {"address": "Kantstrasse 99"})
        assert result.changed["geocode_precision"] == {"old": "venue", "new": None}
        assert any("repair sweep" in w for w in result.warnings)

    def test_clearing_the_address_stores_null_not_empty_string(self):
        # write_event completes an absent address with coalesce(v.address, ..)
        # which treats "" as present — a clear must store NULL.
        session = FakeSession(update_node=dict(VENUE_NODE))
        result = update_venue(session, "v-1", {"address": None})
        assert result.changed["address"] == {"old": "Kantstrasse 12a", "new": None}
        params = next(p for q, p in session.queries if "AS updated_uid" in q)
        assert params["address"] is None

    def test_capacity_is_a_plain_property(self):
        session = FakeSession(update_node=dict(VENUE_NODE))
        result = update_venue(session, "v-1", {"capacity": 350})
        assert result.changed == {"capacity": {"old": None, "new": 350}}
        assert not any("embedding = NULL" in q for q, _ in session.queries)

    def test_empty_description_on_a_null_node_is_a_noop(self):
        # write_event never sets venue descriptions, so they read back NULL;
        # an untouched empty form field must not file a phantom delta.
        session = FakeSession(update_node=dict(VENUE_NODE))
        result = update_venue(session, "v-1", {"description": ""})
        assert result.status == "updated"
        assert result.changed == {}
        assert len(session.queries) == 1

    @pytest.mark.parametrize(
        "fields",
        [{"address": 123}, {"capacity": "many"}, {"capacity": True}, {"venue_type": 1}],
    )
    def test_bad_types_are_invalid_not_a_raise(self, fields):
        session = FakeSession(update_node=dict(VENUE_NODE))
        assert update_venue(session, "v-1", fields).status == "invalid"

    def test_rename_is_refused(self):
        # name_norm is the MERGE identity; a rename is not a SET.
        result = update_venue(FakeSession(), "v-1", {"name": "New Name"})
        assert result.status == "invalid"


class TestUpdateArtist:
    def test_genres_replace_the_edges_in_the_same_query(self):
        session = FakeSession(update_node=dict(ARTIST_NODE))
        result = update_artist(session, "a-1", {"genres": ["Electronic", "Jazz"]})
        assert result.status == "updated"
        assert result.changed["genres"] == {
            "old": ["jazz"],
            "new": ["electronic", "jazz"],
        }
        write = next(q for q, _ in session.queries if "AS updated_uid" in q)
        assert "DELETE r" in write
        assert "FOREACH (tag IN $genres" in write
        assert any("embedding = NULL" in q for q, _ in session.queries)

    def test_a_string_for_genres_is_refused(self):
        # A bare string would iterate character by character and MERGE
        # one-letter Genre nodes into the graph.
        result = update_artist(
            FakeSession(update_node=dict(ARTIST_NODE)), "a-1", {"genres": "jazz"}
        )
        assert result.status == "invalid"

    def test_all_filler_words_refuse_rather_than_clear(self):
        result = update_artist(
            FakeSession(update_node=dict(ARTIST_NODE)), "a-1", {"genres": ["Various"]}
        )
        assert result.status == "invalid"
        cleared = update_artist(
            FakeSession(update_node=dict(ARTIST_NODE)), "a-1", {"genres": []}
        )
        assert cleared.status == "updated"
        assert cleared.changed["genres"] == {"old": ["jazz"], "new": []}

    def test_partial_recognition_warns_about_the_dropped_words(self):
        result = update_artist(
            FakeSession(update_node=dict(ARTIST_NODE)),
            "a-1",
            {"genres": ["Electronic", "Live"]},
        )
        assert result.status == "updated"
        assert result.changed["genres"]["new"] == ["electronic"]
        assert any("Live" in w for w in result.warnings)

    def test_description_edit(self):
        session = FakeSession(update_node=dict(ARTIST_NODE))
        result = update_artist(session, "a-1", {"description": "Berlin quartet."})
        assert result.status == "updated"
        assert result.changed["description"]["new"] == "Berlin quartet."

    @pytest.mark.parametrize("fields", [{"genres": [123]}, {"description": 5}])
    def test_bad_types_are_invalid_not_a_raise(self, fields):
        session = FakeSession(update_node=dict(ARTIST_NODE))
        assert update_artist(session, "a-1", fields).status == "invalid"

    def test_rename_is_refused(self):
        result = update_artist(FakeSession(), "a-1", {"name": "New Name"})
        assert result.status == "invalid"
