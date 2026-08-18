import sys

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field(..., alias="NEO4J_USERNAME")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")
    # Per replica. 4 retriever pods x 16 + pusher 5 + search 5 = 74 connections.
    neo4j_max_pool_size: int = Field(16, alias="NEO4J_MAX_POOL_SIZE")
    # Shared with the gateway; empty disables the check (see internal_auth.py).
    internal_api_key: str = Field("", alias="INTERNAL_API_KEY")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    # Models per role (05-decisions R3): cheap classifier, correctness-critical
    # Cypher long tail, tone-critical composer. Swapping any is a one-line change.
    classifier_model: str = Field("gpt-4o-mini", alias="CLASSIFIER_MODEL")
    query_builder_model: str = Field("gpt-4o", alias="QUERY_BUILDER_MODEL")
    composer_model: str = Field("gpt-4o", alias="COMPOSER_MODEL")
    embeddings_model: str = Field("text-embedding-3-small", alias="EMBEDDINGS_MODEL")
    embeddings_dimensions: int = 1536
    # Voice input is public (anonymous callers included), so the model choice
    # and the size cap in laiive_shared.speech are both cost decisions.
    whisper_model: str = Field("whisper-1", alias="WHISPER_MODEL")

    # Safety: OpenAI moderation endpoint (free) + regex Cypher guard.
    # The OpenRouter/LlamaGuard layer is gone (R3 — it never executed).
    enable_moderation: bool = Field(True, alias="ENABLE_MODERATION")

    langfuse_public_key: str = Field("", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field("", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field("https://cloud.langfuse.com", alias="LANGFUSE_HOST")
    langfuse_enabled: bool = Field(True, alias="LANGFUSE_ENABLED")

    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8002, alias="PORT")

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Query settings
    max_results_limit: int = 10
    vector_k: int = 20
    vector_score_threshold: float = 0.70

    # LLM settings
    llm_temperature_composer: float = 0.7
    llm_temperature_classifier: float = 0.0

    # Location settings
    location_default_radius_km: float = 5.0
    location_max_radius_km: float = 30.0
    location_min_events: int = 5
    location_radius_steps: list[float] = [5.0, 10.0, 15.0, 20.0, 30.0]
    # A venue whose pin is only its city's centroid is "somewhere in this city",
    # not "here". It stays findable but sorts behind anything actually located,
    # by adding this to its sort key only — the distance_km on the card stays
    # the true one. See laiive_shared.geocode / v.geocode_precision.
    location_centroid_penalty_km: float = 5.0


try:
    settings = Settings()
except ValidationError as e:
    missing = sorted(
        {str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"}
    )
    sys.exit(
        "retriever config: missing required environment keys: "
        + ", ".join(missing)
        + "\n(.env is loaded from ../../.env relative to CWD — run from services/retriever)"
    )
