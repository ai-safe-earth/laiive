from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings


def get_openai_client() -> OpenAI:
    """The one OpenAI client factory.

    It used to branch on `langfuse_enabled` and return a wrapped client, which
    is why only this service was ever traced. Tracing is no longer a property of
    the client: `laiive_shared.tracing.setup_tracing` instruments the openai
    module once at startup, so a plain client is traced and the pusher's
    module-level clients are too.
    """
    return OpenAI(api_key=settings.openai_api_key)


RETRY_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RETRY_EXCEPTIONS),
)
def chat_completion_with_retry(client: OpenAI, **kwargs):
    return client.chat.completions.create(**kwargs)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RETRY_EXCEPTIONS),
)
def embedding_with_retry(client: OpenAI, **kwargs):
    return client.embeddings.create(**kwargs)
