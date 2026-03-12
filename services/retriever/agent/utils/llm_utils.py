from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
from config import settings


def get_openai_client(
    api_key: str = None, base_url: str = None, http_client=None
) -> OpenAI:
    key = settings.openai_api_key

    if settings.langfuse_enabled:
        from langfuse import Langfuse

        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        from langfuse.openai import OpenAI as LangfuseOpenAI

        return LangfuseOpenAI(api_key=key, base_url=base_url, http_client=http_client)
    else:
        return OpenAI(api_key=key, base_url=base_url, http_client=http_client)


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
