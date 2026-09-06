from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SLSG AI Server"
    log_level: str = "INFO"
    database_url: str = "postgresql://ai_service:local-development-only@localhost:5433/ai_service"
    database_pool_min_size: int = Field(default=1, ge=1, le=20)
    database_pool_max_size: int = Field(default=10, ge=1, le=100)
    source_root: Path = Path("./data/scenarios")

    sqladmin_enabled: bool = False
    sqladmin_username: str | None = None
    sqladmin_password: SecretStr | None = None
    sqladmin_session_secret: SecretStr | None = None
    sqladmin_secure_cookies: bool = False
    sqladmin_session_max_age_seconds: int = Field(default=28800, ge=300, le=86400)

    ai_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = Field(default=65536, ge=1024, le=65536)
    github_token: str | None = None
    generation_retries: int = Field(default=3, ge=1, le=10)
    cve_min_year: int = Field(default=2024, ge=1999, le=2100)
    scenario_generation_attempts: int = Field(default=5, ge=1, le=10)
    source_generation_attempts: int = Field(default=3, ge=1, le=5)
    ai_timeout_seconds: float = Field(default=600, gt=0)

    build_server_url: str = "http://localhost:8080"
    build_server_token: str = "local-development-token"
    build_timeout_seconds: float = Field(default=30, gt=0)
    build_repair_max_attempts: int = Field(default=3, ge=0, le=10)

    scenario_chunk_size: int = Field(default=320, ge=1, le=4096)

    @model_validator(mode="after")
    def validate_database_and_admin_settings(self) -> Settings:
        if self.database_pool_min_size > self.database_pool_max_size:
            raise ValueError("database_pool_min_size must not exceed database_pool_max_size")
        if not self.sqladmin_enabled:
            return self
        configured_values = (
            ("SQLADMIN_USERNAME", self.sqladmin_username),
            ("SQLADMIN_PASSWORD", self.sqladmin_password),
            ("SQLADMIN_SESSION_SECRET", self.sqladmin_session_secret),
        )
        missing = []
        for name, value in configured_values:
            secret_value = value.get_secret_value() if isinstance(value, SecretStr) else value
            if not secret_value:
                missing.append(name)
        if missing:
            raise ValueError(
                f"SQLAdmin is enabled but these settings are missing: {', '.join(missing)}"
            )
        assert self.sqladmin_session_secret is not None
        if len(self.sqladmin_session_secret.get_secret_value()) < 32:
            raise ValueError("SQLADMIN_SESSION_SECRET must contain at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
