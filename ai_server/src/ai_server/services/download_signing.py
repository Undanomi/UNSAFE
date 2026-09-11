from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass


class InvalidDownloadSignatureError(ValueError):
    pass


@dataclass(frozen=True)
class SignedDownload:
    expires: int
    signature: str


class DownloadSigner:
    """Issue and validate short-lived, artifact-bound download signatures."""

    def __init__(
        self,
        secret: str,
        ttl_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._secret = secret.encode()
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def issue(self, session_id: str, build_id: str, artifact_id: str) -> SignedDownload:
        expires = int(self._clock()) + self._ttl_seconds
        return SignedDownload(
            expires=expires,
            signature=self._signature(session_id, build_id, artifact_id, expires),
        )

    def validate(
        self,
        session_id: str,
        build_id: str,
        artifact_id: str,
        expires: int,
        signature: str,
    ) -> None:
        # Treat equality as expired so no request is accepted beyond the declared second.
        if expires <= int(self._clock()):
            raise InvalidDownloadSignatureError("download URL has expired")
        expected = self._signature(session_id, build_id, artifact_id, expires)
        if not hmac.compare_digest(signature, expected):
            raise InvalidDownloadSignatureError("download URL signature is invalid")

    def _signature(
        self, session_id: str, build_id: str, artifact_id: str, expires: int
    ) -> str:
        payload = f"v1\n{session_id}\n{build_id}\n{artifact_id}\n{expires}".encode()
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
