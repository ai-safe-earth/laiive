from laiive_shared.cards import EventDraft
from laiive_shared.geocode import GeocodeResult, NominatimGeocoder
from laiive_shared.neo4j_writer import parse_start_at, write_event


class FakeResult:
    def __init__(self, single=None, rows=None):
        self._single = single
        self._rows = rows or []

    def single(self):
        return self._single

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    """Answers the dedup probe, the write, and the backfill queries in order."""

    def __init__(self, dedup_hit=None):
        self.queries: list[tuple[str, dict]] = []
        self._dedup_hit = dedup_hit

    def run(self, query, **params):
        self.queries.append((query, params))
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
