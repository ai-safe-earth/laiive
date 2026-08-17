"""Kubernetes probe endpoints, shared by every Python service.

Three endpoints, three audiences, and conflating them is how a healthy service
gets restarted:

- ``/livez``   — the kubelet asking "is this process wedged?". Zero I/O, always
  200. A liveness probe that touches a dependency turns *someone else's* outage
  into a restart loop of your own.
- ``/readyz``  — the kubelet asking "should I send traffic here?". Checks the
  dependencies the service cannot serve without, with the result cached so N
  replicas probing every 30 s do not become load of their own.
- ``/health``  — a human or an uptime monitor asking for detail. Each service
  keeps its own, and it may be as expensive as it likes.

The retriever's ``/health`` calls ``openai.models.list()``; as a liveness probe
across replicas that was tens of needless authenticated API calls a minute, and
an OpenAI blip would have restarted pods that were serving fine.
"""

import threading
import time
from typing import Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse

LIVENESS_PATH = "/livez"
READINESS_PATH = "/readyz"

DEFAULT_CACHE_SECONDS = 20.0


class _ReadinessCache:
    """Caches a successful check; re-runs after a failure.

    Successes are cached because they are the steady state and the probe should
    be nearly free. Failures are not, so a recovered dependency is picked up on
    the very next probe instead of up to a cache window later.
    """

    def __init__(self, check: Callable[[], bool], cache_seconds: float):
        self._check = check
        self._cache_seconds = cache_seconds
        self._lock = threading.Lock()
        self._ok_until = 0.0

    def ready(self) -> tuple[bool, str | None]:
        with self._lock:
            if time.monotonic() < self._ok_until:
                return True, None
        try:
            ok = bool(self._check())
        except Exception as exc:  # a dependency being down is not a bug here
            return False, f"{type(exc).__name__}: {exc}"
        if ok:
            with self._lock:
                self._ok_until = time.monotonic() + self._cache_seconds
            return True, None
        return False, "dependency check returned false"


def register_health(
    app: FastAPI,
    *,
    service: str,
    ready_check: Callable[[], bool],
    cache_seconds: float = DEFAULT_CACHE_SECONDS,
) -> None:
    """Mount ``/livez`` and ``/readyz`` on ``app``.

    ``ready_check`` should be cheap and synchronous — one round-trip to the
    thing the service cannot work without (for all three services today, Neo4j).
    Returning false or raising both mean "not ready"; never call a metered API
    from it.
    """
    cache = _ReadinessCache(ready_check, cache_seconds)

    @app.get(LIVENESS_PATH, include_in_schema=False)
    def livez():
        """Process is up. Deliberately checks nothing."""
        return {"status": "ok", "service": service}

    @app.get(READINESS_PATH, include_in_schema=False)
    def readyz():
        ok, reason = cache.ready()
        if ok:
            return {"status": "ready", "service": service}
        return JSONResponse(
            {"status": "not_ready", "service": service, "reason": reason},
            status_code=503,
        )
