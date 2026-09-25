"""The one OpenAI client factory."""

from openai import OpenAI

from config import settings

# Attempts per call, not retries on top of them. This used to be a tenacity
# ladder around two wrapper functions, retrying RateLimitError, APITimeoutError
# and APIConnectionError with exponential backoff - which is exactly what the
# SDK does for those three when max_retries is set, so the ladder was a second
# one nested inside the first. The wrappers were also the seam the tests
# patched; they inject a Mock client instead now.
MAX_RETRIES = 3


def get_openai_client() -> OpenAI:
    """The client every call in this service is made with.

    It used to branch on `langfuse_enabled` and return a wrapped client, which
    is why only this service was ever traced. Tracing is no longer a property of
    the client: `laiive_shared.tracing.setup_tracing` instruments the openai
    module once at startup, so a plain client is traced and the pusher's
    module-level clients are too.
    """
    return OpenAI(api_key=settings.openai_api_key, max_retries=MAX_RETRIES)
