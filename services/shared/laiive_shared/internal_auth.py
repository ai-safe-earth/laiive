"""Second layer of the "only the gateway may call this service" boundary.

The gateway verifies the JWT and hands the services `X-User-Id` / `X-User-Role`
as facts. The services believe those headers, which is safe exactly as long as
nothing else can reach them. Today that rests entirely on network placement:
compose `expose`, `--host 127.0.0.1`, and in the cluster a default-deny
NetworkPolicy.

That is a good control and it is the primary one — but it is also invisible from
inside the process, cluster-specific, and one misapplied label away from being
off. This adds a check the service itself can make: a shared secret the gateway
injects and nothing else knows. Note what it is *not*: it is not
authentication of the end user (the JWT already did that) and it is not a
defence against someone who can read the pod's environment.

Deliberately middleware and not a `Depends`: an app-wide dependency would also
gate `/livez` and `/readyz`, and the kubelet cannot send a header.

No key configured means no check, so local runs, compose and the whole test
suite behave exactly as before.
"""

import hmac
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from .health import LIVENESS_PATH, READINESS_PATH

logger = logging.getLogger(__name__)

HEADER = "x-internal-key"

# Probes are exempt because the kubelet cannot authenticate; `/health` and `/`
# are exempt because they are the operator's window into a service that may be
# misconfigured — including misconfigured keys.
EXEMPT_PATHS = frozenset({LIVENESS_PATH, READINESS_PATH, "/health", "/"})


def install_internal_auth(app: FastAPI, *, expected: str) -> None:
    """Reject requests that did not come through the gateway.

    `expected` is the shared secret (`INTERNAL_API_KEY`). Empty disables the
    check entirely — that is the local and single-process path, and it must stay
    a no-op rather than a hard failure.
    """
    if not expected:
        logger.info("internal-key check disabled (no INTERNAL_API_KEY set)")
        return

    @app.middleware("http")
    async def _require_internal_key(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        # compare_digest, not ==, so a wrong key cannot be discovered a byte at
        # a time from response timing.
        if not hmac.compare_digest(request.headers.get(HEADER, ""), expected):
            logger.warning(
                "rejected %s %s: missing or wrong internal key",
                request.method,
                request.url.path,
            )
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        return await call_next(request)
