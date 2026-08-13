import sys

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")

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
    embedding_model: str = Field("text-embedding-3-small", alias="EMBEDDINGS_MODEL")
    whisper_model: str = Field("whisper-1", alias="WHISPER_MODEL")

    # Nominatim geocode cache (D12) — path relative to the service CWD.
    geocode_cache_path: str = Field(".geocode_cache.json", alias="GEOCODE_CACHE_PATH")


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
