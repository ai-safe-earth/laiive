"""Nominatim geocoding with cache and 1 req/s politeness (05-decisions D12).

Nominatim's usage policy requires a descriptive User-Agent and at most one
request per second. The cache means repeat submissions for known venues and
cities never hit the network at all.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from .geocode_store import GeocodeStore, JsonFileGeocodeStore
from .normalize import norm

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "laiive/0.2 (event platform; contact: arroscar@gmail.com)"


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
