from pydantic_settings import BaseSettings, SettingsConfigDict



from pydantic import BaseSettings

class DbParserSettings(BaseSettings):


settings = DbParserSettings()
    POSTGRES_URL: str

    model_config = SettingsConfigDict(
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

class db_parser_settings(BaseSettings):
    POSTGRES_URL: str

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        case_sensitive=False,
        extra="ignore",
    )        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.POSTGRES_URL.startswith("postgresql+asyncpg://"):
            self.POSTGRES_URL = self.POSTGRES_URL.replace(
                "postgresql+asyncpg://", "postgresql://"
            )


settings = db_parser_settings()
