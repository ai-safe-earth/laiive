from laiive_shared.cards import EventDraft, missing_required
from laiive_shared.geocode import GeocodeResult, NominatimGeocoder
from laiive_shared.neo4j_writer import (
    has_explicit_time,
    parse_start_at,
    resolve_timezone,
    tag_artist_genres,
    write_event,
)


class FakeResult:
    def __init__(self, single=None, rows=None):
        self._single = single
        self._rows = rows or []

    def single(self):
        return self._single

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    """Answers the venue-by-uid resolve, the dedup probe, the write, and the
    backfill queries in order."""

    def __init__(self, dedup_hit=None, venue_node=None):
        self.queries: list[tuple[str, dict]] = []
        self._dedup_hit = dedup_hit
        self._venue_node = venue_node

    def run(self, query, **params):
        self.queries.append((query, params))
        if "MATCH (v:Venue {uid: $uid})" in query:
            return FakeResult(single=self._venue_node)
        if "RETURN e.uid AS uid, e.name AS name LIMIT 1" in query:
            return FakeResult(single=self._dedup_hit)
        if "CREATE (e:Event" in query:
            return FakeResult(
                single={
                    "uid": params["event_uid"],
                    "name": params["name"],
                    "venue": params["venue"],
                    "city": params["city"],
                }
            )
        if "MERGE (a)-[:HAS_GENRE]->(g)" in query:
            return FakeResult(single={"tagged": len(params["rows"])})
        return FakeResult(rows=[])  # backfill selects — nothing to embed


class DictStore:
    """In-memory GeocodeStore: no file, no Redis, no rate gate."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        return (key in self.data, self.data.get(key))

    def set(self, key, value):
        self.data[key] = value

    def acquire_slot(self):
        return None


class FakeGeocoder(NominatimGeocoder):
    """The real geocoder with only the network swapped out.

    Subclassed rather than duck-typed on purpose: the form ordering and the
    plausibility rejection are what the writer depends on, so the tests should
    exercise the production implementations, not a parallel copy of them.
    """

    def __init__(self, results):
        super().__init__(store=DictStore())
        self._results = results
        self.calls = []

    def geocode(self, query):
        self.calls.append(query)
        return self._results.get(query)


DRAFT = EventDraft(
    artists=["Ana Beck Quartet"],
    start_at="2026-09-01T20:00:00",
    venue="Quasimodo",
    address="Kantstraße 12a",
    city="Berlin",
    price_min=22.0,
    genre="Jazz",
)


SWEPT = EventDraft(
    name="Jazz Night",
    start_at="2026-09-01T20:00:00",
    venue="Quasimodo",
    city="Berlin",
)


def test_invalid_draft_lists_missing_fields():
    result = write_event(
        FakeSession(), EventDraft(artists=["X"]), source="pro_submission"
    )
    assert result.status == "invalid"
    assert set(result.missing) == {
        "start_at",
        "venue",
        "address",
        "city",
        "price_min",
    }


def test_admin_search_does_not_require_an_address():
    """Promoters know the street; a swept listing usually does not state one,
    so requiring it there would reject most of the discovery pipeline."""
    result = write_event(
        FakeSession(),
        EventDraft(
            name="Night", start_at="2026-09-01T20:00:00", venue="V", city="Berlin"
        ),
        source="admin_search",
    )
    assert result.status == "created"


def test_admin_search_requires_name_not_artists_or_price():
    """Internet listings rarely state lineup or price (D13): discovery drafts
    write with just name + date + venue + city; a nameless one is refused."""
    listing = EventDraft(
        name="Barcelona Rock Fest",
        start_at="2026-10-08T19:00:00",
        venue="Poble Espanyol",
        city="Barcelona",
    )
    result = write_event(FakeSession(), listing, source="admin_search")
    assert result.status == "created"

    nameless = listing.model_copy(update={"name": None})
    result = write_event(FakeSession(), nameless, source="admin_search")
    assert result.status == "invalid"
    assert result.missing == ["name"]


def test_unparseable_date_is_invalid():
    draft = DRAFT.model_copy(update={"start_at": "next full moon"})
    result = write_event(FakeSession(), draft, source="pro_submission")
    assert result.status == "invalid"
    assert result.missing == ["start_at"]


def test_duplicate_probe_short_circuits():
    session = FakeSession(dedup_hit={"uid": "existing-uid", "name": "Ana Beck Quartet"})
    result = write_event(session, DRAFT.model_copy(), source="pro_submission")
    assert result.status == "duplicate"
    assert result.uid == "existing-uid"
    assert len(session.queries) == 1  # nothing written


def test_created_event_carries_identity_and_provenance():
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Quasimodo, Berlin": GeocodeResult(
                lat=52.5058, lng=13.323, country_code="DE", display_name="Quasimodo"
            ),
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            ),
        }
    )
    result = write_event(
        session,
        DRAFT.model_copy(),
        source="pro_submission",
        owner_id="user-123",
        geocoder=geocoder,
    )
    assert result.status == "created"
    assert result.warnings == []

    write_params = session.queries[1][1]
    assert write_params["name"] == "Ana Beck Quartet live at Quasimodo"
    assert write_params["name_norm"] == "ana beck quartet live at quasimodo"
    assert write_params["country_code"] == "DE"
    assert write_params["venue_lat"] == 52.5058
    assert write_params["genre"] == "jazz"
    assert write_params["genre_name"] == "Jazz"
    assert write_params["owner_id"] == "user-123"
    assert write_params["source"] == "pro_submission"
    assert write_params["price_max"] == 22.0  # defaults to price_min
    assert write_params["artists"][0]["name_norm"] == "ana beck quartet"


PICKED_NODE = {
    "name": "Quasimodo",
    "name_norm": "quasimodo",
    "address": "Kantstra\u00dfe 12a",
    "lat": 52.5058,
    "lng": 13.323,
    "city": "Berlin",
    "country_code": "DE",
}


def test_a_picked_venue_skips_the_geocoder_and_keeps_the_nodes_identity():
    """venue_uid resolves the node first: the graph's name, city and pin win
    over whatever was typed, and a submission at a known venue costs zero
    Nominatim round-trips."""
    session = FakeSession(venue_node=PICKED_NODE)
    geocoder = FakeGeocoder({})
    draft = DRAFT.model_copy(
        update={"venue": "quasimodo berlin", "address": None, "city": None}
    )
    result = write_event(
        session, draft, source="pro_submission", geocoder=geocoder, venue_uid="v-1"
    )
    assert result.status == "created"
    assert geocoder.calls == []

    probe_params = session.queries[1][1]
    assert probe_params["venue_norm"] == "quasimodo"

    write_query, write_params = session.queries[2]
    assert "MATCH (v:Venue {uid: $picked_uid})" in write_query
    assert "coalesce(v.address" in write_query
    # One row however many LOCATED_IN edges the node has grown — without the
    # cap the CREATE runs per row and dies on the event_uid constraint.
    assert "WITH v, c LIMIT 1" in write_query
    assert write_params["picked_uid"] == "v-1"
    assert write_params["venue"] == "Quasimodo"
    assert write_params["country_code"] == "DE"


def test_a_picked_venues_own_address_reaches_the_geocoder():
    """A node with a street but no pin (a geocoder miss at write time) must be
    pinned via that street, not name-only — the form deliberately sends no
    draft address when the venue has one on file."""
    node = dict(PICKED_NODE, lat=None, lng=None)
    session = FakeSession(venue_node=node)
    geocoder = FakeGeocoder(
        {
            # Only the full form answers, so a name-only lookup would miss and
            # coalesce a city centroid onto the shared node forever.
            "Quasimodo, Kantstra\u00dfe 12a, Berlin": GeocodeResult(
                lat=52.5058, lng=13.323, country_code="DE", display_name="Quasimodo"
            ),
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            ),
        }
    )
    draft = DRAFT.model_copy(update={"address": None})
    result = write_event(
        session, draft, source="pro_submission", geocoder=geocoder, venue_uid="v-1"
    )
    assert result.status == "created"
    assert "Quasimodo, Kantstra\u00dfe 12a, Berlin" in geocoder.calls
    write_params = session.queries[2][1]
    assert write_params["venue_lat"] == 52.5058
    assert write_params["geocode_precision"] == "venue"


def test_an_unknown_venue_uid_dies_on_the_match_not_as_a_new_venue():
    """An invented uid (a model can invent a draft field, and the walk
    round-trips drafts through one) must refuse, never fork a venue."""
    session = FakeSession(venue_node=None)
    result = write_event(
        session, DRAFT.model_copy(), source="pro_submission", venue_uid="made-up"
    )
    assert result.status == "invalid"
    assert result.missing == ["venue_uid"]
    assert len(session.queries) == 1  # nothing probed, nothing written


def test_a_picked_venue_without_an_address_still_demands_one():
    node = dict(PICKED_NODE, address=None, lat=None, lng=None)
    session = FakeSession(venue_node=node)
    draft = DRAFT.model_copy(update={"address": None})
    result = write_event(session, draft, source="pro_submission", venue_uid="v-1")
    assert result.status == "invalid"
    assert result.missing == ["address"]


def test_a_missing_address_on_a_picked_venue_is_completed_set_if_absent():
    """The promoter's address fills the hole and earns the venue its pin —
    completing the record, never overwriting it (coalesce on every field)."""
    node = dict(PICKED_NODE, address=None, lat=None, lng=None)
    session = FakeSession(venue_node=node)
    geocoder = FakeGeocoder(
        {
            "Quasimodo, Berlin": GeocodeResult(
                lat=52.5058, lng=13.323, country_code="DE", display_name="Quasimodo"
            ),
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            ),
        }
    )
    result = write_event(
        session,
        DRAFT.model_copy(),
        source="pro_submission",
        geocoder=geocoder,
        venue_uid="v-1",
    )
    assert result.status == "created"
    assert geocoder.calls  # this time the pin had to be earned

    write_query, write_params = session.queries[2]
    assert "coalesce(v.location" in write_query
    assert write_params["address"] == DRAFT.address
    assert write_params["venue_lat"] == 52.5058
    assert write_params["geocode_precision"] == "venue"


def test_missing_required_waives_what_a_picked_venue_brings():
    draft = EventDraft(artists=["X"], start_at="2026-09-01T20:00:00", price_min=10.0)
    assert missing_required(draft) == ["venue", "address", "city"]
    assert missing_required(draft, venue_known=True) == []


def test_geocode_miss_falls_back_to_city_and_warns():
    geocoder = FakeGeocoder(
        {
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            )
        }
    )
    result = write_event(
        FakeSession(), DRAFT.model_copy(), source="pro_submission", geocoder=geocoder
    )
    assert result.status == "created"
    assert any("city centroid" in w for w in result.warnings)


def test_venue_lookup_tries_short_form_before_the_full_address():
    """The long join scored 0% against Nominatim; the short form is tried first."""
    geocoder = FakeGeocoder(
        {
            "Quasimodo, Berlin": GeocodeResult(
                lat=52.5058, lng=13.323, country_code="DE", display_name="Quasimodo"
            ),
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            ),
        }
    )
    write_event(
        FakeSession(), DRAFT.model_copy(), source="pro_submission", geocoder=geocoder
    )
    assert geocoder.calls == ["Berlin", "Quasimodo, Berlin"]


def test_venue_lookup_falls_back_to_the_full_address():
    """A venue the short form cannot find still resolves via the full string."""
    geocoder = FakeGeocoder(
        {
            "Quasimodo, Kantstraße 12a, Berlin": GeocodeResult(
                lat=52.5058, lng=13.323, country_code="DE", display_name="Quasimodo"
            ),
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            ),
        }
    )
    result = write_event(
        FakeSession(), DRAFT.model_copy(), source="pro_submission", geocoder=geocoder
    )
    assert result.warnings == []
    assert geocoder.calls == [
        "Berlin",
        "Quasimodo, Berlin",
        "Kantstraße 12a, Berlin",  # bare street is ambiguous; city appended
        "Quasimodo, Kantstraße 12a, Berlin",
    ]


def test_address_already_carrying_the_city_is_not_doubled():
    """Sweep-extracted addresses end with the city; appending it again is the
    exact shape that scored 0% against Nominatim."""
    draft = DRAFT.model_copy(update={"address": "Av. Felipe II, 28009 Berlin, Spain"})
    geocoder = FakeGeocoder(
        {
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            )
        }
    )
    write_event(FakeSession(), draft, source="pro_submission", geocoder=geocoder)
    assert "Av. Felipe II, 28009 Berlin, Spain" in geocoder.calls
    assert "Av. Felipe II, 28009 Berlin, Spain, Berlin" not in geocoder.calls


def test_venue_geocoded_to_another_region_is_rejected():
    """A wrong hit is worse than a miss — it would be written with no warning."""
    geocoder = FakeGeocoder(
        {
            # Nominatim answers "oasys, barcelona" with a theme park in Almería.
            "Quasimodo, Berlin": GeocodeResult(
                lat=48.1372, lng=11.5756, country_code="DE", display_name="München"
            ),
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            ),
        }
    )
    session = FakeSession()
    result = write_event(
        session, DRAFT.model_copy(), source="pro_submission", geocoder=geocoder
    )
    assert any("city centroid" in w for w in result.warnings)
    # the Munich coordinate is discarded, not written
    assert session.queries[1][1]["venue_lat"] == 52.52


def test_no_geocoder_still_writes_with_warning():
    result = write_event(FakeSession(), DRAFT.model_copy(), source="seed")
    assert result.status == "created"
    assert any("nearby search" in w for w in result.warnings)


def test_parse_start_at_formats():
    assert parse_start_at("2026-09-01T20:00:00").hour == 20
    assert parse_start_at("2026-09-01 20:00").day == 1
    assert parse_start_at("01/09/2026 20:00").month == 9
    assert parse_start_at("2026-09-01").year == 2026
    assert parse_start_at("whenever") is None
    assert parse_start_at("") is None


def test_address_resolver_is_the_last_resort_and_is_cached():
    """Only consulted after every name form misses, and only once per venue.

    A lookup is a web search plus an LLM call, so a second write for the same
    unresolvable venue must not pay for it again.
    """
    geocoder = FakeGeocoder(
        {
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            ),
            "Kantstrasse 12a, Berlin": GeocodeResult(
                lat=52.5058, lng=13.323, country_code="DE", display_name="Quasimodo"
            ),
        }
    )
    calls = []

    def resolver(venue, city):
        calls.append((venue, city))
        return "Kantstrasse 12a"

    # admin_search, not pro_submission: a promoter must supply an address now,
    # so the resolver only ever runs for swept listings -- which is also the
    # only service it is wired into.
    draft = SWEPT.model_copy()
    for _ in range(2):
        result = write_event(
            FakeSession(),
            draft.model_copy(),
            source="admin_search",
            geocoder=geocoder,
            address_resolver=resolver,
        )
        assert result.warnings == []
    assert calls == [("Quasimodo", "Berlin")]


def test_address_resolver_failure_falls_back_to_the_city_centroid():
    geocoder = FakeGeocoder(
        {
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            )
        }
    )

    def resolver(venue, city):
        raise RuntimeError("tavily down")

    result = write_event(
        FakeSession(),
        SWEPT.model_copy(),
        source="admin_search",
        geocoder=geocoder,
        address_resolver=resolver,
    )
    assert result.status == "created"
    assert any("city centroid" in w for w in result.warnings)


class TestTagArtistGenres:
    """Tagging an artist reaches every event they play, past and future."""

    def test_untagged_artists_are_tagged(self):
        session = FakeSession()
        tagged = tag_artist_genres(
            session, {"Placebo": "Alternative Rock", "Yandel": "reggaeton"}
        )
        assert tagged == 2
        rows = session.queries[-1][1]["rows"]
        assert {r["genre"] for r in rows} == {"alternative-rock", "reggaeton"}
        # The Genre MERGE has to match write_event's, or the same genre ends up
        # as two nodes: same slug key, same title-cased name on create.
        assert {r["name"] for r in rows} == {"Alternative Rock", "Reggaeton"}

    def test_an_artist_that_already_has_a_genre_is_left_alone(self):
        """A human correction must survive a re-run of the tagging script."""
        session = FakeSession()
        tag_artist_genres(session, {"Klangfeld": "pop"})
        assert (
            "WHERE NOT EXISTS { (a)-[:HAS_GENRE]->(:Genre) }" in session.queries[-1][0]
        )

    def test_nothing_to_tag_is_not_a_query(self):
        session = FakeSession()
        assert tag_artist_genres(session, {}) == 0
        assert session.queries == []


class TestStartTimeKnown:
    """A date-only listing must not claim the concert starts at midnight.

    30 of 57 discovered events sat at exactly 00:00 because the page gave a
    day and nothing else, and the card printed it as a start time.
    """

    def test_a_stated_time_is_recorded_as_known(self):
        for raw in ("2026-08-29T20:00:00", "2026-08-29 20:00", "29/08/2026 21.30"):
            assert has_explicit_time(raw) is True

    def test_a_date_alone_is_not_a_time(self):
        for raw in ("2026-08-29", "29/08/2026", ""):
            assert has_explicit_time(raw) is False

    def test_the_flag_is_read_from_the_text_not_the_datetime(self):
        """Once parsed, a defaulted midnight and a real one look identical."""
        assert has_explicit_time("2026-08-29T00:00:00") is True
        assert has_explicit_time("2026-08-29") is False

    def test_the_written_event_carries_it(self):
        session = FakeSession()
        draft = EventDraft(
            name="Date-only listing",
            artists=["Klangfeld"],
            start_at="2026-08-29",
            venue="Berghain",
            address="Am Wriezener Bahnhof",
            city="Berlin",
            price_min=0,
        )
        write_event(session, draft, source="admin_search")
        create = next(p for q, p in session.queries if "CREATE (e:Event" in q)
        assert create["start_time_known"] is False


def test_resolve_timezone_reads_the_zone_off_the_coordinate():
    """The country code is not a substitute: Spain spans two zones, and the
    graph already holds Spanish events."""
    assert resolve_timezone(52.5058, 13.323) == "Europe/Berlin"
    assert resolve_timezone(45.695, 9.67) == "Europe/Rome"
    # Both Spain. A country -> zone table gets the second one wrong by an hour.
    assert resolve_timezone(41.3874, 2.1686) == "Europe/Madrid"
    assert resolve_timezone(28.1235, -15.4363) == "Atlantic/Canary"
    assert resolve_timezone(None, None) is None


def test_start_time_is_read_in_the_venues_zone_not_as_utc():
    """A draft states a wall-clock time and no zone. Reading "22:00" as UTC
    moved a Bergamo gig to midnight the next day; it has to be read at the
    door. Regression for the 41 events written before this."""
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Druso, Bergamo": GeocodeResult(
                lat=45.695, lng=9.67, country_code="IT", display_name="Druso"
            ),
            "Bergamo": GeocodeResult(
                lat=45.6983, lng=9.6773, country_code="IT", display_name="Bergamo"
            ),
        }
    )
    result = write_event(
        session,
        EventDraft(
            artists=["BobSin"],
            start_at="2026-08-22T22:00:00",
            venue="Druso",
            address="Via Portico 71",
            city="Bergamo",
            price_min=5.0,
        ),
        source="pro_submission",
        geocoder=geocoder,
    )
    assert result.status == "created"

    write_params = session.queries[1][1]
    # 22:00 at the door in Bergamo, which is 20:00 UTC in August — not 22:00Z.
    assert write_params["start_at"] == "2026-08-22T22:00:00+02:00"
    assert write_params["timezone"] == "Europe/Rome"


def test_a_draft_that_states_its_offset_keeps_its_instant():
    """fromisoformat keeps an explicit offset, and replace() on an aware value
    would relabel the digits into the venue zone and shift the instant: a
    19:00+00:00 Rome show would store as 19:00+02:00 = 17:00 UTC, two hours
    early. A stated instant is kept and only re-expressed at the door."""
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Druso, Bergamo": GeocodeResult(
                lat=45.695, lng=9.67, country_code="IT", display_name="Druso"
            ),
            "Bergamo": GeocodeResult(
                lat=45.6983, lng=9.6773, country_code="IT", display_name="Bergamo"
            ),
        }
    )
    result = write_event(
        session,
        EventDraft(
            artists=["BobSin"],
            start_at="2026-08-28T19:00:00+00:00",
            venue="Druso",
            address="Via Portico 71",
            city="Bergamo",
            price_min=5.0,
        ),
        source="pro_submission",
        geocoder=geocoder,
    )
    assert result.status == "created"

    write_params = session.queries[1][1]
    # 19:00 UTC is 21:00 at the door in August Rome — the same instant.
    assert write_params["start_at"] == "2026-08-28T21:00:00+02:00"
    assert write_params["timezone"] == "Europe/Rome"


def test_zone_is_resolved_from_the_city_when_the_venue_is_not_found():
    """The venue falls back to the city centroid, and the zone follows that
    pin — a centroid is imprecise about the street, not about the hour."""
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            )
        }
    )
    result = write_event(
        session, DRAFT.model_copy(), source="pro_submission", geocoder=geocoder
    )
    assert result.status == "created"
    write_params = session.queries[1][1]
    assert write_params["timezone"] == "Europe/Berlin"
    assert write_params["start_at"] == "2026-09-01T20:00:00+02:00"


def test_no_coordinate_keeps_utc_and_says_so():
    """A geocoder outage must not stop submissions, but it must not quietly
    invent an instant either: the row keeps the old UTC reading and carries an
    empty zone so the backfill can find it."""
    session = FakeSession()
    result = write_event(session, DRAFT.model_copy(), source="pro_submission")
    assert result.status == "created"
    write_params = session.queries[1][1]
    assert write_params["start_at"] == "2026-09-01T20:00:00"
    assert write_params["timezone"] == ""
    assert any("timezone" in w for w in result.warnings)


def test_date_only_draft_is_localised_too_but_stays_flagged_unknown():
    """Midnight from a date-only listing is a placeholder, so the card must
    still hide the hour — but the date it prints is the local one."""
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            )
        }
    )
    result = write_event(
        session,
        SWEPT.model_copy(update={"start_at": "2026-09-01"}),
        source="admin_search",
        geocoder=geocoder,
    )
    assert result.status == "created"
    write_params = session.queries[1][1]
    assert write_params["start_at"] == "2026-09-01T00:00:00+02:00"
    assert write_params["start_time_known"] is False


def test_source_domain_groups_one_site_under_one_key():
    from laiive_shared.normalize import source_domain

    assert source_domain("https://www.ecodibergamo.it/agenda/x") == "ecodibergamo.it"
    # The same site, two spellings. Counted apart, each would carry half the
    # evidence and neither would ever clear a promotion threshold.
    assert source_domain("https://ecodibergamo.it/agenda/x") == "ecodibergamo.it"
    assert source_domain("HTTPS://WWW.EcoDiBergamo.IT/x") == "ecodibergamo.it"
    assert source_domain("") == ""
    assert source_domain("not a url") == ""


def test_a_discovered_event_records_the_page_it_came_from():
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Berlin": GeocodeResult(
                lat=52.52, lng=13.405, country_code="DE", display_name="Berlin"
            )
        }
    )
    result = write_event(
        session,
        SWEPT.model_copy(),
        source="admin_search",
        geocoder=geocoder,
        source_url="https://www.ecodibergamo.it/agenda/bobsin",
    )
    assert result.status == "created"
    write_params = session.queries[1][1]
    assert write_params["source_url"] == "https://www.ecodibergamo.it/agenda/bobsin"
    assert write_params["source_domain"] == "ecodibergamo.it"


def test_a_promoter_submission_has_no_source_page():
    """Nobody searched for it, so there is no page to name — and the card must
    not imply one."""
    session = FakeSession()
    result = write_event(session, DRAFT.model_copy(), source="pro_submission")
    assert result.status == "created"
    write_params = session.queries[1][1]
    assert write_params["source_url"] == ""
    assert write_params["source_domain"] == ""


def test_a_province_suffix_does_not_create_a_second_city():
    """The graph holds both "Bergamo" and "ponteranica, BG" today. City
    identity is (name_norm, country_code), so a suffixed spelling is a city
    nobody searches for, holding events the plain name never returns."""
    from laiive_shared.normalize import clean_city_name

    assert clean_city_name("Ponteranica, BG") == "Ponteranica"
    assert clean_city_name("Ponteranica (BG)") == "Ponteranica"
    assert clean_city_name("ponteranica,BG") == "ponteranica"
    # Left alone: a real name, a lowercase word, and a longer code.
    assert clean_city_name("Sant Feliu de Guíxols") == "Sant Feliu de Guíxols"
    assert clean_city_name("Frankfurt am Main") == "Frankfurt am Main"
    assert clean_city_name("Bergamo") == "Bergamo"
    assert clean_city_name("Torino, ITA") == "Torino, ITA"
    assert clean_city_name("") == ""


def test_the_writer_strips_the_suffix_before_it_becomes_a_merge_key():
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Ponteranica": GeocodeResult(
                lat=45.73, lng=9.65, country_code="IT", display_name="Ponteranica"
            )
        }
    )
    result = write_event(
        session,
        EventDraft(
            name="bimbo Funk",
            start_at="2026-09-19T20:00:00",
            venue="la casa delle finestre azurre",
            city="ponteranica, BG",
        ),
        source="admin_search",
        geocoder=geocoder,
    )
    assert result.status == "created"
    write_params = session.queries[1][1]
    assert write_params["city"] == "ponteranica"
    assert write_params["city_norm"] == "ponteranica"
    # The geocoder is asked for the town, not the town-plus-code string.
    assert "Ponteranica" in geocoder.calls or "ponteranica" in geocoder.calls


def test_an_exonym_does_not_become_a_second_city():
    """A real Torino sweep returned eight candidates saying "Torino" and seven
    saying "Turin". City identity is (name_norm, country_code), so approving
    that report unfixed is two cities and a search that finds half its events.
    The geocoder answers in the local language, so it settles the spelling."""
    session = FakeSession()
    geocoder = FakeGeocoder(
        {
            "Turin": GeocodeResult(
                lat=45.0703,
                lng=7.6869,
                country_code="IT",
                display_name="Torino, Piemonte, Italia",
            )
        }
    )
    result = write_event(
        session,
        EventDraft(
            name="The Night of Hits",
            start_at="2026-09-11T21:00:00",
            venue="Teatro Regio",
            city="Turin",
        ),
        source="admin_search",
        geocoder=geocoder,
    )
    assert result.status == "created"
    write_params = session.queries[1][1]
    assert write_params["city"] == "Torino"
    assert write_params["city_norm"] == "torino"


def test_canonical_city_name_keeps_what_it_cannot_improve():
    from laiive_shared.normalize import canonical_city_name

    assert canonical_city_name("Torino, Piemonte, Italia") == "Torino"
    assert canonical_city_name("München, Bayern, Deutschland") == "München"
    assert canonical_city_name("Bergamo, Lombardia, Italia") == "Bergamo"
    # An address, not a place — renaming a city after a house number would be
    # worse than the split it is meant to fix.
    assert canonical_city_name("12, Kantstraße, Berlin") == ""
    assert canonical_city_name("") == ""


def test_no_geocoder_leaves_the_city_as_written():
    """The canonicalisation is the geocoder's answer, so without one the draft
    is all there is — and a write must still go through."""
    session = FakeSession()
    result = write_event(
        session,
        SWEPT.model_copy(update={"city": "Turin"}),
        source="admin_search",
    )
    assert result.status == "created"
    assert session.queries[1][1]["city"] == "Turin"
