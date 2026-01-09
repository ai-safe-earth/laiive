from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    neo4j_uri: str = Field(..., alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openrouter_api_key: str = Field(..., alias="OPENROUTER_API_KEY")
    query_builder_model: str = Field("gpt-4o", alias="OPENAI_MODEL")
    router_model: str = Field("gpt-4o", alias="OPENAI_MODEL")
    conversation_model: str = Field("gpt-4o", alias="OPENAI_MODEL")
    embeddings_model: str = Field("text-embedding-3-small", alias="EMBEDDINGS_MODEL")
    guardrail_model: str = Field("meta-llama/llama-guard-3-8b", alias="GUARDRAIL_MODEL")

    # ares_api_key: Optional[str] = Field(None, alias="ARES_API_KEY")


    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
