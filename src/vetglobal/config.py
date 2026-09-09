from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://vetglobal:vetglobal@localhost:5432/vetglobal"

    @field_validator("database_url")
    @classmethod
    def require_async_psycopg_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("database_url must use postgresql+psycopg")
        return value


class Settings(DatabaseSettings):
    """Environment-backed application configuration."""

    internal_service_token: SecretStr = Field(min_length=16)
    allowed_frontend_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"

    @field_validator("allowed_frontend_origins")
    @classmethod
    def reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        if not value or "*" in value:
            raise ValueError("allowed_frontend_origins must contain explicit origins")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
