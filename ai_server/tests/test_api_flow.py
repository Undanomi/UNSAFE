from __future__ import annotations

import asyncio
import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from ai_server.config import Settings
from ai_server.main import create_app
from ai_server.models import (
    Artifact,
    AttackGraph,
    AttackStep,
    MachineInformation,
    ScenarioDraft,
    SessionState,
    SessionStatus,
)
from ai_server.repository import SessionNotFoundError


class FakeSessionRepository:
    def __init__(self) -> None:
        self.states: dict[str, SessionState] = {}

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> None:
        return None

    async def create(self, owner_user_id: str) -> SessionState:
        from uuid import uuid4

        state = SessionState(session_id=str(uuid4()), owner_user_id=owner_user_id)
        self.states[state.session_id] = state.model_copy(deep=True)
        return state

    async def get(self, session_id: str) -> SessionState:
        if session_id not in self.states:
            raise SessionNotFoundError(session_id)
        return self.states[session_id].model_copy(deep=True)

    async def save(self, state: SessionState) -> SessionState:
        self.states[state.session_id] = state.model_copy(deep=True)
        return state


class FakeBuildClient:
    def __init__(self) -> None:
        self.submitted_archive: Path | None = None
        self.submitted_request: dict | None = None
        self.submitted_requests: list[dict] = []
        self.get_response: dict | None = None
        self.packer_log_response = ""

    async def submit(self, **request) -> dict:
        self.submitted_request = request
        self.submitted_requests.append(request)
        self.submitted_archive = request["archive_path"]
        with zipfile.ZipFile(self.submitted_archive) as archive:
            assert "contents/build.sh" in archive.namelist()
            assert "contents/scenario_manifest.json" in archive.namelist()
            assert "generation_manifest.json" in archive.namelist()
            assert "validation_report.json" in archive.namelist()
        return {
            "build_id": "a49f148e-1f8c-4703-97bb-d0aa180682ae",
            "status": "queued",
            "progress": 0,
        }

    async def get(self, build_id: str) -> dict:
        if self.get_response is not None:
            return {"build_id": build_id, **self.get_response}
        return {"build_id": build_id, "status": "completed", "progress": 100}

    async def packer_log(self, build_id: str) -> str:
        return self.packer_log_response

    async def artifacts(self, build_id: str) -> list[Artifact]:
        return [
            Artifact(
                artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
                artifact_type="qcow2",
                file_name="image.qcow2",
                file_size=4,
                checksum="test-checksum",
            )
        ]

    async def download(self, build_id: str, artifact_id: str) -> AsyncIterator[bytes]:
        yield b"disk"


@pytest.fixture
async def client(tmp_path: Path):
    settings = Settings(
        ai_provider="stub",
        source_root=tmp_path / "scenarios",
    )
    app = create_app(settings, repository_override=FakeSessionRepository())
    async with app.router.lifespan_context(app):
        fake_build = FakeBuildClient()
        app.state.workflow.build_client = fake_build
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client, app, fake_build


@pytest.mark.asyncio
async def test_complete_session_scenario_build_and_download(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}

    created = await http.post("/v1/sessions", headers=headers)
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    machine = {
        "name": "Nginx Engine",
        "visibility": "private",
        "theme": "Web security",
        "difficulty": "Easy",
        "needs_user_flag": True,
        "user_flag_details": "/home/student/user.txt after service enumeration",
        "needs_system_flag": False,
    }
    saved = await http.put(
        f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "ready"
    assert saved.json()["machine_information"]["operating_system"] == "Ubuntu 26.04"

    events = await http.get(f"/v1/sessions/{session_id}/scenarios/events", headers=headers)
    assert events.status_code == 200
    assert "event: scenario.started" in events.text
    assert "event: scenario.delta" in events.text
    assert "event: scenario.completed" in events.text
    assert '"target_os": "Ubuntu 26.04"' in events.text

    scenario_id = (await app.state.repository.get(session_id)).scenario.scenario_id
    accepted = await http.post(
        f"/v1/sessions/{session_id}/machines",
        json={"scenario_id": scenario_id},
        headers=headers,
    )
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "generating_code"

    for _ in range(50):
        if (await app.state.repository.get(session_id)).build_id:
            break
        await asyncio.sleep(0.01)
    assert fake_build.submitted_archive is not None

    completed = await http.get(f"/v1/sessions/{session_id}", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["download_url"].endswith(f"/v1/sessions/{session_id}/download")

    download = await http.get(f"/v1/sessions/{session_id}/download", headers=headers)
    assert download.status_code == 200
    assert download.content == b"disk"
    assert download.headers["content-disposition"] == 'attachment; filename="image.qcow2"'


@pytest.mark.asyncio
async def test_session_owner_is_not_disclosed(client) -> None:
    http, _, _ = client
    created = await http.post("/v1/sessions", headers={"X-Authenticated-User-ID": "owner"})
    session_id = created.json()["session_id"]
    response = await http.get(
        f"/v1/sessions/{session_id}", headers={"X-Authenticated-User-ID": "other"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scenario_requires_machine_information(client) -> None:
    http, _, _ = client
    session_id = (await http.post("/v1/sessions")).json()["session_id"]
    response = await http.get(f"/v1/sessions/{session_id}/scenarios/events")
    assert response.status_code == 409


async def create_failed_build_state(
    app, status: SessionStatus = SessionStatus.FAILED
) -> SessionState:
    state = await app.state.repository.create("user-123")
    state.machine_information = MachineInformation(
        name="retry",
        visibility="private",
        theme="web",
        difficulty="Easy",
        needs_user_flag=False,
        needs_system_flag=False,
    )
    state.scenario = ScenarioDraft(
        scenario_id="scenario-retry",
        title="retry",
        definition="retry",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="web-entry",
                    title="Web entry",
                    kind="web_vulnerability",
                    phase="initial_access",
                    description="training web weakness",
                    implementation_steps=["provision the weak route"],
                )
            ]
        ),
    )
    previous_source = await app.state.workflow.generator.generate_source(
        state.machine_information, state.scenario
    )
    previous_archive, previous_checksum = app.state.workflow.source_archive.create(
        state.session_id, state.scenario, previous_source
    )
    state.source_path = str(previous_archive.parent / "source")
    state.source_checksum = previous_checksum
    state.build_id = "f4122fe0-ca91-4ba6-813b-0f6acba0e8d5"
    state.build_status = "failed"
    state.error_message = "packer failed"
    state.status = status
    return await app.state.repository.save(state)


@pytest.mark.asyncio
async def test_failed_packer_build_repairs_source(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    fake_build.packer_log_response = "command before failure\nerror detail"

    accepted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "generating_code"
    assert accepted.json()["build_id"] == "f4122fe0-ca91-4ba6-813b-0f6acba0e8d5"
    assert accepted.json()["source_checksum"] == state.source_checksum
    assert accepted.json()["build_repair_attempts"] == 1

    for _ in range(50):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)
    assert fake_build.submitted_request is not None
    assert fake_build.submitted_request["idempotency_key"].startswith(
        f"ai-session-{state.session_id}-"
    )
    assert fake_build.submitted_archive is not None
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        readme = archive.read("contents/README.md").decode()
        repair_report = archive.read("repair_report.json").decode()
    assert "Repair applied for local integration testing" in readme
    assert '"changed_files"' in repair_report
    assert "contents/README.md" in repair_report
    assert "command before failure" in repair_report
    assert "error detail" in repair_report


@pytest.mark.asyncio
async def test_failed_build_is_automatically_repaired_up_to_configured_limit(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    fake_build.get_response = {
        "status": "failed",
        "progress": 100,
        "error_message": "packer failed",
    }

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    assert response.json()["status"] == "generating_code"
    assert response.json()["build_repair_attempts"] == 1

    for _ in range(200):
        if (
            len(fake_build.submitted_requests) == 3
            and state.session_id not in app.state.workflow.tasks
        ):
            break
        await asyncio.sleep(0.01)
    assert len(fake_build.submitted_requests) == 3

    exhausted = await http.get(f"/v1/sessions/{state.session_id}", headers=headers)
    assert exhausted.status_code == 200
    assert exhausted.json()["status"] == "failed"
    assert exhausted.json()["build_repair_attempts"] == 3
    assert len(fake_build.submitted_requests) == 3
    assert fake_build.submitted_archive is not None
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        readme = archive.read("contents/README.md").decode()
        repair_report = json.loads(archive.read("repair_report.json"))
    assert readme.count("Repair applied for local integration testing") == 3
    assert len(repair_report["attempts"]) == 3

    fake_build.get_response = {"status": "completed", "progress": 100}
    restarted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert restarted.status_code == 202
    assert restarted.json()["status"] == "generating_code"
    assert restarted.json()["build_repair_attempts"] == 1

    for _ in range(100):
        current = await app.state.repository.get(state.session_id)
        if current.status == SessionStatus.COMPLETED:
            break
        await asyncio.sleep(0.01)
    assert current.status == SessionStatus.COMPLETED
    assert len(fake_build.submitted_requests) == 4


def test_build_repair_limit_can_be_set_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("BUILD_REPAIR_MAX_ATTEMPTS", "2")
    assert Settings(_env_file=None).build_repair_max_attempts == 2
