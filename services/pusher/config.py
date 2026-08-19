import sys

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")
    neo4j_max_pool_size: int = Field(5, alias="PUSHER_NEO4J_MAX_POOL_SIZE")

    aura_instanceid: str | None = Field(None, alias="AURA_INSTANCEID")
    aura_instancename: str | None = Field(None, alias="AURA_INSTANCENAME")

    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8003, alias="PORT")

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    conversation_model: str = Field("gpt-4o", alias="OPENAI_MODEL")
    # Same env key the retriever's classifier uses: both are the cheap
    # "decide one small thing" model. Here it only detects the reply language.
    classifier_model: str = Field("gpt-4o-mini", alias="CLASSIFIER_MODEL")
    embedding_model: str = Field("text-embedding-3-small", alias="EMBEDDINGS_MODEL")
    whisper_model: str = Field("whisper-1", alias="WHISPER_MODEL")

    # Nominatim geocode cache (D12) — path relative to the service CWD.
    geocode_cache_path: str = Field(".geocode_cache.json", alias="GEOCODE_CACHE_PATH")
    # Set it and the geocode cache and its 1 req/s gate become shared across
    # replicas; unset keeps the process-local JSON file (see geocode_store.py).
    redis_url: str = Field("", alias="REDIS_URL")
    # Shared with the gateway; empty disables the check (see internal_auth.py).
    internal_api_key: str = Field("", alias="INTERNAL_API_KEY")


try:
    settings = Settings()
except ValidationError as e:
    missing = sorted(
        {str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"}
    )
    sys.exit(
        "pusher config: missing required environment keys: "
        + ", ".join(missing)
        + "\n(.env is loaded from ../../.env relative to CWD — run from services/pusher)"
    )
