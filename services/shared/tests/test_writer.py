from laiive_shared.cards import EventDraft
from laiive_shared.geocode import GeocodeResult
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


class FakeGeocoder:
    def __init__(self, results):
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


def test_invalid_draft_lists_missing_fields():
    result = write_event(
        FakeSession(), EventDraft(artists=["X"]), source="pro_submission"
    )
    assert result.status == "invalid"
    assert set(result.missing) == {"start_at", "venue", "city", "price_min"}


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
            "Quasimodo, Kantstraße 12a, Berlin": GeocodeResult(
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
