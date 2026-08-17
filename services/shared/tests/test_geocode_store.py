"""The geocode store is what makes more than one replica safe to run.

What matters here is not the cache hit rate but the two invariants a second
process used to break: one Nominatim request per second for the whole
application, and one shared answer instead of per-process copies racing over a
file.
"""

import json
import time

import pytest
from laiive_shared.geocode import NominatimGeocoder
from laiive_shared.geocode_store import (
    GATE_KEY,
    KEY_PREFIX,
    MISS_TTL_SECONDS,
    JsonFileGeocodeStore,
    RedisGeocodeStore,
)

MADRID = {
    "lat": 40.4168,
    "lng": -3.7038,
    "country_code": "ES",
    "display_name": "Madrid",
}


class FakeRedis:
    """Enough of the Redis contract for the store: get/set with nx and expiry."""

    def __init__(self):
        self.data: dict[str, str] = {}
        self.expiry: dict[str, int] = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex=None, nx=False, px=None):
        if nx and key in self.data:
            return None
        self.data[key] = value
        if ex is not None:
            self.expiry[key] = ex
        if px is not None:
            self.expiry[key] = px
        return True


@pytest.fixture
def redis():
    return FakeRedis()


def test_two_geocoders_sharing_a_store_ask_nominatim_once(redis, monkeypatch):
    """The point of the shared cache: replica B benefits from replica A's call."""
    calls = []

    def fake_request(self, query):
        calls.append(query)
        return MADRID

    monkeypatch.setattr(NominatimGeocoder, "_request", fake_request)

    replica_a = NominatimGeocoder(store=RedisGeocodeStore(client=redis))
    replica_b = NominatimGeocoder(store=RedisGeocodeStore(client=redis))

    assert replica_a.geocode("Sala Clamores, Madrid").lat == MADRID["lat"]
    assert replica_b.geocode("Sala Clamores, Madrid").lat == MADRID["lat"]
    assert calls == ["Sala Clamores, Madrid"]


def test_a_miss_is_cached_but_expires(redis):
    """A transient Nominatim failure used to be remembered as 'does not exist'."""
    store = RedisGeocodeStore(client=redis)
    store.set("nowhere", None)

    cached, value = store.get("nowhere")
    assert cached is True
    assert value is None
    assert redis.expiry[KEY_PREFIX + "nowhere"] == MISS_TTL_SECONDS


def test_a_hit_never_expires(redis):
    store = RedisGeocodeStore(client=redis)
    store.set("madrid", MADRID)
    assert KEY_PREFIX + "madrid" not in store._redis.expiry
    assert store.get("madrid") == (True, MADRID)


def test_the_gate_admits_one_caller_at_a_time(redis):
    """SET NX PX is the whole lock: the second caller waits for the window."""
    store = RedisGeocodeStore(client=redis, min_interval_s=0.05, gate_timeout_s=0.5)
    store.acquire_slot()
    assert redis.data[GATE_KEY] == "1"

    # The window is still held, so a second caller must not get through
    # immediately — FakeRedis has no expiry, so it falls through on timeout.
    started = time.monotonic()
    store.acquire_slot()
    assert time.monotonic() - started >= 0.4


def test_the_gate_never_blocks_a_request_forever_when_redis_is_down():
    class DeadRedis:
        def set(self, *args, **kwargs):
            raise ConnectionError("redis is gone")

        def get(self, key):
            raise ConnectionError("redis is gone")

    store = RedisGeocodeStore(client=DeadRedis())
    store.acquire_slot()  # returns rather than raising
    assert store.get("madrid") == (False, None)
    store.set("madrid", MADRID)  # swallowed


def test_json_file_store_round_trips_and_is_the_default(tmp_path):
    path = tmp_path / "geo.json"
    store = JsonFileGeocodeStore(path, min_interval_s=0.0)
    assert store.get("madrid") == (False, None)
    store.set("madrid", MADRID)
    assert store.get("madrid") == (True, MADRID)
    assert json.loads(path.read_text(encoding="utf-8")) == {"madrid": MADRID}

    # a fresh instance rehydrates from the file, as the pusher does on restart
    assert JsonFileGeocodeStore(path).get("madrid") == (True, MADRID)

    # and a geocoder built the old way still gets this store
    geocoder = NominatimGeocoder(cache_path=path)
    assert isinstance(geocoder._store, JsonFileGeocodeStore)
