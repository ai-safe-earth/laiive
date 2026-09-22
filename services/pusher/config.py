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
    # Dated snapshots, not the floating alias — see the note in the retriever's
    # config. refine_draft returns the draft unchanged when a reply will not
    # parse, so a silent model swap costs extractions with nothing in the logs.
    conversation_model: str = Field("gpt-4o-2024-08-06", alias="OPENAI_MODEL")
    # Same env key the retriever's classifier uses: both are the cheap
    # "decide one small thing" model. Here it only detects the reply language.
    classifier_model: str = Field("gpt-4o-mini-2024-07-18", alias="CLASSIFIER_MODEL")
    embedding_model: str = Field("text-embedding-3-small", alias="EMBEDDINGS_MODEL")
    whisper_model: str = Field("whisper-1", alias="WHISPER_MODEL")

    # Nominatim geocode cache (D12) — path relative to the service CWD.
    geocode_cache_path: str = Field(".geocode_cache.json", alias="GEOCODE_CACHE_PATH")
    # Set it and the geocode cache and its 1 req/s gate become shared across
    # replicas; unset keeps the process-local JSON file (see geocode_store.py).
    redis_url: str = Field("", alias="REDIS_URL")
    # Shared with the gateway; empty disables the check (see internal_auth.py).
    internal_api_key: str = Field("", alias="INTERNAL_API_KEY")

    # push_records: the write verdict, joined to the gateway's conversation_logs
    # on request_id. Empty URL disables the write — local runs and tests. This
    # makes the pusher the fourth holder of the full-RLS-bypass service key; the
    # standing mitigation is a scoped insert-only Postgres role for all four,
    # which is tracked and not done.
    supabase_url: str = Field("", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field("", alias="SUPABASE_SERVICE_ROLE_KEY")

    # Tracing into Arize Phoenix (laiive_shared.tracing). This service never had
    # tracing: its three module-level OpenAI clients were outside the Langfuse
    # wrapper. The instrumentor patches the openai module, so they are covered
    # here without being touched.
    phoenix_enabled: bool = Field(False, alias="PHOENIX_ENABLED")
    phoenix_collector_endpoint: str = Field(
        "http://localhost:6006", alias="PHOENIX_COLLECTOR_ENDPOINT"
    )
    phoenix_api_key: str = Field("", alias="PHOENIX_API_KEY")


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
