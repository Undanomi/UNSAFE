from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SLSG AI Server"
    database_url: str
    database_pool_min_size: int = Field(default=1, ge=1, le=20)
    database_pool_max_size: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_database_pool_settings(self) -> DatabaseSettings:
        if self.database_pool_min_size > self.database_pool_max_size:
            raise ValueError("database_pool_min_size must not exceed database_pool_max_size")
        return self


class RuntimeLimitSettings(DatabaseSettings):
    """Non-secret AI server limits shared with the read-only admin dashboard."""

    gemini_max_output_tokens: int = Field(default=65536, ge=1024, le=65536)
    generation_retries: int = Field(default=3, ge=1, le=10)
    cve_min_year: int = Field(default=2024, ge=1999, le=2100)
    scenario_generation_attempts: int = Field(default=5, ge=1, le=10)
    source_generation_attempts: int = Field(default=3, ge=1, le=5)
    scenario_sync_attempts: int = Field(default=3, ge=1, le=10)
    ai_timeout_seconds: float = Field(default=600, gt=0)

    build_timeout_seconds: float = Field(default=30, gt=0)
    build_repair_max_attempts: int = Field(default=3, ge=0, le=10)
    download_url_ttl_seconds: int = Field(default=1800, ge=60, le=86400)

    scenario_chunk_size: int = Field(default=320, ge=1, le=4096)

    skills_max_active: int = Field(default=32, ge=1, le=100)
    skills_max_per_phase: int = Field(default=8, ge=1, le=20)
    skill_context_max_chars: int = Field(default=50_000, ge=1_000, le=200_000)
    skill_selection_max_chars: int = Field(default=60_000, ge=1_000, le=300_000)
    skill_selection_retries: int = Field(default=2, ge=1, le=3)
    skill_selection_max_cves: int = Field(default=3, ge=1, le=10)


class Settings(RuntimeLimitSettings):
    log_level: str = "INFO"
    source_root: Path = Path("./data/scenarios")

    ai_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    github_token: str | None = None

    build_server_url: str = "http://localhost:8080"
    build_server_token: SecretStr = Field(min_length=32)
    download_signing_secret: SecretStr = SecretStr(
        "local-development-download-signing-secret-change-me"
    )

    skills_enabled: bool = True

    @model_validator(mode="after")
    def validate_download_signing_settings(self) -> Settings:
        if len(self.download_signing_secret.get_secret_value()) < 32:
            raise ValueError("DOWNLOAD_SIGNING_SECRET must contain at least 32 characters")
        return self


class AdminSettings(RuntimeLimitSettings):
    sqladmin_username: str
    sqladmin_password: SecretStr
    sqladmin_session_secret: SecretStr
    sqladmin_secure_cookies: bool = False
    sqladmin_session_max_age_seconds: int = Field(default=28800, ge=300, le=86400)

    @model_validator(mode="after")
    def validate_admin_settings(self) -> AdminSettings:
        configured_values = (
            ("SQLADMIN_USERNAME", self.sqladmin_username),
            ("SQLADMIN_PASSWORD", self.sqladmin_password.get_secret_value()),
            ("SQLADMIN_SESSION_SECRET", self.sqladmin_session_secret.get_secret_value()),
        )
        missing = [name for name, value in configured_values if not value]
        if missing:
            raise ValueError(f"SQLAdmin settings are missing: {', '.join(missing)}")
        if len(self.sqladmin_session_secret.get_secret_value()) < 32:
            raise ValueError("SQLADMIN_SESSION_SECRET must contain at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
