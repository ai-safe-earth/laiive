"""Executor unit tests — query builders are pure functions, execution mocked."""

from unittest.mock import Mock

from agent.classifier import Constraints
from agent.executor import (
    Executor,
    build_bbox_query,
    build_nearby_query,
    build_template_query,
    build_vector_query,
    pad_bbox,
    flexible_rows_to_cards,
    rows_to_cards,
)
from agent.router import ExecutionPlan, PlanKind
from laiive_shared.geocode import GeocodeResult

STANDARD_ROW = {
    "uid": "e1",
    "name": "Klangfeld Nacht",
    "description": "hypnotic techno",
    "start_at": "2026-08-15T23:00:00+00:00",
    "price_min": 20.0,
    "price_max": 20.0,
    "price_currency": "EUR",
    "ticket_url": "https://tickets.example/1",
    "source": "seed",
    "venue": "Berghain",
    "venue_type": "club",
    "city": "Berlin",
    "lat": 52.5111,
    "lng": 13.4433,
    "artists": ["Klangfeld", "DJ Petra"],
}


class TestTemplateQuery:
    def test_city_and_genre_filters(self):
        cypher, params = build_template_query(
            Constraints(city="Café City", genre="jazz")
        )
        assert "c.name_norm = $city_norm" in cypher
        assert params["city_norm"] == "cafe city"  # normalized
        assert "HAS_GENRE" in cypher
        assert params["genres"] == ["jazz"]
        assert "e.status = 'scheduled'" in cypher
        assert "e.start_at >= datetime()" in cypher  # upcoming by default

    def test_date_range_replaces_default_upcoming(self):
        cypher, params = build_template_query(
            Constraints(
                city="Berlin",
                date_from="2026-09-01T00:00:00",
                date_to="2026-09-02T00:00:00",
            )
        )
        assert "localdatetime(e.start_at) >= localdatetime($date_from)" in cypher
        assert "localdatetime(e.start_at) < localdatetime($date_to)" in cypher
        assert "e.start_at >= datetime()" not in cypher

    def test_a_date_window_is_read_on_the_venues_clock(self):
        """A window is a wall-clock question. datetime() would read the naive
        bounds as UTC and compare them against a zoned instant, shifting every
        window by the venue's offset — a 19:00 Madrid gig fell out of
        "tonight" and 01:00 the next local morning fell in."""
        cypher, _ = build_template_query(
            Constraints(date_from="2026-08-22T18:00:00", date_to="2026-08-23T06:00:00")
        )
        # The zoned form must not survive on either bound. Checked as the
        # whole clause because "localdatetime($date_from)" contains
        # "datetime($date_from)" as a substring.
        assert "e.start_at >= datetime($date_from)" not in cypher
        assert "e.start_at < datetime($date_to)" not in cypher
        assert "localdatetime(e.start_at) >= localdatetime($date_from)" in cypher
        assert "localdatetime(e.start_at) < localdatetime($date_to)" in cypher

    def test_upcoming_default_stays_an_instant_comparison(self):
        """ "Still to come" is the same moment in every zone, so the default is
        the one clause that must NOT become a wall-clock comparison."""
        cypher, _ = build_template_query(Constraints(city="Berlin"))
        assert "e.start_at >= datetime()" in cypher
        assert "localdatetime" not in cypher

    def test_artist_venue_type_and_price(self):
        cypher, params = build_template_query(
            Constraints(artist="Niña de las Dunas", venue_type="club", price_max=20)
        )
        assert params["artist_norm"] == "nina de las dunas"
        assert "v.venue_type = $venue_type" in cypher
        assert "e.price_min <= $price_max" in cypher

    def test_country_filter(self):
        _, params = build_template_query(Constraints(country_code="es"))
        assert params["country_code"] == "ES"

    def test_values_never_inlined(self):
        cypher, _ = build_template_query(Constraints(city="Berlin'}) DETACH DELETE (e"))
        assert "DETACH" not in cypher  # values only travel as parameters


class TestNearbyQuery:
    def test_shape(self):
        cypher, params = build_nearby_query(
            Constraints(genre="techno"), 52.52, 13.405, 10.0
        )
        assert "point.distance" in cypher
        assert "v.location IS NOT NULL" in cypher
        assert "e.start_at >= datetime()" in cypher  # the missing filter, fixed
        assert "distance_m" in cypher
        assert params["radius_m"] == 10000


class TestVectorQuery:
    def test_shape(self):
        cypher, params = build_vector_query(
            Constraints(free_text="candle-lit jazz", city="Madrid")
        )
        assert "db.index.vector.queryNodes('event_embedding'" in cypher
        assert "score >= $threshold" in cypher
        assert "c.name_norm = $city_norm" in cypher


class TestCardMapping:
    def test_standard_row_to_card(self):
        card = rows_to_cards([dict(STANDARD_ROW, distance_m=365.0)])[0]
        assert card.uid == "e1"
        assert card.artists == ["Klangfeld", "DJ Petra"]
        assert card.lat == 52.5111
        assert card.distance_km == 0.36
        assert card.source == "seed"

    def test_flexible_mapping_of_llm_rows(self):
        rows = [
            {
                "event": {
                    "uid": "e9",
                    "name": "Jazz al Palau",
                    "start_at": "2026-09-01",
                },
                "venue_name": "Palau",
                "city": "Barcelona",
                "artists": "Marta Sánchez Trio",
            },
            {"no_name": True},  # unmappable row is skipped
        ]
        cards = flexible_rows_to_cards(rows)
        assert len(cards) == 1
        assert cards[0].name == "Jazz al Palau"
        assert cards[0].artists == ["Marta Sánchez Trio"]


class TestExecutorDispatch:
    def test_template_plan_executes_and_maps(self):
        neo4j = Mock()
        neo4j.execute_read.return_value = [STANDARD_ROW]
        executor = Executor(neo4j, embed_fn=Mock(), query_builder=Mock())
        outcome = executor.execute(
            ExecutionPlan(PlanKind.TEMPLATE, Constraints(city="Berlin"))
        )
        assert outcome.error is None
        assert outcome.cards[0].name == "Klangfeld Nacht"
        assert outcome.cypher is not None  # cypher always reported

    def test_vector_plan_embeds_free_text(self):
        neo4j = Mock()
        neo4j.execute_read.return_value = []
        embed = Mock(return_value=[0.1] * 1536)
        executor = Executor(neo4j, embed_fn=embed, query_builder=Mock())
        executor.execute(
            ExecutionPlan(PlanKind.VECTOR, Constraints(free_text="dreamy shoegaze"))
        )
        embed.assert_called_once_with("dreamy shoegaze")
        params = neo4j.execute_read.call_args[0][1]
        assert params["embedding"] == [0.1] * 1536

    def test_nearby_expands_radius_until_enough(self):
        from config import settings

        neo4j = Mock()
        neo4j.execute_read.side_effect = [
            [],
            [],
            [STANDARD_ROW] * settings.location_min_events,
        ]
        executor = Executor(neo4j, embed_fn=Mock(), query_builder=Mock())
        outcome = executor.execute(
            ExecutionPlan(PlanKind.NEARBY, Constraints(near_me=True)),
            location={"latitude": 52.52, "longitude": 13.405},
        )
        assert neo4j.execute_read.call_count == 3  # progressive radius steps
        assert len(outcome.cards) == settings.location_min_events

    def test_explicit_radius_no_expansion(self):
        neo4j = Mock()
        neo4j.execute_read.return_value = []
        executor = Executor(neo4j, embed_fn=Mock(), query_builder=Mock())
        executor.execute(
            ExecutionPlan(PlanKind.NEARBY, Constraints(near_me=True, radius_km=3.0)),
            location={"latitude": 52.52, "longitude": 13.405},
        )
        assert neo4j.execute_read.call_count == 1
        assert neo4j.execute_read.call_args[0][1]["radius_m"] == 3000.0


class TestGeocodePrecisionRanking:
    """Nearby search has to distrust the pins the repair sweep flagged.

    A 'suspect' location is one the backfill measured as being outside its own
    city — worse than no location, because it places the event confidently
    somewhere it is not. A 'city_centroid' one only means "somewhere in this
    city", so it stays findable but sorts behind anything actually located.
    """

    def build(self):
        return build_nearby_query(
            Constraints(near_me=True), lat=52.52, lng=13.405, radius_km=5.0
        )

    def test_suspect_locations_are_excluded(self):
        cypher, _ = self.build()
        assert "coalesce(v.geocode_precision, 'venue') <> 'suspect'" in cypher

    def test_rows_predating_the_flag_are_still_trusted(self):
        """A NULL precision is legacy data, not a known-bad pin."""
        cypher, _ = self.build()
        assert "coalesce(v.geocode_precision, 'venue')" in cypher

    def test_centroid_pins_are_penalised_in_the_sort_only(self):
        from config import settings

        cypher, params = self.build()
        assert (
            "ORDER BY distance_m + CASE WHEN v.geocode_precision = 'city_centroid'"
            in cypher
        )
        assert params["centroid_penalty_m"] == (
            settings.location_centroid_penalty_km * 1000
        )
        # the distance the card reports stays the true one
        assert ", distance_m" in cypher

    def test_template_and_vector_paths_neither_filter_nor_rank_on_it(self):
        """Only nearby ranks on location, so only nearby pays for the check.

        Both still *return* the flag — every card says how much its pin is
        worth — but neither hides a row or reorders one because of it.
        """
        for cypher, _ in (
            build_template_query(Constraints(city="Berlin")),
            build_vector_query(Constraints(free_text="loud")),
        ):
            assert "v.geocode_precision AS geocode_precision" in cypher
            assert "coalesce(v.geocode_precision" not in cypher
            assert "CASE WHEN v.geocode_precision" not in cypher


class TestNamedPlaceFallback:
    """A named place that is not a City node: "techno in Kreuzberg".

    The classifier has nowhere else to put a place name, so it arrives as
    `city` and matches no City node. Rather than answer nothing, the place is
    geocoded to a bounding box — but only after the ordinary template returned
    zero rows, so a real city with events never pays for the extra lookup.
    """

    KREUZBERG = GeocodeResult(
        lat=52.4979,
        lng=13.4184,
        country_code="DE",
        display_name="Friedrichshain-Kreuzberg, Berlin",
        bbox=(52.4823, 52.5170, 13.3823, 13.4657),
    )
    CATALONIA = GeocodeResult(
        lat=41.8,
        lng=1.5,
        country_code="ES",
        display_name="Catalunya, España",
        bbox=(40.5, 42.9, 0.15, 3.33),
    )

    def executor(self, rows, geocoder=None):
        neo4j = Mock()
        neo4j.execute_read.side_effect = rows
        ex = Executor(neo4j, embed_fn=Mock(), query_builder=Mock(), geocoder=geocoder)
        return ex, neo4j

    def run(self, ex, city="Kreuzberg", **kwargs):
        return ex.execute(
            ExecutionPlan(PlanKind.TEMPLATE, Constraints(city=city, **kwargs))
        )

    def test_zero_rows_for_a_place_are_retried_as_a_bbox(self):
        geocoder = Mock()
        geocoder.geocode.return_value = self.KREUZBERG
        ex, neo4j = self.executor([[], [STANDARD_ROW]], geocoder)
        outcome = self.run(ex)
        assert [c.name for c in outcome.cards] == ["Klangfeld Nacht"]
        geocoder.geocode.assert_called_once_with("Kreuzberg")
        params = neo4j.execute_read.call_args[0][1]
        assert (params["south"], params["north"]) == (52.4823, 52.5170)
        assert (params["west"], params["east"]) == (13.3823, 13.4657)

    def test_a_city_that_has_events_never_geocodes(self):
        """The happy path must stay free — this is the whole design constraint."""
        geocoder = Mock()
        ex, _ = self.executor([[STANDARD_ROW]], geocoder)
        outcome = self.run(ex, city="Berlin")
        assert len(outcome.cards) == 1
        geocoder.geocode.assert_not_called()

    def test_other_constraints_survive_the_retry(self):
        geocoder = Mock()
        geocoder.geocode.return_value = self.KREUZBERG
        ex, neo4j = self.executor([[], [STANDARD_ROW]], geocoder)
        self.run(ex, genre="techno")
        cypher, params = neo4j.execute_read.call_args[0]
        assert params["genres"] == ["techno"]
        assert "c.name_norm = $city_norm" not in cypher  # the box replaced it
        assert "city_norm" not in params

    def test_a_region_sized_box_is_refused(self):
        """ "in Catalonia" would box in the whole graph and filter nothing."""
        geocoder = Mock()
        geocoder.geocode.return_value = self.CATALONIA
        ex, neo4j = self.executor([[]], geocoder)
        outcome = self.run(ex, city="Catalonia")
        assert outcome.cards == []
        assert neo4j.execute_read.call_count == 1  # never retried

    def test_a_place_with_no_box_is_refused(self):
        geocoder = Mock()
        geocoder.geocode.return_value = GeocodeResult(1.0, 2.0, "DE", "somewhere")
        ex, neo4j = self.executor([[]], geocoder)
        assert self.run(ex).cards == []
        assert neo4j.execute_read.call_count == 1

    def test_an_unresolvable_place_keeps_the_empty_answer(self):
        geocoder = Mock()
        geocoder.geocode.return_value = None
        ex, _ = self.executor([[]], geocoder)
        outcome = self.run(ex, city="Nowheresville")
        assert outcome.cards == [] and outcome.error is None
        assert "c.name_norm = $city_norm" in outcome.cypher  # the template's

    def test_a_box_with_no_events_keeps_the_empty_answer(self):
        geocoder = Mock()
        geocoder.geocode.return_value = self.KREUZBERG
        ex, _ = self.executor([[], []], geocoder)
        outcome = self.run(ex)
        assert outcome.cards == []
        assert "c.name_norm = $city_norm" in outcome.cypher

    def test_without_a_geocoder_nothing_changes(self):
        ex, neo4j = self.executor([[]])
        assert self.run(ex).cards == []
        assert neo4j.execute_read.call_count == 1


class TestBboxQuery:
    def build(self, **kwargs):
        return build_bbox_query(
            Constraints(city="Kreuzberg", **kwargs), (52.48, 52.51, 13.38, 13.46)
        )

    def test_only_venue_precision_pins_are_inside_a_neighbourhood(self):
        """A centroid pin sits in whichever central district contains it.

        Ranking it down (what nearby does) is not enough here: "in Mitte" would
        list every un-located venue in Berlin, which is a wrong answer rather
        than an imprecise one.
        """
        cypher, _ = self.build()
        assert "coalesce(v.geocode_precision, 'venue') = 'venue'" in cypher
        assert "v.location IS NOT NULL" in cypher

    def test_the_box_is_a_filter_not_a_ranking(self):
        cypher, params = self.build()
        assert "v.location.latitude >= $south" in cypher
        assert "v.location.longitude <= $east" in cypher
        assert "ORDER BY start_at" in cypher  # date order, as the template
        assert params["south"] == 52.48 and params["east"] == 13.46


class TestPrecisionOnTheCard:
    """The card has to say how much its pin is worth, or the map overstates it."""

    def test_precision_travels_to_the_card(self):
        row = {**STANDARD_ROW, "geocode_precision": "city_centroid"}
        card = rows_to_cards([row])[0]
        assert card.geocode_precision == "city_centroid"
        assert (card.lat, card.lng) == (52.5111, 13.4433)  # still plotted

    def test_a_suspect_pin_loses_its_coordinates(self):
        """Known-wrong is not the same as imprecise: it is not drawn at all."""
        row = {**STANDARD_ROW, "geocode_precision": "suspect"}
        card = rows_to_cards([row])[0]
        assert card.lat is None and card.lng is None
        assert card.name == "Klangfeld Nacht"  # the event itself survives

    def test_legacy_rows_stay_trusted(self):
        card = rows_to_cards([STANDARD_ROW])[0]
        assert card.geocode_precision is None
        assert (card.lat, card.lng) == (52.5111, 13.4433)


class TestBboxPadding:
    """Nominatim answers a place with whatever object carries the name.

    For seven of the 22 places measured that is a square, a street or a
    building, not the district: Lavapiés, Poblenou and Barceloneta all come
    back as a 10 m box. Unpadded, those match only a venue standing on the
    exact same coordinate — which is to say, never.
    """

    POINT = (41.3874, 41.3874, 2.1900, 2.1900)  # Poblenou, as OSM answers it

    def test_a_point_becomes_the_smallest_plausible_place(self):
        south, north, west, east = pad_bbox(self.POINT)
        assert round((north - south) * 111.32, 1) == 2.0
        # Longitude degrees are shorter this far north, so the pad is wider.
        assert (east - west) > (north - south)

    def test_a_real_neighbourhood_is_left_alone(self):
        kreuzberg = (52.4823, 52.5170, 13.3823, 13.4657)
        assert pad_bbox(kreuzberg) == kreuzberg

    def test_padding_is_centred(self):
        south, north, west, east = pad_bbox(self.POINT)
        assert round((south + north) / 2, 6) == 41.3874
        assert round((west + east) / 2, 6) == 2.1900


class TestCollapsedPinsInsideABox:
    """The flag cannot carry this on its own — 34 of 35 venues predate it."""

    def test_a_pin_on_the_city_centre_is_not_an_address(self):
        cypher, params = build_bbox_query(
            Constraints(city="Malasaña"), (40.41, 40.43, -3.71, -3.69)
        )
        assert "point.distance(v.location, c.location) > $centroid_collapse_m" in cypher
        assert params["centroid_collapse_m"] == 100.0

    def test_a_pin_two_venues_share_is_not_an_address(self):
        """Eight Barcelona venues sat on one point 888 m from c.location.

        Far enough that the centre test missed it, so the second rule is
        geometric in a different way: two venues cannot share a doorway.
        """
        cypher, _ = build_bbox_query(
            Constraints(city="Gòtic"), (41.37, 41.39, 2.16, 2.19)
        )
        assert "NOT EXISTS { MATCH (other:Venue)-[:LOCATED_IN]->(c)" in cypher
        assert "other.location = v.location AND other.uid <> v.uid" in cypher


class TestGenreSpellings:
    """One genre, several spellings, and words that are not genres at all."""

    def test_a_query_reaches_the_spelling_already_in_the_graph(self):
        """'electronica' is on two artists; canonicalising writes cannot help them."""
        _, params = build_template_query(Constraints(genre="Electronic"))
        assert params["genres"] == ["edm", "electro", "electronic", "electronica"]

    def test_asking_by_the_variant_finds_the_canonical_too(self):
        _, params = build_template_query(Constraints(genre="electronica"))
        assert "electronic" in params["genres"]

    def test_a_non_genre_filters_nothing(self):
        """'various' is a tag nobody can query for — it must not become one."""
        cypher, params = build_template_query(Constraints(genre="various"))
        assert "HAS_GENRE" not in cypher
        assert "genres" not in params


class TestGenreBoundaries:
    """A genre matches whole parts of a slug, never a substring of a word."""

    def build(self, genre):
        cypher, params = build_template_query(Constraints(genre=genre))
        return cypher, params["genres"]

    def test_a_multi_part_variant_reaches_a_composite_slug(self):
        """'r-b' has to reach 'r-b-pop-new-wave', which split() never offers."""
        cypher, genres = self.build("R&B")
        assert "r-b" in genres
        assert "g.slug STARTS WITH asked + '-'" in cypher

    def test_the_boundaries_are_what_stop_a_substring_match(self):
        """ "rap" must not answer 'trap' — different genre, shared letters."""
        cypher, _ = self.build("rap")
        assert "g.slug ENDS WITH '-' + asked" in cypher
        assert "g.slug CONTAINS asked" not in cypher  # never the bare form


class TestStartTimeOnTheCard:
    def test_a_date_only_event_says_so(self):
        card = rows_to_cards([{**STANDARD_ROW, "start_time_known": False}])[0]
        assert card.start_time_known is False
        assert card.start_at == "2026-08-15T23:00:00+00:00"  # the value is unchanged

    def test_legacy_rows_keep_their_time(self):
        """No flag means the old behaviour, which was right for every seed row."""
        assert rows_to_cards([STANDARD_ROW])[0].start_time_known is None

    def test_the_flag_is_returned_by_every_template_path(self):
        for cypher, _ in (
            build_template_query(Constraints(city="Berlin")),
            build_nearby_query(Constraints(near_me=True), 52.5, 13.4, 5.0),
            build_vector_query(Constraints(free_text="loud")),
        ):
            assert "e.start_time_known AS start_time_known" in cypher
