"""Bounding boxes, and the cache-compatibility rule that had to come with them.

The bbox exists so a named place ("Kreuzberg") can become an area to search in
rather than a City node that does not exist. Adding a field to a cached shape
is the risky half: the geocode store outlives the process that wrote it and is
shared between services that deploy separately.
"""

import httpx
import pytest
from laiive_shared.geocode import GeocodeResult, NominatimGeocoder

KREUZBERG_HIT = {
    "lat": "52.4979",
    "lon": "13.4184",
    "display_name": "Friedrichshain-Kreuzberg, Berlin, Deutschland",
    "address": {"country_code": "de"},
    "boundingbox": ["52.4823", "52.5170", "13.3823", "13.4657"],
}


@pytest.fixture
def geocoder(tmp_path):
    return NominatimGeocoder(cache_path=tmp_path / "cache.json", min_interval_s=0)


def _respond(payload):
    def handler(*args, **kwargs):
        return httpx.Response(
            200, json=payload, request=httpx.Request("GET", "http://x")
        )

    return handler


def test_a_bbox_is_kept_and_survives_the_cache(geocoder, monkeypatch):
    monkeypatch.setattr(httpx, "get", _respond([KREUZBERG_HIT]))
    live = geocoder.geocode("Kreuzberg, Berlin")
    assert live is not None
    assert live.bbox == (52.4823, 52.5170, 13.3823, 13.4657)

    # Second call is served from the store, where the tuple round-tripped as a
    # JSON list — it must come back as a tuple, not a list.
    monkeypatch.setattr(httpx, "get", _respond([]))
    cached = geocoder.geocode("Kreuzberg, Berlin")
    assert cached == live


def test_a_hit_without_a_bbox_is_still_a_hit(geocoder, monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        _respond([{k: v for k, v in KREUZBERG_HIT.items() if k != "boundingbox"}]),
    )
    result = geocoder.geocode("somewhere")
    assert result is not None and result.bbox is None
    assert result.bbox_diagonal_km() is None


def test_the_diagonal_measures_the_area(geocoder, monkeypatch):
    monkeypatch.setattr(httpx, "get", _respond([KREUZBERG_HIT]))
    diagonal = geocoder.geocode("Kreuzberg, Berlin").bbox_diagonal_km()
    # Kreuzberg is a few km across; the assertion is deliberately loose because
    # OSM redraws district extents and this is not a test of Berlin.
    assert 1 < diagonal < 15


def test_an_entry_written_by_a_newer_version_still_loads():
    """Forward compatibility: unknown keys are dropped, not raised on.

    GeocodeResult(**raw) used to be a straight splat, so the first process
    reading an entry written by a version with one more field would die with a
    TypeError on a cache hit — the failure mode this file exists to prevent.
    """
    raw = {
        "lat": 52.5,
        "lng": 13.4,
        "country_code": "DE",
        "display_name": "Berlin",
        "bbox": [52.3, 52.7, 13.1, 13.8],
        "osm_type": "relation",  # a field this version knows nothing about
    }
    result = NominatimGeocoder._from_cached(raw)
    assert result == GeocodeResult(52.5, 13.4, "DE", "Berlin", (52.3, 52.7, 13.1, 13.8))


def test_an_entry_written_by_an_older_version_still_loads():
    raw = {"lat": 52.5, "lng": 13.4, "country_code": "DE", "display_name": "Berlin"}
    assert NominatimGeocoder._from_cached(raw).bbox is None


class TestSecondOpinion:
    """An answer inside the guard but far out does not win by being first.

    Sant Jordi Club, from the repaired graph: the name form resolves 17.7 km
    from Barcelona, which the 25 km guard allows, and the address form — the
    correct Montjuïc one — resolves 3.1 km out beside the Palau Sant Jordi it
    shares a wall with. The old chain stopped at the first plausible answer and
    never asked.
    """

    BARCELONA = GeocodeResult(41.3874, 2.1686, "ES", "Barcelona")
    # ~17 km north, inside VENUE_MAX_KM; ~3 km out, on Montjuïc.
    FAR = {
        "lat": 41.5437,
        "lng": 2.2068,
        "country_code": "ES",
        "display_name": "somewhere north",
    }
    NEAR = {
        "lat": 41.3635,
        "lng": 2.1526,
        "country_code": "ES",
        "display_name": "Palau Sant Jordi",
    }

    def geocoder(self, tmp_path, answers):
        geo = NominatimGeocoder(cache_path=tmp_path / "c.json", min_interval_s=0)
        geo._request = lambda query: answers.pop(0)  # one per form, in order
        return geo

    def test_a_far_answer_yields_to_a_nearer_form(self, tmp_path):
        geo = self.geocoder(tmp_path, [self.FAR, self.NEAR])
        result = geo.geocode_venue(
            "Sant Jordi Club",
            "Passeig Olímpic 5-7, 08038 Barcelona",
            "Barcelona",
            near=self.BARCELONA,
        )
        assert result.display_name == "Palau Sant Jordi"

    def test_a_close_answer_still_wins_immediately(self, tmp_path):
        """Sala El Sol: 0.3 km by name, 25 km by address. No second opinion."""
        geo = self.geocoder(tmp_path, [self.NEAR])
        result = geo.geocode_venue(
            "Sala El Sol", "Calle Jardines 3, Madrid", "Barcelona", near=self.BARCELONA
        )
        assert result.display_name == "Palau Sant Jordi"  # only one call made

    def test_an_out_of_town_venue_is_still_answered(self, tmp_path):
        """Every form agreeing on "far" means the venue really is out there."""
        geo = self.geocoder(tmp_path, [self.FAR, None, None])
        result = geo.geocode_venue(
            "Festival Site", "some field", "Barcelona", near=self.BARCELONA
        )
        assert result is not None and result.display_name == "somewhere north"

    def test_without_a_reference_the_first_answer_wins(self, tmp_path):
        geo = self.geocoder(tmp_path, [self.FAR])
        assert (
            geo.geocode_venue("Anywhere", None, None).display_name == "somewhere north"
        )
