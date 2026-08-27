from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SLSG AI Server"
    log_level: str = "INFO"
    database_url: str = "postgresql://ai_service:local-development-only@localhost:5433/ai_service"
    database_pool_min_size: int = Field(default=1, ge=1, le=20)
    database_pool_max_size: int = Field(default=10, ge=1, le=100)
    source_root: Path = Path("./data/scenarios")

    ai_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = Field(default=65536, ge=1024, le=65536)
    github_token: str | None = None
    generation_retries: int = Field(default=3, ge=1, le=10)
    cve_min_year: int = Field(default=2024, ge=1999, le=2100)
    cve_selection_attempts: int = Field(default=5, ge=1, le=10)
    source_generation_attempts: int = Field(default=3, ge=1, le=5)
    ai_timeout_seconds: float = Field(default=600, gt=0)

    build_server_url: str = "http://localhost:8080"
    build_server_token: str = "local-development-token"
    build_timeout_seconds: float = Field(default=30, gt=0)

    scenario_chunk_size: int = Field(default=320, ge=1, le=4096)


@lru_cache
def get_settings() -> Settings:
    return Settings()
