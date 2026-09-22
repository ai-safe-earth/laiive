"""OpenTelemetry tracing into Arize Phoenix, shared by every Python service.

This replaces the Langfuse client wrapper, and the difference is why the
migration is small rather than a refactor: Langfuse wrapped a *client*, so only
calls made through the retriever's ``get_openai_client()`` were traced and the
pusher's three module-level clients (``conversation.py``, ``converters.py``,
``graph.py``) were invisible. OpenInference instruments the ``openai`` *module*,
so one call at import time covers every OpenAI call in the process no matter who
constructed the client — the pusher's three included, untouched.

Off unless ``enabled``, the same posture as the ``LANGFUSE_ENABLED`` flag it
replaces. ``phoenix.otel`` is imported inside the function so a service still
boots if the tracing wheels are missing.

Export is fire-and-forget by construction: ``batch=True`` installs a
BatchSpanProcessor, which drops spans it cannot deliver rather than raising into
the caller. A collector that is down costs traces, never requests.
"""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# phoenix.otel infers HTTP vs gRPC from the endpoint's path and warns
# ("Could not infer collector endpoint protocol") when there is none, which is
# what a bare base URL gives it — and a base URL is what anyone types, in .env
# and in `fly secrets` alike. Appending the OTLP/HTTP path makes the choice
# explicit instead of inferred. 6006 serves both the UI and OTLP/HTTP; the gRPC
# collector is 4317, and an endpoint that already names a path is left alone.
OTLP_HTTP_PATH = "/v1/traces"


def _with_otlp_path(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return endpoint  # not a URL we can reason about — hand it over as typed
    if parsed.path.strip("/"):
        return endpoint
    return endpoint.rstrip("/") + OTLP_HTTP_PATH


def setup_tracing(
    service: str,
    *,
    enabled: bool,
    endpoint: str,
    api_key: str = "",
) -> bool:
    """Register the Phoenix tracer provider. Returns whether tracing is on.

    Call once at module scope in the service's ``api.py``, before the first
    OpenAI call is made.

    Settings are passed in rather than read from the environment on purpose:
    every service loads the root ``.env`` through pydantic-settings, which reads
    the file without exporting it, so ``phoenix.otel``'s own ``PHOENIX_*``
    lookups would find nothing on a Fly machine or a local run alike.
    """
    if not enabled:
        return False
    try:
        from phoenix.otel import register

        register(
            project_name=f"laiive-{service}",
            endpoint=_with_otlp_path(endpoint),
            batch=True,
            auto_instrument=True,
            **({"api_key": api_key} if api_key else {}),
        )
    except Exception as e:
        # A tracing failure must never stop a service booting — a missing wheel,
        # a malformed endpoint and an unreachable collector all land here.
        logger.warning("Phoenix tracing off (%s): %s", type(e).__name__, e)
        return False
    logger.info("Phoenix tracing on: %s -> %s", service, endpoint)
    return True
