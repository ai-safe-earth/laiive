"""Nominatim geocoding with cache and 1 req/s politeness (05-decisions D12).

Nominatim's usage policy requires a descriptive User-Agent and at most one
request per second. The cache means repeat submissions for known venues and
cities never hit the network at all.
"""

import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from .geocode_store import GeocodeStore, JsonFileGeocodeStore
from .normalize import norm

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "laiive/0.2 (event platform; contact: arroscar@gmail.com)"

# How far a venue may sit from the centroid of the city it claims to be in
# before the answer is rejected. Measured, not guessed: across the whole cached
# corpus every correct answer landed within 12.5 km of its city centroid and
# every answer beyond that was wrong (a same-name venue in another town, a
# theme park 627 km away, a street in the Philippines). 25 km keeps double the
# observed headroom while still rejecting all of them.
VENUE_MAX_KM = 25.0

# (venue, city) -> street address, or None. Injected by the caller so this
# module stays free of search/LLM clients; see services/search/agent/address_lookup.py.
AddressResolver = Callable[[str, str | None], str | None]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lng: float
    country_code: str  # ISO-3166-1 alpha-2, lowercased by Nominatim; stored upper
    display_name: str


class NominatimGeocoder:
    """Rate-limited, cached forward geocoder."""

    def __init__(
        self,
        cache_path: Path | str | None = None,
        min_interval_s: float = 1.0,
        timeout_s: float = 10.0,
        store: GeocodeStore | None = None,
    ):
        self._timeout_s = timeout_s
        # The cache and the rate gate belong to the store — pass a
        # RedisGeocodeStore when more than one process geocodes. `cache_path` is
        # kept so existing call sites and tests read unchanged.
        self._store: GeocodeStore = store or JsonFileGeocodeStore(
            cache_path, min_interval_s=min_interval_s
        )

    def geocode(self, query: str) -> GeocodeResult | None:
        """Resolve a free-text place query. Returns None when nothing matches."""
        key = norm(query)
        cached, value = self._store.get(key)
        if cached:
            return self._from_cached(value)

        raw = self._request(query)
        self._store.set(key, raw)
        return self._from_cached(raw)

    def geocode_venue(
        self,
        venue: str,
        address: str | None = None,
        city: str | None = None,
        near: GeocodeResult | None = None,
        max_km: float = VENUE_MAX_KM,
        address_resolver: AddressResolver | None = None,
    ) -> GeocodeResult | None:
        """Locate a venue, trying the query forms Nominatim actually answers.

        Callers used to pass a single ", ".join(venue, address, city) string.
        That form scores 0% against Nominatim: `address` already ends with the
        city, so appending the city duplicates it ("…28009 madrid, spain,
        madrid"), and a full street string over-specifies what is really a POI
        lookup. The same venues resolve as "venue, city".

        Forms are tried most-likely first and the first plausible answer wins.
        `near` — normally the already-geocoded city — rejects an answer that
        landed in the wrong metro area entirely, which is worse than no answer:
        a miss falls back to the city centroid and warns, while a wrong hit is
        written to the graph silently.

        `address_resolver` is the last resort: given a venue and city it returns
        a street address from somewhere outside OSM. Small independent venues
        are simply absent from OSM as named POIs, but their address is on the
        open web, and an address is what a street geocoder is good at.
        """
        # Sweep-extracted addresses usually already end with the city ("…28009
        # madrid, spain"); a hand-typed one usually does not, and a bare street
        # name is ambiguous across every city in the country. Append the city
        # only when it is not already in there.
        forms = [
            f"{venue}, {city}" if city else venue,
            self._with_city(address, city),
            ", ".join(p for p in (venue, address, city) if p),
        ]
        seen: set[str] = set()
        for query in forms:
            result = self._try_form(query, seen, near, max_km)
            if result is not None:
                return result

        if address_resolver is not None:
            found = self._resolved_address(venue, city, address_resolver)
            if found:
                return self._try_form(self._with_city(found, city), seen, near, max_km)
        return None

    @staticmethod
    def _with_city(address: str | None, city: str | None) -> str:
        if not address:
            return ""
        if city and norm(city) not in norm(address):
            return f"{address}, {city}"
        return address

    def _try_form(
        self,
        query: str,
        seen: set[str],
        near: GeocodeResult | None,
        max_km: float,
    ) -> GeocodeResult | None:
        """One candidate query: skip duplicates, reject implausible answers."""
        if not query or norm(query) in seen:
            return None
        seen.add(norm(query))
        result = self.geocode(query)
        if result is None:
            return None
        if near is not None:
            off_km = haversine_km(result.lat, result.lng, near.lat, near.lng)
            if off_km > max_km:
                logger.warning(
                    "Geocode for %r landed %.0f km away (%r) — rejected",
                    query,
                    off_km,
                    result.display_name,
                )
                return None
        return result

    def _resolved_address(
        self, venue: str, city: str | None, resolver: AddressResolver
    ) -> str | None:
        """Cached address lookup — a web search and an LLM call are not cheap.

        Shares the geocode store, so a venue is looked up once and a failed
        lookup expires on the store's miss TTL rather than repeating per write.
        """
        key = f"addr:{norm(venue)}|{norm(city or '')}"
        cached, value = self._store.get(key)
        if cached:
            return (value or {}).get("address")
        try:
            address = resolver(venue, city)
        except Exception as e:  # a resolver outage must not fail the write
            logger.warning("Address lookup failed for %r: %s", venue, e)
            return None
        self._store.set(key, {"address": address} if address else None)
        return address

    def _request(self, query: str) -> dict | None:
        self._store.acquire_slot()
        try:
            resp = httpx.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": 1,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=self._timeout_s,
            )
            resp.raise_for_status()
            hits = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.warning("Geocoding failed for %r: %s", query, e)
            return None
        if not hits:
            return None
        hit = hits[0]
        return {
            "lat": float(hit["lat"]),
            "lng": float(hit["lon"]),
            "country_code": (hit.get("address", {}).get("country_code") or "").upper(),
            "display_name": hit.get("display_name", ""),
        }

    @staticmethod
    def _from_cached(raw: dict | None) -> GeocodeResult | None:
        if raw is None:
            return None
        return GeocodeResult(**raw)
