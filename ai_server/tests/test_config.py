from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_server.config import Settings


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
