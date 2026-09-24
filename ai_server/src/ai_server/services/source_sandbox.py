from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic

import httpx

from ..models import GeneratedSource, SourceFile, SourcePatch, SourceWorkbenchCommand


class SourceSandboxError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSandboxExecution:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SourceSandboxClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        token: str,
        wait_timeout_seconds: float = 240,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.wait_timeout_seconds = wait_timeout_seconds

    async def create(self, source: GeneratedSource) -> str:
        response = await self.client.post(
            f"{self.base_url}/v1/sandboxes",
            headers=self.headers,
            json=source.model_dump(mode="json"),
        )
        self._raise(response)
        sandbox_id = response.json().get("sandbox_id")
        if not isinstance(sandbox_id, str) or not sandbox_id:
            raise SourceSandboxError("source sandbox returned no sandbox_id")
        deadline = monotonic() + self.wait_timeout_seconds
        while monotonic() < deadline:
            status_response = await self.client.get(
                f"{self.base_url}/v1/sandboxes/{sandbox_id}",
                headers=self.headers,
            )
            self._raise(status_response)
            body = status_response.json()
            sandbox_status = body.get("status")
            if sandbox_status == "ready":
                return sandbox_id
            if sandbox_status in {"failed", "cancelled", "expired"}:
                await self.destroy(sandbox_id)
                raise SourceSandboxError(
                    "source sandbox preparation failed: "
                    + str(body.get("error") or sandbox_status)
                )
            await asyncio.sleep(0.5)
        await self.destroy(sandbox_id)
        raise SourceSandboxError("timed out waiting in the source sandbox queue")

    async def execute(
        self,
        sandbox_id: str,
        command: SourceWorkbenchCommand,
    ) -> SourceSandboxExecution:
        response = await self.client.post(
            f"{self.base_url}/v1/sandboxes/{sandbox_id}/exec",
            headers=self.headers,
            json=command.model_dump(mode="json"),
        )
        self._raise(response)
        body = response.json()
        return SourceSandboxExecution(
            exit_code=int(body["exit_code"]),
            stdout=str(body.get("stdout", "")),
            stderr=str(body.get("stderr", "")),
            timed_out=bool(body.get("timed_out", False)),
        )

    async def changes(self, sandbox_id: str) -> SourcePatch | None:
        response = await self.client.get(
            f"{self.base_url}/v1/sandboxes/{sandbox_id}/changes",
            headers=self.headers,
        )
        self._raise(response)
        body = response.json()
        files = [SourceFile.model_validate(item) for item in body.get("files", [])]
        delete_paths = [str(item) for item in body.get("delete_paths", [])]
        if not files and not delete_paths:
            return None
        return SourcePatch(files=files, delete_paths=delete_paths)

    async def destroy(self, sandbox_id: str) -> None:
        response = await self.client.delete(
            f"{self.base_url}/v1/sandboxes/{sandbox_id}",
            headers=self.headers,
        )
        if response.status_code == 404:
            return
        self._raise(response)

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            detail = response.text[:2000]
            raise SourceSandboxError(
                f"source sandbox returned {response.status_code}: {detail}"
            ) from error
