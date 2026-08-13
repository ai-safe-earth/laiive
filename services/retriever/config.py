from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field(..., alias="NEO4J_USERNAME")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(..., alias="NEO4J_DATABASE")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openrouter_api_key: str = Field(..., alias="OPENROUTER_API_KEY")

    # Core Models
    query_builder_model: str = Field("gpt-4o", alias="QUERY_BUILDER_MODEL")
    embeddings_model: str = Field("text-embedding-3-small", alias="EMBEDDINGS_MODEL")

    # Conversation Model (used for all conversation tasks: decision, guidance, results, goodbye)
    conversation_model: str = Field("gpt-4o", alias="CONVERSATIONAL_MODEL")

    # Safety Model (used for all safety checks: input validation, output validation)
    safety_model: str = Field("meta-llama/llama-guard-4-12b", alias="SAFETY_MODEL")

    langfuse_public_key: str = Field("", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field("", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field("https://cloud.langfuse.com", alias="LANGFUSE_HOST")
    langfuse_enabled: bool = Field(True, alias="LANGFUSE_ENABLED")

    # ares_api_key: Optional[str] = Field(None, alias="ARES_API_KEY")

    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8002, alias="PORT")

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API settings
    sse_stream_delay: float = 0.01

    # Query settings
    max_results_limit: int = 10
    results_preview_limit: int = 5

    # LLM settings
    llm_temperature_conversation: float = 0.7
    llm_temperature_goodbye: float = 0.8
    llm_temperature_decision: float = 0.0
    decision_max_tokens: int = 20

    # Safety settings
    enable_output_safety_check: bool = Field(
        False, alias="ENABLE_OUTPUT_SAFETY_CHECK"
    )  # Set to True to validate AI responses with LlamaGuard (adds ~500ms latency)

    # ReAct agent settings
    react_max_loops: int = Field(5, alias="REACT_MAX_LOOPS")

    # Internet search settings
    brave_search_api_key: str = Field("", alias="BRAVE_SEARCH_API_KEY")
    internet_search_extraction_model: str = Field(
        "gpt-4o", alias="INTERNET_SEARCH_MODEL"
    )
    enable_internet_search: bool = Field(True, alias="ENABLE_INTERNET_SEARCH")

    # Location settings
    location_default_radius_km: float = 5.0
    location_max_radius_km: float = 30.0
    location_min_events: int = 10
    location_radius_steps: list[float] = [5.0, 10.0, 15.0, 20.0, 30.0]


settings = Settings()
