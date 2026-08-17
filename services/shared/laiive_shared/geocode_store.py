"""Where the geocoder's cache and its 1 req/s gate live.

Nominatim's policy is one request per second **per application**, not per
process. The original in-process `threading.Lock` was correct for one uvicorn
process and quietly wrong the moment a second replica existed: two pods meant
two requests a second, and both rewrote the same cache file with whatever each
happened to know (`write_text` of the whole dict, no locking, last writer wins).

So the gate is a distributed lock and the cache is shared state. Two
implementations:

- `JsonFileGeocodeStore` — the original behaviour, and still the default. One
  process, a JSON file, a threading lock. Correct for local runs and tests.
- `RedisGeocodeStore` — one bucket and one gate for every replica. `SET NX PX`
  is the whole lock; nothing else is needed.

Redis is imported lazily so `laiive_shared` keeps declaring no client of its
own, and so a service that never geocodes never needs the dependency.
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

# Bumped when the cached shape changes, so old entries are ignored rather than
# mis-parsed.
KEY_PREFIX = "geo:v1:"
GATE_KEY = "geo:gate"

# A "no match" answer is cached too, or every submission naming an unknown venue
# re-asks Nominatim. But it expires: a transient 503 used to be recorded as "this
# place does not exist" permanently.
MISS_TTL_SECONDS = 7 * 24 * 3600


class GeocodeStore(Protocol):
    """Cache plus rate gate. `get` distinguishes a cached None from a miss."""

    def get(self, key: str) -> tuple[bool, dict | None]:
        """Return (cached, value). `(True, None)` means "known to have no match"."""
        ...

    def set(self, key: str, value: dict | None) -> None: ...

    def acquire_slot(self) -> None:
        """Block until this caller may issue one Nominatim request."""
        ...


class JsonFileGeocodeStore:
    """In-process cache backed by a JSON file, with a thread lock as the gate."""

    def __init__(
        self,
        cache_path: Path | str | None = None,
        min_interval_s: float = 1.0,
    ):
        self._min_interval_s = min_interval_s
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

    def get(self, key: str) -> tuple[bool, dict | None]:
        if key in self._cache:
            return True, self._cache[key]
        return False, None

    def set(self, key: str, value: dict | None) -> None:
        self._cache[key] = value
        if not self._cache_path:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("Could not persist geocode cache: %s", e)

    def acquire_slot(self) -> None:
        with self._lock:
            wait = self._min_interval_s - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()


class RedisGeocodeStore:
    """Cache and gate shared by every replica.

    `client` is injected in tests; in production pass a URL and let it build one.
    """

    def __init__(
        self,
        url: str = "",
        client=None,
        min_interval_s: float = 1.0,
        gate_timeout_s: float = 15.0,
    ):
        if client is None:
            import redis  # lazy: only a service that geocodes needs the dep

            client = redis.Redis.from_url(
                url, decode_responses=True, socket_timeout=2.0
            )
        self._redis = client
        self._min_interval_s = min_interval_s
        self._gate_timeout_s = gate_timeout_s

    def get(self, key: str) -> tuple[bool, dict | None]:
        try:
            raw = self._redis.get(KEY_PREFIX + key)
        except Exception as e:  # a cache outage must not fail a submission
            logger.warning("Geocode cache read failed for %r: %s", key, e)
            return False, None
        if raw is None:
            return False, None
        try:
            return True, json.loads(raw)
        except json.JSONDecodeError:
            return False, None

    def set(self, key: str, value: dict | None) -> None:
        try:
            # Hits never expire — a venue's coordinates do not move. Misses do.
            self._redis.set(
                KEY_PREFIX + key,
                json.dumps(value),
                ex=None if value is not None else MISS_TTL_SECONDS,
            )
        except Exception as e:
            logger.warning("Geocode cache write failed for %r: %s", key, e)

    def acquire_slot(self) -> None:
        """Hold a short-lived lock so only one replica calls Nominatim per second.

        The key's own expiry *is* the interval: whoever sets it owns the next
        window, and the window ends by itself even if that process dies. Falls
        through after `gate_timeout_s` rather than blocking a request forever —
        exceeding the rate limit occasionally beats hanging a submission.
        """
        px = max(1, int(self._min_interval_s * 1000) + 100)
        deadline = time.monotonic() + self._gate_timeout_s
        while True:
            try:
                if self._redis.set(GATE_KEY, "1", nx=True, px=px):
                    return
            except Exception as e:
                logger.warning("Geocode rate gate unavailable, proceeding: %s", e)
                return
            if time.monotonic() >= deadline:
                logger.warning("Geocode rate gate timed out; proceeding anyway")
                return
            time.sleep(0.05)
