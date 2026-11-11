"""Application configuration loaded via pydantic-settings."""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for BD Job Hunter."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "development"
    SECRET_KEY: str
    DATABASE_URL: str = "sqlite:///./data/app.db"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = ""
    MAX_UPLOAD_MB: int = 5
    JOBICY_ENABLED: bool = True
    REMOTEOK_ENABLED: bool = True
    SOURCE_USER_AGENT: str = "bd-job-hunter/0.1 (personal project; contact: you@example.com)"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        """Fail fast with a clear message if SECRET_KEY is empty."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(
                "SECRET_KEY must not be empty. Set a non-empty SECRET_KEY in your .env file."
            )
        return cleaned

    @model_validator(mode="after")
    def validate_production_secret_key(self) -> "Settings":
        """Require SECRET_KEY to be at least 32 characters in production."""
        if self.ENV.lower() == "production" and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
