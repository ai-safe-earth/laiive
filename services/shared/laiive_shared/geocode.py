"""Nominatim geocoding with cache and 1 req/s politeness (05-decisions D12).

Nominatim's usage policy requires a descriptive User-Agent and at most one
request per second. The cache means repeat submissions for known venues and
cities never hit the network at all.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

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
    ):
        self._min_interval_s = min_interval_s
        self._timeout_s = timeout_s
        self._last_request_at = 0.0
        self._lock = threading.Lock()
        self._cache_path = Path(cache_path) if cache_path else None
        self._cache: dict[str, dict | None] = {}
        if self._cache_path and self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    "Could not load geocode cache %s: %s", self._cache_path, e
                )

    def geocode(self, query: str) -> GeocodeResult | None:
        """Resolve a free-text place query. Returns None when nothing matches."""
        key = norm(query)
        if key in self._cache:
            return self._from_cached(self._cache[key])

        raw = self._request(query)
        self._cache[key] = raw
        self._persist_cache()
        return self._from_cached(raw)

    def _request(self, query: str) -> dict | None:
        with self._lock:
            wait = self._min_interval_s - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()
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

    def _persist_cache(self) -> None:
        if not self._cache_path:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("Could not persist geocode cache: %s", e)
