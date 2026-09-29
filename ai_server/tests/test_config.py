from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_server.config import AdminSettings, Settings


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_settings_require_build_server_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUILD_SERVER_TOKEN")

    with pytest.raises(ValidationError, match="build_server_token"):
        Settings(_env_file=None)


def test_settings_reject_short_build_server_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BUILD_SERVER_TOKEN", "local-development-token")

    with pytest.raises(ValidationError, match="at least 32"):
        Settings(_env_file=None)


def test_admin_settings_do_not_require_build_server_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BUILD_SERVER_TOKEN")

    settings = AdminSettings(
        sqladmin_username="admin-user",
        sqladmin_password="a-long-admin-password",
        sqladmin_session_secret="test-session-secret-that-is-at-least-32-characters",
        _env_file=None,
    )

    assert settings.sqladmin_username == "admin-user"


def test_settings_normalize_supported_ai_provider() -> None:
    settings = Settings(ai_provider=" OpenAI ", _env_file=None)

    assert settings.ai_provider == "openai"
    assert settings.openai_model == "gpt-5.6-luna"


def test_settings_reject_unknown_ai_provider() -> None:
    with pytest.raises(ValidationError, match="AI_PROVIDER must be one of"):
        Settings(ai_provider="unknown", _env_file=None)


def test_settings_reject_invalid_rockyou_window() -> None:
    with pytest.raises(ValidationError, match="ROCKYOU_MIN_LINE"):
        Settings(rockyou_min_line=200, rockyou_max_line=100, _env_file=None)


def test_active_session_limit_defaults_to_one_and_reads_environment(monkeypatch) -> None:
    monkeypatch.delenv("MAX_ACTIVE_SESSIONS_PER_USER", raising=False)
    assert Settings(_env_file=None).max_active_sessions_per_user == 1
    monkeypatch.setenv("MAX_ACTIVE_SESSIONS_PER_USER", "2")
    assert Settings(_env_file=None).max_active_sessions_per_user == 2
    monkeypatch.setenv("MAX_ACTIVE_SESSIONS_PER_USER", "0")
    with pytest.raises(ValidationError, match="max_active_sessions_per_user"):
        Settings(_env_file=None)
