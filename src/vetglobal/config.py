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
    max_file_size_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    max_request_body_bytes: int = Field(default=5 * 1024 * 1024 + 256 * 1024, gt=0)
    polling_timeout_seconds: float = Field(default=25.0, gt=0)
    polling_interval_seconds: float = Field(default=0.5, gt=0)

    @field_validator("allowed_frontend_origins")
    @classmethod
    def reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        if not value or "*" in value:
            raise ValueError("allowed_frontend_origins must contain explicit origins")
        return value

    def model_post_init(self, context: object) -> None:
        if self.max_request_body_bytes <= self.max_file_size_bytes:
            raise ValueError("max_request_body_bytes must exceed max_file_size_bytes")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
