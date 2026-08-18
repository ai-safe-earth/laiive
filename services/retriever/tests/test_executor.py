"""Executor unit tests — query builders are pure functions, execution mocked."""

from unittest.mock import Mock

from agent.classifier import Constraints
from agent.executor import (
    Executor,
    build_nearby_query,
    build_template_query,
    build_vector_query,
    flexible_rows_to_cards,
    rows_to_cards,
)
from agent.router import ExecutionPlan, PlanKind

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
        assert params["genre"] == "jazz"
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
        assert "e.start_at >= datetime($date_from)" in cypher
        assert "e.start_at < datetime($date_to)" in cypher
        assert "e.start_at >= datetime()" not in cypher

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

    def test_template_and_vector_paths_are_untouched(self):
        """Only nearby ranks on location, so only nearby pays for the check."""
        for cypher, _ in (
            build_template_query(Constraints(city="Berlin")),
            build_vector_query(Constraints(free_text="loud")),
        ):
            assert "geocode_precision" not in cypher
