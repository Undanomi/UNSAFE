from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from ..models import Artifact


class BuildServerError(RuntimeError):
    pass


class BuildClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str, token: str) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def submit(
        self,
        *,
        scenario_id: str,
        scenario_version_id: str,
        requested_by: str,
        idempotency_key: str,
        archive_path: Path,
    ) -> dict:
        headers = {
            **self.headers,
            "X-Authenticated-User-ID": requested_by,
            "Idempotency-Key": idempotency_key,
        }
        with archive_path.open("rb") as archive:
            response = await self.client.post(
                f"{self.base_url}/v1/builds",
                headers=headers,
                data={
                    "scenario_id": scenario_id,
                    "scenario_version_id": scenario_version_id,
                },
                files={"source": ("source.zip", archive, "application/zip")},
            )
        self._raise(response)
        return response.json()

    async def get(self, build_id: str) -> dict:
        response = await self.client.get(
            f"{self.base_url}/v1/builds/{build_id}", headers=self.headers
        )
        self._raise(response)
        return response.json()

    async def packer_log(self, build_id: str) -> str:
        response = await self.client.get(
            f"{self.base_url}/v1/builds/{build_id}/logs/packer", headers=self.headers
        )
        self._raise(response)
        return response.text

    async def artifacts(self, build_id: str) -> list[Artifact]:
        response = await self.client.get(
            f"{self.base_url}/v1/builds/{build_id}/artifacts", headers=self.headers
        )
        self._raise(response)
        return [Artifact.model_validate(item) for item in response.json().get("items", [])]

    async def download(self, build_id: str, artifact_id: str) -> AsyncIterator[bytes]:
        url = f"{self.base_url}/v1/builds/{build_id}/artifacts/{artifact_id}/content"
        async with self.client.stream("GET", url, headers=self.headers) as response:
            self._raise(response)
            async for chunk in response.aiter_bytes():
                yield chunk

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            detail = response.text[:1000]
            raise BuildServerError(
                f"build server returned {response.status_code}: {detail}"
            ) from error
