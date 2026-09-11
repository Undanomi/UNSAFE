from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_server.config import Settings
from ai_server.services.download_signing import (
    DownloadSigner,
    InvalidDownloadSignatureError,
)


def test_signature_is_bound_to_session_build_artifact_and_expiration() -> None:
    now = 1_800_000_000
    signer = DownloadSigner("s" * 32, 1800, clock=lambda: now)
    signed = signer.issue("session-1", "build-1", "artifact-1")

    assert signed.expires == now + 1800
    signer.validate("session-1", "build-1", "artifact-1", signed.expires, signed.signature)

    for values in (
        ("session-2", "build-1", "artifact-1"),
        ("session-1", "build-2", "artifact-1"),
        ("session-1", "build-1", "artifact-2"),
    ):
        with pytest.raises(InvalidDownloadSignatureError, match="invalid"):
            signer.validate(*values, signed.expires, signed.signature)


def test_expired_signature_is_rejected() -> None:
    current = [1_800_000_000]
    signer = DownloadSigner("s" * 32, 60, clock=lambda: current[0])
    signed = signer.issue("session-1", "build-1", "artifact-1")
    current[0] = signed.expires

    with pytest.raises(InvalidDownloadSignatureError, match="expired"):
        signer.validate(
            "session-1", "build-1", "artifact-1", signed.expires, signed.signature
        )


def test_download_signing_secret_must_be_at_least_32_characters() -> None:
    with pytest.raises(ValidationError, match="DOWNLOAD_SIGNING_SECRET"):
        Settings(download_signing_secret="too-short")
