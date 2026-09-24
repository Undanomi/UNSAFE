from __future__ import annotations

import asyncio
import io
import json
import os
import secrets
import stat
import struct
import tarfile
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from time import monotonic
from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status

from .models import GeneratedSource, SourceFile, SourcePatch, SourceWorkbenchCommand

MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
IGNORED_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "target",
        "venv",
    }
)
BANNED_EXECUTABLES = frozenset(
    {
        "docker",
        "mount",
        "packer",
        "podman",
        "qemu-system-x86_64",
        "reboot",
        "service",
        "ssh",
        "su",
        "sudo",
        "systemctl",
        "umount",
    }
)
NETWORK_PACKAGE_MANAGERS = frozenset(
    {"apt", "apt-get", "composer", "go", "mvn", "npm", "pip", "pip3", "pnpm", "uv", "yarn"}
)
ROOT_PACKAGE_MANAGERS = frozenset({"apt", "apt-get", "dpkg"})


@dataclass
class SandboxSession:
    source: GeneratedSource
    original: dict[str, SourceFile]
    status: str = "queued"
    container_id: str | None = None
    network_id: str | None = None
    error: str | None = None
    released: asyncio.Event = field(default_factory=asyncio.Event)
    last_activity: float = field(default_factory=monotonic)


class DockerEngine:
    def __init__(self, socket_path: str, request_timeout_seconds: float = 660) -> None:
        self.client = httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(uds=socket_path),
            base_url="http://docker",
            timeout=httpx.Timeout(request_timeout_seconds, connect=10),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = await self.client.request(method, path, **kwargs)
        if response.status_code >= 400:
            detail = response.text[:2000]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"sandbox runtime failed ({response.status_code}): {detail}",
            )
        return response


async def _make_workspace_writable(
    engine: DockerEngine,
    container_id: str,
    relative_paths: list[str] | None = None,
) -> None:
    if relative_paths:
        workspace_targets = sorted(
            {
                "/workspace/" + PurePosixPath(*path.parts[:index]).as_posix()
                for raw_path in relative_paths
                for path in [_safe_path(raw_path)]
                for index in range(1, len(path.parts) + 1)
            },
            key=lambda path: (path.count("/"), path),
        )
        commands = (
            ["chown", "65534:65534", *workspace_targets],
            ["chmod", "u+rwX", *workspace_targets],
        )
    else:
        commands = (
            ["chown", "-R", "65534:65534", "/workspace"],
            ["chmod", "-R", "u+rwX", "/workspace"],
        )
    for command in commands:
        created = await engine.request(
            "POST",
            f"/containers/{container_id}/exec",
            json={
                "AttachStderr": True,
                "AttachStdout": True,
                "Cmd": command,
                "User": "0:0",
                "WorkingDir": "/",
            },
        )
        exec_id = created.json()["Id"]
        await engine.request(
            "POST",
            f"/exec/{exec_id}/start",
            json={"Detach": False, "Tty": False},
        )
        inspected = await engine.request("GET", f"/exec/{exec_id}/json")
        if int(inspected.json().get("ExitCode", 1)) != 0:
            raise HTTPException(
                status_code=502,
                detail="could not make candidate workspace writable by sandbox user",
            )


def create_sandbox_app() -> FastAPI:
    token = os.environ.get("SOURCE_SANDBOX_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("SOURCE_SANDBOX_TOKEN must contain at least 32 characters")
    execution_image = os.environ.get("SOURCE_SANDBOX_EXECUTION_IMAGE", "debian:13-slim")
    socket_path = os.environ.get("SOURCE_SANDBOX_DOCKER_SOCKET", "/var/run/docker.sock")
    command_timeout = int(os.environ.get("SOURCE_SANDBOX_COMMAND_TIMEOUT_SECONDS", "600"))
    max_concurrent = int(os.environ.get("SOURCE_SANDBOX_MAX_CONCURRENT", "2"))
    queue_capacity = int(os.environ.get("SOURCE_SANDBOX_QUEUE_CAPACITY", "100"))
    session_ttl = int(os.environ.get("SOURCE_SANDBOX_SESSION_TTL_SECONDS", "900"))
    if max_concurrent < 1 or queue_capacity < 1 or session_ttl < 1:
        raise RuntimeError("source sandbox queue and TTL limits must be positive")
    sessions: dict[str, SandboxSession] = {}
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_capacity)
    workers: list[asyncio.Task[None]] = []
    cleanup_tasks: set[asyncio.Task[None]] = set()
    engine = DockerEngine(socket_path, request_timeout_seconds=command_timeout + 60)
    image_lock = asyncio.Lock()
    image_ready = False

    async def remove_orphaned_resources() -> None:
        filters = json.dumps({"label": ["slsg.source-sandbox=true"]})
        containers = await engine.request(
            "GET", "/containers/json", params={"all": "1", "filters": filters}
        )
        for container in containers.json():
            container_id = container.get("Id")
            if isinstance(container_id, str) and container_id:
                response = await engine.client.delete(
                    f"/containers/{container_id}", params={"force": "1", "v": "1"}
                )
                if response.status_code not in {204, 404}:
                    raise HTTPException(
                        status_code=502,
                        detail=f"could not remove orphaned sandbox container: {response.text[:1000]}",
                    )
        networks = await engine.request("GET", "/networks", params={"filters": filters})
        for network in networks.json():
            network_id = network.get("Id")
            if isinstance(network_id, str) and network_id:
                response = await engine.client.delete(f"/networks/{network_id}")
                if response.status_code not in {204, 404}:
                    raise HTTPException(
                        status_code=502,
                        detail=f"could not remove orphaned sandbox network: {response.text[:1000]}",
                    )

    async def ensure_execution_image() -> None:
        nonlocal image_ready
        if image_ready:
            return
        async with image_lock:
            if image_ready:
                return
            inspected = await engine.client.get(
                f"/images/{quote(execution_image, safe='')}/json"
            )
            if inspected.status_code == 404:
                repository, separator, tag = execution_image.rpartition(":")
                if not separator or "/" in tag:
                    repository, tag = execution_image, "latest"
                pulled = await engine.request(
                    "POST",
                    "/images/create",
                    params={"fromImage": repository, "tag": tag},
                )
                for line in pulled.text.splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict) and event.get("error"):
                        raise HTTPException(status_code=502, detail=str(event["error"])[:2000])
            elif inspected.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"could not inspect sandbox execution image: {inspected.text[:1000]}",
                )
            image_ready = True

    async def authorize(authorization: str | None = Header(default=None)) -> None:
        expected = "Bearer " + token
        if authorization is None or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    async def remove_runtime_resources(session: SandboxSession) -> None:
        if session.container_id is not None:
            container_id = session.container_id
            session.container_id = None
            try:
                await engine.client.delete(
                    f"/containers/{container_id}", params={"force": "1", "v": "1"}
                )
            except httpx.HTTPError:
                pass
        if session.network_id is not None:
            network_id = session.network_id
            session.network_id = None
            try:
                await engine.client.delete(f"/networks/{network_id}")
            except httpx.HTTPError:
                pass

    async def destroy_session(sandbox_id: str) -> bool:
        session = sessions.get(sandbox_id)
        if session is None:
            return False
        session.status = "cancelled"
        session.released.set()
        if session.container_id is None:
            sessions.pop(sandbox_id, None)
        return True

    def schedule_failed_session_cleanup(
        sandbox_id: str, session: SandboxSession
    ) -> None:
        async def cleanup() -> None:
            await asyncio.sleep(session_ttl)
            if sessions.get(sandbox_id) is session and session.status == "failed":
                sessions.pop(sandbox_id, None)

        task = asyncio.create_task(cleanup())
        cleanup_tasks.add(task)
        task.add_done_callback(cleanup_tasks.discard)

    async def prepare_session(sandbox_id: str, session: SandboxSession) -> None:
        await ensure_execution_image()
        network = await engine.request(
            "POST",
            "/networks/create",
            json={
                "Name": _network_name(sandbox_id),
                "Driver": "bridge",
                "Internal": False,
                "Attachable": False,
                "CheckDuplicate": True,
                "Labels": {
                    "slsg.source-sandbox": "true",
                    "slsg.sandbox-id": sandbox_id,
                },
            },
        )
        session.network_id = network.json()["Id"]
        response = await engine.request(
            "POST",
            "/containers/create",
            params={"name": f"slsg-source-{sandbox_id}"},
            json=_container_configuration(execution_image, sandbox_id),
        )
        session.container_id = response.json()["Id"]
        await engine.request("POST", f"/containers/{session.container_id}/start")
        # Docker's special `none` network cannot later be replaced with a bridge.
        # Start only the inert sleep process, disconnect its candidate-private bridge,
        # and upload untrusted source after the container is fully offline.
        await engine.request(
            "POST",
            f"/networks/{session.network_id}/disconnect",
            json={"Container": session.container_id, "Force": True},
        )
        await engine.request(
            "PUT",
            f"/containers/{session.container_id}/archive",
            params={"path": "/workspace", "copyUIDGID": "1"},
            content=_source_tar(session.source),
            headers={"Content-Type": "application/x-tar"},
        )
        await _make_workspace_writable(engine, session.container_id)

    async def sandbox_worker() -> None:
        while True:
            sandbox_id = await queue.get()
            session = sessions.get(sandbox_id)
            if session is None or session.status == "cancelled":
                queue.task_done()
                continue
            session.status = "preparing"
            try:
                await prepare_session(sandbox_id, session)
            except asyncio.CancelledError:
                await remove_runtime_resources(session)
                queue.task_done()
                raise
            except (HTTPException, KeyError, TypeError, ValueError, httpx.HTTPError) as error:
                await remove_runtime_resources(session)
                session.status = "failed"
                session.error = str(error)[:2000]
                schedule_failed_session_cleanup(sandbox_id, session)
                queue.task_done()
                continue
            if session.released.is_set() or sandbox_id not in sessions:
                await remove_runtime_resources(session)
                sessions.pop(sandbox_id, None)
                queue.task_done()
                continue
            session.status = "ready"
            session.last_activity = monotonic()
            try:
                while not session.released.is_set():
                    idle_seconds = monotonic() - session.last_activity
                    remaining_ttl = max(0.0, session_ttl - idle_seconds)
                    try:
                        await asyncio.wait_for(session.released.wait(), timeout=remaining_ttl)
                    except TimeoutError:
                        if monotonic() - session.last_activity >= session_ttl:
                            session.status = "expired"
                            break
            finally:
                await remove_runtime_resources(session)
                sessions.pop(sandbox_id, None)
                queue.task_done()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await remove_orphaned_resources()
        await ensure_execution_image()
        workers.extend(asyncio.create_task(sandbox_worker()) for _ in range(max_concurrent))
        yield
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        for task in cleanup_tasks:
            task.cancel()
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        await asyncio.gather(
            *(remove_runtime_resources(session) for session in list(sessions.values())),
            return_exceptions=True,
        )
        sessions.clear()
        await engine.close()

    app = FastAPI(title="SLSG Source Sandbox", version="0.1.0", lifespan=lifespan)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        await engine.request("GET", "/_ping")
        await ensure_execution_image()
        return {"status": "ok"}

    @app.post("/v1/sandboxes", dependencies=[Depends(authorize)], status_code=202)
    async def create(source: GeneratedSource) -> dict[str, str]:
        original = _validate_source(source)
        normalized_source = GeneratedSource(
            files=[original[path] for path in sorted(original)]
        )
        sandbox_id = str(uuid4())
        sessions[sandbox_id] = SandboxSession(source=normalized_source, original=original)
        try:
            queue.put_nowait(sandbox_id)
        except asyncio.QueueFull as error:
            sessions.pop(sandbox_id, None)
            raise HTTPException(status_code=429, detail="source sandbox queue is full") from error
        return {"sandbox_id": sandbox_id, "status": "queued"}

    @app.get("/v1/sandboxes", dependencies=[Depends(authorize)])
    async def sandbox_capacity() -> dict:
        counts = {
            state: sum(session.status == state for session in sessions.values())
            for state in ("queued", "preparing", "ready", "failed")
        }
        return {
            **counts,
            "max_concurrent": max_concurrent,
            "queue_capacity": queue_capacity,
        }

    @app.get("/v1/sandboxes/{sandbox_id}", dependencies=[Depends(authorize)])
    async def get_sandbox(sandbox_id: str) -> dict:
        session = sessions.get(sandbox_id)
        if session is None:
            raise HTTPException(status_code=404, detail="sandbox not found")
        if session.status in {"preparing", "ready"}:
            session.last_activity = monotonic()
        queued_ids = [
            queued_id
            for queued_id, queued in sessions.items()
            if queued.status == "queued"
        ]
        queue_position = (
            queued_ids.index(sandbox_id) + 1
            if session.status == "queued" and sandbox_id in queued_ids
            else None
        )
        return {
            "sandbox_id": sandbox_id,
            "status": session.status,
            "queue_position": queue_position,
            "error": session.error,
        }

    @app.post("/v1/sandboxes/{sandbox_id}/exec", dependencies=[Depends(authorize)])
    async def execute(sandbox_id: str, command: SourceWorkbenchCommand) -> dict:
        session = sessions.get(sandbox_id)
        if session is None:
            raise HTTPException(status_code=404, detail="sandbox not found")
        if session.status != "ready" or session.container_id is None:
            raise HTTPException(status_code=409, detail=f"sandbox is {session.status}")
        session.last_activity = monotonic()
        _validate_command(command)
        network_connected = False
        if command.network_access:
            if session.network_id is None:
                raise HTTPException(status_code=409, detail="sandbox network is unavailable")
            await engine.request(
                "POST",
                f"/networks/{session.network_id}/connect",
                json={"Container": session.container_id},
            )
            network_connected = True
        try:
            created = await engine.request(
                "POST",
                f"/containers/{session.container_id}/exec",
                json={
                    "AttachStderr": True,
                    "AttachStdout": True,
                    "Cmd": [
                        "timeout",
                        "--signal=KILL",
                        "--kill-after=5s",
                        f"{command_timeout}s",
                        *command.argv,
                    ],
                    "Env": [
                        "HOME=/tmp",
                        "LC_ALL=C.UTF-8",
                        "PATH=/usr/local/bin:/usr/bin:/bin",
                        "XDG_CACHE_HOME=/tmp/.cache",
                        "DEBIAN_FRONTEND=noninteractive",
                    ],
                    "User": "0:0" if command.run_as_root else "65534:65534",
                    "WorkingDir": "/workspace/" + command.cwd,
                },
            )
            exec_id = created.json()["Id"]
            try:
                executed = await asyncio.wait_for(
                    engine.request(
                        "POST",
                        f"/exec/{exec_id}/start",
                        json={"Detach": False, "Tty": False},
                    ),
                    timeout=command_timeout + 10,
                )
            except TimeoutError:
                await destroy_session(sandbox_id)
                return {"exit_code": 124, "stdout": "", "stderr": "", "timed_out": True}
            stdout, stderr = _demultiplex(executed.content)
            inspected = await engine.request("GET", f"/exec/{exec_id}/json")
            exit_code = int(inspected.json().get("ExitCode", 1))
            session.last_activity = monotonic()
            return {
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": exit_code in {124, 137},
            }
        finally:
            if network_connected and sandbox_id in sessions:
                try:
                    await engine.client.post(
                        f"/networks/{session.network_id}/disconnect",
                        json={"Container": session.container_id, "Force": True},
                    )
                except httpx.HTTPError:
                    pass

    @app.post("/v1/sandboxes/{sandbox_id}/patch", dependencies=[Depends(authorize)])
    async def patch_source(sandbox_id: str, patch: SourcePatch) -> dict:
        session = sessions.get(sandbox_id)
        if session is None:
            raise HTTPException(status_code=404, detail="sandbox not found")
        if session.status != "ready" or session.container_id is None:
            raise HTTPException(status_code=409, detail=f"sandbox is {session.status}")
        normalized_patch, updated_source = _validate_workbench_patch(session.source, patch)
        session.last_activity = monotonic()
        if normalized_patch.delete_paths:
            deleted = await engine.request(
                "POST",
                f"/containers/{session.container_id}/exec",
                json={
                    "AttachStderr": True,
                    "AttachStdout": True,
                    "Cmd": [
                        "rm",
                        "-f",
                        "--",
                        *[f"/workspace/{path}" for path in normalized_patch.delete_paths],
                    ],
                    "User": "65534:65534",
                    "WorkingDir": "/workspace",
                },
            )
            delete_exec_id = deleted.json()["Id"]
            delete_result = await engine.request(
                "POST",
                f"/exec/{delete_exec_id}/start",
                json={"Detach": False, "Tty": False},
            )
            delete_status = await engine.request("GET", f"/exec/{delete_exec_id}/json")
            if int(delete_status.json().get("ExitCode", 1)) != 0:
                _, stderr = _demultiplex(delete_result.content)
                raise HTTPException(
                    status_code=502,
                    detail=f"could not delete patched source files: {stderr[:1000]}",
                )
        if normalized_patch.files:
            await engine.request(
                "PUT",
                f"/containers/{session.container_id}/archive",
                params={"path": "/workspace", "copyUIDGID": "1"},
                content=_source_tar(GeneratedSource(files=normalized_patch.files)),
                headers={"Content-Type": "application/x-tar"},
            )
            # Docker archive extraction may recreate patched paths as root even when
            # tar ownership metadata is present. Restore the disposable workspace to
            # the unprivileged command user before any verification command runs.
            await _make_workspace_writable(
                engine,
                session.container_id,
                [file.path for file in normalized_patch.files],
            )
        session.source = updated_source
        session.last_activity = monotonic()
        return {
            "changed_files": sorted(file.path for file in normalized_patch.files),
            "deleted_files": sorted(normalized_patch.delete_paths),
        }

    @app.get("/v1/sandboxes/{sandbox_id}/changes", dependencies=[Depends(authorize)])
    async def changes(sandbox_id: str) -> dict:
        session = sessions.get(sandbox_id)
        if session is None:
            raise HTTPException(status_code=404, detail="sandbox not found")
        if session.status != "ready" or session.container_id is None:
            raise HTTPException(status_code=409, detail=f"sandbox is {session.status}")
        session.last_activity = monotonic()
        response = await engine.request(
            "GET",
            f"/containers/{session.container_id}/archive",
            params={"path": "/workspace"},
        )
        current = _read_workspace_tar(response.content)
        changed = [
            source_file.model_dump(mode="json")
            for path, source_file in sorted(current.items())
            if session.original.get(path) != source_file
        ]
        deleted = sorted(set(session.original) - set(current))
        return {"files": changed, "delete_paths": deleted}

    @app.delete(
        "/v1/sandboxes/{sandbox_id}",
        dependencies=[Depends(authorize)],
        status_code=204,
    )
    async def destroy(sandbox_id: str) -> Response:
        if not await destroy_session(sandbox_id):
            raise HTTPException(status_code=404, detail="sandbox not found")
        return Response(status_code=204)

    return app


def _container_configuration(image: str, sandbox_id: str) -> dict:
    return {
        "Image": image,
        "Cmd": ["sleep", "infinity"],
        "WorkingDir": "/workspace",
        "User": "0:0",
        "Env": [
            "HOME=/tmp",
            "LC_ALL=C.UTF-8",
            "PATH=/usr/local/bin:/usr/bin:/bin",
            "XDG_CACHE_HOME=/tmp/.cache",
        ],
        "Labels": {
            "slsg.source-sandbox": "true",
            "slsg.sandbox-id": sandbox_id,
        },
        "HostConfig": {
            "AutoRemove": False,
            "CapDrop": ["ALL"],
            "CapAdd": ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"],
            "Memory": 1024 * 1024 * 1024,
            "NanoCpus": 2_000_000_000,
            "NetworkMode": _network_name(sandbox_id),
            "PidsLimit": 256,
            "ReadonlyRootfs": False,
            "SecurityOpt": ["no-new-privileges"],
            "Tmpfs": {
                "/tmp": "rw,nosuid,nodev,noexec,size=256m,mode=1777",
            },
        },
    }


def _network_name(sandbox_id: str) -> str:
    return f"slsg-source-net-{sandbox_id}"


def _safe_path(raw: str) -> PurePosixPath:
    if len(raw) > 500:
        raise HTTPException(status_code=400, detail="source path exceeds size limit")
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise HTTPException(status_code=400, detail=f"unsafe source path: {raw}")
    if path.parts[0] != "contents":
        raise HTTPException(status_code=400, detail=f"source path must start with contents/: {raw}")
    return path


def _validate_workbench_patch(
    current: GeneratedSource, patch: SourcePatch
) -> tuple[SourcePatch, GeneratedSource]:
    files = {file.path: file for file in current.files}
    normalized_files: list[SourceFile] = []
    changed_paths: set[str] = set()
    for source_file in patch.files:
        path = _safe_path(source_file.path)
        if any(part in IGNORED_PARTS for part in path.parts):
            raise HTTPException(status_code=400, detail=f"patch targets ignored path: {path}")
        normalized = path.as_posix()
        if normalized in changed_paths:
            raise HTTPException(status_code=400, detail=f"duplicate patch path: {normalized}")
        changed_paths.add(normalized)
        normalized_file = source_file.model_copy(update={"path": normalized})
        if files.get(normalized) == normalized_file:
            raise HTTPException(status_code=400, detail=f"patch does not change file: {normalized}")
        files[normalized] = normalized_file
        normalized_files.append(normalized_file)

    normalized_deletes: list[str] = []
    deleted_paths: set[str] = set()
    for raw_path in patch.delete_paths:
        path = _safe_path(raw_path)
        normalized = path.as_posix()
        if normalized in changed_paths:
            raise HTTPException(
                status_code=400,
                detail=f"patch cannot replace and delete the same path: {normalized}",
            )
        if normalized in deleted_paths:
            raise HTTPException(status_code=400, detail=f"duplicate delete path: {normalized}")
        if normalized not in files:
            raise HTTPException(status_code=400, detail=f"patch delete path does not exist: {normalized}")
        deleted_paths.add(normalized)
        normalized_deletes.append(normalized)
        del files[normalized]

    if not files:
        raise HTTPException(status_code=400, detail="patch cannot delete every source file")
    updated = GeneratedSource(files=[files[path] for path in sorted(files)])
    _validate_source(updated)
    return (
        SourcePatch(files=normalized_files, delete_paths=normalized_deletes),
        updated,
    )


def _validate_source(source: GeneratedSource) -> dict[str, SourceFile]:
    total = 0
    result: dict[str, SourceFile] = {}
    for source_file in source.files:
        path = _safe_path(source_file.path).as_posix()
        if path in result:
            raise HTTPException(status_code=400, detail=f"duplicate source path: {path}")
        total += len(source_file.content.encode("utf-8"))
        if total > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail="source exceeds workbench size limit")
        result[path] = source_file.model_copy(update={"path": path})
    return result


def _source_tar(source: GeneratedSource) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        directories = sorted(
            {
                PurePosixPath(*path.parts[:index]).as_posix()
                for source_file in source.files
                for path in [_safe_path(source_file.path)]
                for index in range(1, len(path.parts))
            },
            key=lambda path: (path.count("/"), path),
        )
        for directory in directories:
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.uid = 65534
            info.gid = 65534
            info.uname = "nobody"
            info.gname = "nogroup"
            archive.addfile(info)
        for source_file in source.files:
            path = _safe_path(source_file.path).as_posix()
            content = source_file.content.encode("utf-8")
            info = tarfile.TarInfo(path)
            info.size = len(content)
            info.mode = int(source_file.mode, 8)
            info.uid = 65534
            info.gid = 65534
            info.uname = "nobody"
            info.gname = "nogroup"
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def _validate_command(command: SourceWorkbenchCommand) -> None:
    cwd = PurePosixPath(command.cwd)
    if cwd.is_absolute() or not cwd.parts or cwd.parts[0] != "contents" or ".." in cwd.parts:
        raise HTTPException(status_code=400, detail="command cwd must be contents or its child")
    executable_path = PurePosixPath(command.argv[0])
    if executable_path.is_absolute() or not executable_path.parts or ".." in executable_path.parts:
        raise HTTPException(
            status_code=400,
            detail="command executable must be a safe relative path",
        )
    executable = executable_path.name
    if executable in BANNED_EXECUTABLES:
        raise HTTPException(
            status_code=400,
            detail=f"command executable is prohibited: {executable}",
        )
    if command.run_as_root and command.argv[0] != executable:
        raise HTTPException(
            status_code=400,
            detail="root package tools must be invoked by executable name",
        )
    if command.run_as_root and executable not in ROOT_PACKAGE_MANAGERS:
        raise HTTPException(status_code=400, detail="root execution is limited to OS package tools")
    if not command.run_as_root and executable in ROOT_PACKAGE_MANAGERS:
        raise HTTPException(status_code=400, detail="OS package tools must run as root")
    if executable in {"bash", "sh", "python", "python3", "node", "ruby", "php"} and any(
        argument in {"-c", "-e", "--eval"} for argument in command.argv[1:]
    ):
        raise HTTPException(status_code=400, detail="inline code execution is not permitted")
    if command.network_access:
        if executable not in NETWORK_PACKAGE_MANAGERS:
            raise HTTPException(status_code=400, detail="network access is limited to package managers")
        if executable in {"npm", "pnpm", "yarn"} and not any(
            argument in {"--ignore-scripts", "--ignore_scripts"} for argument in command.argv
        ):
            raise HTTPException(
                status_code=400,
                detail="JavaScript package-manager network commands must disable lifecycle scripts",
            )


def _demultiplex(payload: bytes) -> tuple[str, str]:
    stdout = bytearray()
    stderr = bytearray()
    offset = 0
    while offset + 8 <= len(payload):
        stream = payload[offset]
        size = struct.unpack(">I", payload[offset + 4 : offset + 8])[0]
        offset += 8
        chunk = payload[offset : offset + size]
        offset += size
        target = stderr if stream == 2 else stdout
        remaining = MAX_OUTPUT_BYTES - len(target)
        if remaining > 0:
            target.extend(chunk[:remaining])
    if offset == 0 and payload:
        stdout.extend(payload[:MAX_OUTPUT_BYTES])
    return stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")


def _read_workspace_tar(payload: bytes) -> dict[str, SourceFile]:
    files: dict[str, SourceFile] = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if parts and parts[0] == "workspace":
                parts = parts[1:]
            if not parts or any(part in IGNORED_PARTS for part in parts):
                continue
            if not member.isfile():
                if member.issym() or member.islnk():
                    raise HTTPException(status_code=400, detail="sandbox produced a symbolic link")
                continue
            path = _safe_path(PurePosixPath(*parts).as_posix()).as_posix()
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            content = extracted.read(MAX_SOURCE_BYTES + 1)
            total += len(content)
            if len(content) > MAX_SOURCE_BYTES or total > MAX_SOURCE_BYTES:
                raise HTTPException(status_code=413, detail="sandbox changes exceed size limit")
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            mode_value = stat.S_IMODE(member.mode)
            mode = f"{mode_value:04o}"
            if mode not in {"0600", "0640", "0644", "0700", "0750", "0755"}:
                mode = "0755" if mode_value & 0o111 else "0644"
            files[path] = SourceFile(path=path, content=text, mode=mode)
    return files
