"""Owner edits (Phase E): update_event / update_venue / update_artist.

PATCH semantics against the fake session from test_writer: only fields
present change, explicit None clears, identity fields are untouchable, and
a moved dedup key re-probes excluding the node itself.
"""

from laiive_shared.geocode import GeocodeResult
from laiive_shared.neo4j_writer import update_artist, update_event, update_venue

from tests.test_writer import FakeSession

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
    "cur_description": "",
    "cur_capacity": None,
    "cur_city": "Berlin",
}

ARTIST_NODE = {
    "cur_name": "Ana Beck Quartet",
    "cur_description": "",
    "cur_genres": ["jazz"],
}


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

    def test_noop_edit_changes_nothing(self):
        session = self._session()
        result = update_event(session, "e-1", {"price_min": 22.0})
        assert result.status == "updated"
        assert result.changed == {}
        assert len(session.queries) == 1  # the load, nothing else

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
        assert result.changed["location"]["new"] == {"lat": 52.501, "lng": 13.401}
        params = next(p for q, p in session.queries if "AS updated_uid" in q)
        assert params["geocode_precision"] == "venue"

    def test_geocode_miss_keeps_the_old_pin(self):
        session = FakeSession(update_node=dict(VENUE_NODE))
        result = update_venue(
            session, "v-1", {"address": "Nowhere 1"}, geocoder=_EditGeocoder()
        )
        assert result.status == "updated"
        assert "location" not in result.changed
        assert any("pin is unchanged" in w for w in result.warnings)
        set_query = next(q for q, _ in session.queries if "AS updated_uid" in q)
        assert "v.location" not in set_query
        assert "v.address" in set_query

    def test_capacity_is_a_plain_property(self):
        session = FakeSession(update_node=dict(VENUE_NODE))
        result = update_venue(session, "v-1", {"capacity": 350})
        assert result.changed == {"capacity": {"old": None, "new": 350}}
        assert not any("embedding = NULL" in q for q, _ in session.queries)

    def test_rename_is_refused(self):
        # name_norm is the MERGE identity; a rename is not a SET.
        result = update_venue(FakeSession(), "v-1", {"name": "New Name"})
        assert result.status == "invalid"


class TestUpdateArtist:
    def test_genres_replace_the_edges(self):
        session = FakeSession(update_node=dict(ARTIST_NODE))
        result = update_artist(session, "a-1", {"genres": ["Electronic", "Jazz"]})
        assert result.status == "updated"
        assert result.changed["genres"] == {
            "old": ["jazz"],
            "new": ["electronic", "jazz"],
        }
        replace = next(q for q, _ in session.queries if "FOREACH (tag IN $genres" in q)
        assert "DELETE r" in replace
        assert any("embedding = NULL" in q for q, _ in session.queries)

    def test_description_edit(self):
        session = FakeSession(update_node=dict(ARTIST_NODE))
        result = update_artist(session, "a-1", {"description": "Berlin quartet."})
        assert result.status == "updated"
        assert result.changed["description"]["new"] == "Berlin quartet."

    def test_rename_is_refused(self):
        result = update_artist(FakeSession(), "a-1", {"name": "New Name"})
        assert result.status == "invalid"
