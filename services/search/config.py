import sys

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")

    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8004, alias="PORT")

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    tavily_api_key: str = Field(..., alias="TAVILY_API_KEY")

    # Reports outlive a restart: they persist in Supabase (service-role only).
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")

    # Extraction runs on the cheap model first; the fallback re-reads a page
    # only when mini finds nothing on a page that plainly lists events (05: batch cost).
    extraction_model: str = Field("gpt-4o-mini", alias="SEARCH_EXTRACTION_MODEL")
    extraction_fallback_model: str = Field(
        "gpt-4o", alias="SEARCH_EXTRACTION_FALLBACK_MODEL"
    )
    embedding_model: str = Field("text-embedding-3-small", alias="EMBEDDINGS_MODEL")

    # Sweep bounds — a sweep is a synchronous admin call, keep it minutes not hours.
    sweep_max_pages: int = Field(10, alias="SEARCH_SWEEP_MAX_PAGES")
    sweep_results_per_query: int = Field(5, alias="SEARCH_RESULTS_PER_QUERY")
    page_max_chars: int = Field(12000, alias="SEARCH_PAGE_MAX_CHARS")

    # Cosine score above which a vector neighbour is flagged as a likely
    # duplicate in the dry-run report (advisory — the writer's own probe is
    # what actually refuses a duplicate on approve).
    dedup_similarity: float = Field(0.92, alias="SEARCH_DEDUP_SIMILARITY")

    geocode_cache_path: str = Field(".geocode_cache.json", alias="GEOCODE_CACHE_PATH")


try:
    settings = Settings()
except ValidationError as e:
    missing = sorted(
        {str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"}
    )
    sys.exit(
        "search config: missing required environment keys: "
        + ", ".join(missing)
        + "\n(.env is loaded from ../../.env relative to CWD — run from services/search)"
    )
