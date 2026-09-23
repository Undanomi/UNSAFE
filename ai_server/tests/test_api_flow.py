from __future__ import annotations

import asyncio
import json
import re
import zipfile
from pathlib import Path

import httpx
import pytest

from ai_server.config import Settings
from ai_server.main import create_app
from ai_server.models import (
    Artifact,
    AttackGraph,
    AttackStep,
    GeneratedSource,
    MachineInformation,
    ScenarioDraft,
    ScenarioReview,
    ScenarioReviewFinding,
    ScenarioRevision,
    SessionState,
    SessionStatus,
    SourceFile,
    SourcePatch,
    SourceReview,
    SourceReviewFinding,
)
from ai_server.repository import SessionNotFoundError
from ai_server.services.errors import ScenarioInputRevisionRequiredError
from ai_server.services.workflow import MachineWorkflow, _source_review_scope_invalidation_reasons


class FakeAsyncStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self):
        yield self.content


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
        self.requested_build_ids: list[str] = []
        self.packer_log_response = ""
        self.download_requests: list[tuple[str, str]] = []
        self.download_headers: list[tuple[str | None, str | None]] = []
        self.cancelled_build_ids: list[str] = []

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
        self.requested_build_ids.append(build_id)
        if self.get_response is not None:
            return {"build_id": build_id, **self.get_response}
        return {
            "build_id": build_id,
            "status": "completed",
            "progress": 100,
            "machine_password": "test-generated-machine-password",
        }

    async def cancel(self, build_id: str) -> None:
        self.cancelled_build_ids.append(build_id)

    async def packer_log(self, build_id: str) -> str:
        return self.packer_log_response

    async def artifacts(self, build_id: str) -> list[Artifact]:
        return [
            Artifact(
                artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
                artifact_type="zip",
                file_name="3a3c16bd-6d41-49e1-98c3-927138f8a271.zip",
                file_size=7,
                checksum="test-checksum",
            )
        ]

    async def open_download(
        self,
        build_id: str,
        artifact_id: str,
        *,
        range_header: str | None = None,
        if_range: str | None = None,
    ) -> httpx.Response:
        self.download_requests.append((build_id, artifact_id))
        self.download_headers.append((range_header, if_range))
        request = httpx.Request("GET", "http://build.test/artifact")
        headers = {
            "Content-Type": "application/zip",
            "Accept-Ranges": "bytes",
        }
        if range_header == "bytes=2-" and if_range is None:
            headers.update({"Content-Length": "5", "Content-Range": "bytes 2-6/7"})
            return httpx.Response(
                206, headers=headers, stream=FakeAsyncStream(b"chive"), request=request
            )
        if range_header == "bytes=99-":
            headers.update({"Content-Length": "0", "Content-Range": "bytes */7"})
            return httpx.Response(
                416, headers=headers, stream=FakeAsyncStream(b""), request=request
            )
        headers["Content-Length"] = "7"
        return httpx.Response(
            200, headers=headers, stream=FakeAsyncStream(b"archive"), request=request
        )


def test_distribution_artifact_does_not_fallback_to_qcow2() -> None:
    old_artifact = Artifact(
        artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
        artifact_type="qcow2",
        file_name="image.qcow2",
        file_size=4,
        checksum="test-checksum",
    )
    with pytest.raises(RuntimeError, match="without a zip"):
        MachineWorkflow._distribution_artifact([old_artifact])


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
    assert saved.json()["machine_information"]["operating_system"] == "Debian 13.7.0"

    events = await http.get(f"/v1/sessions/{session_id}/scenarios/events", headers=headers)
    assert events.status_code == 200
    assert "event: scenario.started" in events.text
    assert "event: scenario.delta" in events.text
    assert "event: scenario.completed" in events.text
    assert '"target_os": "Debian 13.7.0"' in events.text

    scenario_state = await app.state.repository.get(session_id)
    scenario = scenario_state.scenario
    assert scenario is not None
    assert scenario_state.scenario_generation_attempts == 1
    assert scenario_state.scenario_generation_attempt_limit == 5
    assert scenario.user_flag is not None
    assert re.fullmatch(r"flag\{user_[0-9a-f]{32}\}", scenario.user_flag)
    assert scenario.system_flag is None
    assert scenario.user_flag not in events.text
    version_root = app.state.workflow.source_archive.root / session_id / "v1"
    assert (version_root / "scenario.md").read_text() == scenario.definition.rstrip() + "\n"
    assert (version_root / "attempts/000001/scenario.md").is_file()
    persisted_review = json.loads((version_root / "scenario_review.json").read_text())
    assert persisted_review["approved"] is True
    scenario_id = scenario.scenario_id
    accepted = await http.post(
        f"/v1/sessions/{session_id}/machines",
        json={"scenario_id": scenario_id},
        headers=headers,
    )
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "generating_code"
    assert accepted.json()["user_flag"] == scenario.user_flag
    assert accepted.json()["system_flag"] is None

    for _ in range(50):
        if (await app.state.repository.get(session_id)).build_id:
            break
        await asyncio.sleep(0.01)
    assert fake_build.submitted_archive is not None
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        provision = archive.read("contents/scripts/provision.sh").decode()
    assert scenario.user_flag in provision

    completed = await http.get(f"/v1/sessions/{session_id}", headers=headers)
    assert completed.status_code == 200
    assert completed.headers["cache-control"] == "private, no-store"
    assert completed.json()["status"] == "completed"
    assert completed.json()["machine_access"] == {
        "username": "provisioner",
        "password": "test-generated-machine-password",
    }
    completed_state = await app.state.repository.get(session_id)
    assert completed_state.source_generation_attempts == 1
    assert completed_state.source_generation_attempt_limit == 12

    guidance = await http.post(
        f"/v1/sessions/{session_id}/guidance",
        json={"acquired_flags": []},
        headers=headers,
    )
    assert guidance.status_code == 200
    assert guidance.headers["cache-control"] == "private, no-store"
    assert guidance.json()["items"]
    assert {item["target_flag"] for item in guidance.json()["items"]} == {"user"}
    assert scenario.user_flag not in guidance.text

    denied_guidance = await http.post(
        f"/v1/sessions/{session_id}/guidance",
        json={"acquired_flags": []},
        headers={"X-Authenticated-User-ID": "other"},
    )
    assert denied_guidance.status_code == 404

    completed_state.artifact = Artifact(
        artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
        artifact_type="tar.zst",
        file_name="slsg-machine.tar.zst",
        file_size=9,
        checksum="legacy-checksum",
    )
    await app.state.repository.save(completed_state)
    refreshed = await http.get(f"/v1/sessions/{session_id}", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["artifact"] == {
        "artifact_id": "3a3c16bd-6d41-49e1-98c3-927138f8a271",
        "artifact_type": "zip",
        "file_name": "3a3c16bd-6d41-49e1-98c3-927138f8a271.zip",
        "file_size": 7,
        "checksum": "test-checksum",
    }
    download_url = refreshed.json()["download_url"]
    assert f"/v1/sessions/{session_id}/download?" in download_url
    assert "expires=" in download_url
    assert "signature=" in download_url

    unsigned = await http.get(f"/v1/sessions/{session_id}/download")
    assert unsigned.status_code == 422

    tampered = await http.get(download_url + "0")
    assert tampered.status_code == 403
    assert fake_build.download_requests == []

    download = await http.get(download_url)
    assert download.status_code == 200
    assert download.content == b"archive"
    assert download.headers["content-type"] == "application/zip"
    assert download.headers["content-disposition"] == (
        'attachment; filename="3a3c16bd-6d41-49e1-98c3-927138f8a271.zip"'
    )
    assert download.headers["content-length"] == "7"
    assert fake_build.download_requests == [
        (
            "a49f148e-1f8c-4703-97bb-d0aa180682ae",
            "3a3c16bd-6d41-49e1-98c3-927138f8a271",
        )
    ]

    denied = await http.post(
        f"/v1/sessions/{session_id}/download-url",
        headers={"X-Authenticated-User-ID": "other"},
    )
    assert denied.status_code == 404

    issued = await http.post(f"/v1/sessions/{session_id}/download-url", headers=headers)
    assert issued.status_code == 200
    assert issued.headers["cache-control"] == "private, no-store"
    assert "signature=" in issued.json()["download_url"]
    assert issued.json()["expires_at"]

    ranged = await http.get(
        issued.json()["download_url"],
        headers={"Range": "bytes=2-", "If-Range": '"test-checksum"'},
    )
    assert ranged.status_code == 206
    assert ranged.content == b"chive"
    assert ranged.headers["content-range"] == "bytes 2-6/7"
    assert ranged.headers["accept-ranges"] == "bytes"
    assert ranged.headers["etag"] == '"test-checksum"'
    assert fake_build.download_headers[-1] == ("bytes=2-", None)

    changed = await http.get(
        issued.json()["download_url"],
        headers={"Range": "bytes=2-", "If-Range": '"different-checksum"'},
    )
    assert changed.status_code == 200
    assert changed.content == b"archive"
    assert fake_build.download_headers[-1] == (None, None)

    unsatisfiable = await http.get(issued.json()["download_url"], headers={"Range": "bytes=99-"})
    assert unsatisfiable.status_code == 416
    assert unsatisfiable.headers["content-range"] == "bytes */7"


@pytest.mark.asyncio
async def test_session_owner_is_not_disclosed(client) -> None:
    http, _, _ = client
    created = await http.post("/v1/sessions", headers={"X-Authenticated-User-ID": "owner"})
    session_id = created.json()["session_id"]
    response = await http.get(
        f"/v1/sessions/{session_id}", headers={"X-Authenticated-User-ID": "other"}
    )
    assert response.status_code == 404

    missing_identity = await http.get(f"/v1/sessions/{session_id}")
    assert missing_identity.status_code == 404


@pytest.mark.asyncio
async def test_scenario_requires_machine_information(client) -> None:
    http, _, _ = client
    session_id = (await http.post("/v1/sessions")).json()["session_id"]
    response = await http.get(f"/v1/sessions/{session_id}/scenarios/events")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cancel_stops_scenario_task_and_persists_cancelled_state(client) -> None:
    http, app, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    session_id = (await http.post("/v1/sessions", headers=headers)).json()["session_id"]
    machine = {
        "name": "Cancellation test",
        "visibility": "private",
        "theme": "Web security",
        "difficulty": "Easy",
        "needs_user_flag": False,
        "needs_system_flag": False,
    }
    assert (
        await http.put(
            f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers
        )
    ).status_code == 200

    started = asyncio.Event()
    blocked = asyncio.Event()

    async def generate_scenario(*_args, **_kwargs):
        started.set()
        await blocked.wait()
        raise AssertionError("cancelled generation must not complete")

    app.state.scenarios.generator.generate_scenario = generate_scenario
    app.state.scenarios.ensure_started(session_id)
    await asyncio.wait_for(started.wait(), timeout=1)

    cancelled = await http.post(f"/v1/sessions/{session_id}/cancel", headers=headers)

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert session_id not in app.state.scenarios.tasks
    persisted = await app.state.repository.get(session_id)
    assert persisted.status == SessionStatus.CANCELLED

    events = await http.get(f"/v1/sessions/{session_id}/scenarios/events", headers=headers)
    assert events.status_code == 200
    assert "event: scenario.cancelled" in events.text
    assert session_id not in app.state.scenarios.tasks


@pytest.mark.asyncio
async def test_cancel_requests_active_build_cancellation(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await app.state.repository.create("user-123")
    state.status = SessionStatus.BUILDING
    state.build_id = "a49f148e-1f8c-4703-97bb-d0aa180682ae"
    state.build_status = "building"
    await app.state.repository.save(state)

    cancelled = await http.post(f"/v1/sessions/{state.session_id}/cancel", headers=headers)

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["build_status"] == "cancelled"
    assert fake_build.cancelled_build_ids == [state.build_id]

    fake_build.get_response = {"status": "building", "progress": 80}
    refreshed = await http.get(f"/v1/sessions/{state.session_id}", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "cancelled"
    assert refreshed.json()["build_status"] == "cancelled"


@pytest.mark.asyncio
async def test_get_marks_orphaned_running_build_cancelled_without_status_synchronization(
    client,
) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await app.state.repository.create("user-123")
    state.status = SessionStatus.BUILDING
    state.build_id = "a49f148e-1f8c-4703-97bb-d0aa180682ae"
    state.build_status = "building"
    await app.state.repository.save(state)
    fake_build.get_response = {"status": "completed", "progress": 100}

    response = await http.get(f"/v1/sessions/{state.session_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["build_status"] == "cancelled"
    assert fake_build.cancelled_build_ids == [state.build_id]
    assert fake_build.requested_build_ids == []


@pytest.mark.asyncio
async def test_editing_cancelled_build_resets_generated_state_for_fresh_build(client) -> None:
    http, app, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app, status=SessionStatus.CANCELLED)
    state.build_status = "cancelled"
    state.build_progress = 47
    state.build_repair_attempts = 2
    state.build_repair_attempt_limit = 3
    await app.state.repository.save(state)

    updated = await http.put(
        f"/v1/sessions/{state.session_id}/machine-information",
        headers=headers,
        json={
            **state.machine_information.model_dump(mode="json"),
            "name": "edited after cancellation",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "ready"
    persisted = await app.state.repository.get(state.session_id)
    assert persisted.machine_information is not None
    assert persisted.machine_information.name == "edited after cancellation"
    assert persisted.scenario is None
    assert persisted.source_path is None
    assert persisted.source_checksum is None
    assert persisted.build_id is None
    assert persisted.build_status is None
    assert persisted.build_progress == 0
    assert persisted.build_repair_attempts == 0
    assert persisted.build_repair_attempt_limit == 0
    assert persisted.artifact is None
    assert persisted.machine_access is None


@pytest.mark.asyncio
async def test_scenario_input_revision_error_is_returned_as_structured_event(client) -> None:
    http, app, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    session_id = (await http.post("/v1/sessions", headers=headers)).json()["session_id"]
    await http.put(
        f"/v1/sessions/{session_id}/machine-information",
        headers=headers,
        json={
            "name": "Unstable RCE",
            "visibility": "private",
            "theme": "Web security",
            "difficulty": "Easy",
            "needs_user_flag": False,
            "needs_system_flag": False,
        },
    )

    async def reject_input(*_args, **_kwargs):
        raise ScenarioInputRevisionRequiredError(
            "Stable RCE is not justified at the requested difficulty.",
            [
                {
                    "step_id": "exploit-cve",
                    "severity": "error",
                    "category": "unsupported_assumption",
                    "evidence": "The required exploit is not established.",
                    "remediation": "Raise the difficulty or relax the required impact.",
                }
            ],
        )

    app.state.scenarios.generator.generate_scenario = reject_input
    events = await http.get(
        f"/v1/sessions/{session_id}/scenarios/events",
        headers=headers,
    )

    assert events.status_code == 200
    assert "event: scenario.error" in events.text
    assert '"code": "scenario_input_revision_required"' in events.text
    assert "Raise the difficulty or relax the required impact." in events.text
    failed = await app.state.repository.get(session_id)
    assert failed.status == SessionStatus.FAILED
    assert failed.error_message == "Stable RCE is not justified at the requested difficulty."


@pytest.mark.asyncio
async def test_machine_information_promotes_cve_from_flag_details(client) -> None:
    http, _, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    session_id = (await http.post("/v1/sessions", headers=headers)).json()["session_id"]
    response = await http.put(
        f"/v1/sessions/{session_id}/machine-information",
        headers=headers,
        json={
            "name": "Nginx Engine",
            "visibility": "非公開",
            "theme": "Web セキュリティ",
            "difficulty": "Very Easy",
            "needs_user_flag": True,
            "user_flag_details": "CVE-2026-42533を用いたRCE。",
            "needs_system_flag": False,
            "system_flag_details": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["machine_information"]["cve_ids"] == ["CVE-2026-42533"]


@pytest.mark.asyncio
async def test_repeated_machine_information_cancels_stale_scenario_state(
    client,
) -> None:
    http, app, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    session_id = (await http.post("/v1/sessions", headers=headers)).json()["session_id"]
    machine = {
        "name": "Nginx Engine",
        "visibility": "非公開",
        "theme": "Web セキュリティ",
        "difficulty": "Very Easy",
        "needs_user_flag": True,
        "user_flag_details": "CVE-2026-42533を用いたRCE。",
        "needs_system_flag": False,
        "system_flag_details": "",
    }
    first = await http.put(
        f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers
    )
    assert first.status_code == 200
    state = await app.state.repository.get(session_id)
    state.status = SessionStatus.GENERATING_SCENARIO
    await app.state.repository.save(state)

    repeated = await http.put(
        f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers
    )

    assert repeated.status_code == 409
    persisted = await app.state.repository.get(session_id)
    assert persisted.machine_information is not None
    assert persisted.machine_information.cve_ids == ["CVE-2026-42533"]
    assert persisted.status == SessionStatus.CANCELLED


@pytest.mark.asyncio
async def test_repeated_machine_information_starts_a_fresh_generation_cycle(client) -> None:
    http, app, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    session_id = (await http.post("/v1/sessions", headers=headers)).json()["session_id"]
    machine = {
        "name": "Retry scenario",
        "visibility": "private",
        "theme": "Web security",
        "difficulty": "Easy",
        "needs_user_flag": False,
        "needs_system_flag": False,
    }
    await http.put(f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers)
    state = await app.state.repository.get(session_id)
    state.status = SessionStatus.FAILED
    state.scenario_generation_attempts = 5
    state.scenario_generation_attempt_limit = 5
    state.source_generation_attempts = 2
    state.source_generation_attempt_limit = 12
    await app.state.repository.save(state)

    repeated = await http.put(
        f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers
    )

    assert repeated.status_code == 200
    persisted = await app.state.repository.get(session_id)
    assert persisted.status == SessionStatus.READY
    assert persisted.scenario_generation_attempts == 0
    assert persisted.scenario_generation_attempt_limit == 0
    assert persisted.source_generation_attempts == 0
    assert persisted.source_generation_attempt_limit == 0


@pytest.mark.asyncio
async def test_machine_information_change_requires_stale_generation_to_cancel_first(client) -> None:
    http, app, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    session_id = (await http.post("/v1/sessions", headers=headers)).json()["session_id"]
    machine = {
        "name": "Original",
        "visibility": "private",
        "theme": "Web",
        "difficulty": "Easy",
        "needs_user_flag": False,
        "user_flag_details": "",
        "needs_system_flag": False,
        "system_flag_details": "",
    }
    await http.put(f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers)
    state = await app.state.repository.get(session_id)
    state.status = SessionStatus.GENERATING_SCENARIO
    state.scenario_generation_attempts = 4
    state.scenario_generation_attempt_limit = 5
    state.source_generation_attempts = 3
    state.source_generation_attempt_limit = 12
    await app.state.repository.save(state)

    changed = await http.put(
        f"/v1/sessions/{session_id}/machine-information",
        json={**machine, "name": "Changed"},
        headers=headers,
    )

    assert changed.status_code == 409
    cancelled = await app.state.repository.get(session_id)
    assert cancelled.status == SessionStatus.CANCELLED

    changed = await http.put(
        f"/v1/sessions/{session_id}/machine-information",
        json={**machine, "name": "Changed"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "ready"
    persisted = await app.state.repository.get(session_id)
    assert persisted.machine_information is not None
    assert persisted.machine_information.name == "Changed"
    assert persisted.scenario is None
    assert persisted.scenario_generation_attempts == 0
    assert persisted.scenario_generation_attempt_limit == 0
    assert persisted.source_generation_attempts == 0
    assert persisted.source_generation_attempt_limit == 0


async def create_failed_build_state(
    app,
    status: SessionStatus = SessionStatus.FAILED,
    *,
    semantic_review_approved: bool = False,
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
    if semantic_review_approved:
        previous_checksum = app.state.workflow.source_archive.record_semantic_review(
            previous_archive,
            {
                "kind": "source_semantic_review",
                "status": "pass",
                "error_message": "The source passed semantic review.",
                "summary": {"passed": 1, "failed": 0, "warnings": 0},
                "checks": [],
            },
            approved=True,
        )
    state.source_path = str(previous_archive.parent / "source")
    state.source_checksum = previous_checksum
    state.build_id = "f4122fe0-ca91-4ba6-813b-0f6acba0e8d5"
    state.build_status = "failed"
    state.error_message = "packer failed"
    state.status = status
    return await app.state.repository.save(state)


@pytest.mark.asyncio
async def test_build_repair_reuses_prior_approved_review_scope(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app, semantic_review_approved=True)
    review_contexts: list[dict | None] = []

    async def review(
        _machine,
        _scenario,
        _current,
        _skills=None,
        reconsideration=None,
    ) -> SourceReview:
        review_contexts.append(reconsideration)
        return SourceReview(
            approved=False,
            summary="A late unrelated concern was raised.",
            findings=[
                SourceReviewFinding(
                    step_id="web-entry",
                    severity="error",
                    category="implementation_mismatch",
                    affected_files=["contents/app/unmodified.php"],
                    evidence="This file was not changed by the build repair.",
                    remediation="Do not reopen unrelated source during build repair.",
                )
            ],
        )

    app.state.workflow.generator.review_source = review
    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert len(review_contexts) == 1
    assert review_contexts[0] is not None
    assert review_contexts[0]["kind"] == "source_repair_verification"
    assert review_contexts[0]["repair_origin"] == "build_failure"
    assert fake_build.submitted_archive is not None
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        report = json.loads(archive.read("repair_report.json"))
    assert report["source_semantic_review"]["status"] == "approved"
    assert report["source_semantic_review"]["report"]["checks"][0]["status"] == "warn"


@pytest.mark.asyncio
async def test_get_session_does_not_restart_failed_build(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    state.build_repair_attempt_limit = 3
    await app.state.repository.save(state)
    fake_build.get_response = {
        "status": "failed",
        "progress": 100,
        "error_message": "packer still failed",
    }

    response = await http.get(f"/v1/sessions/{state.session_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["build_repair_attempts"] == 0
    assert fake_build.submitted_requests == []
    assert state.session_id not in app.state.workflow.tasks


@pytest.mark.asyncio
async def test_download_url_does_not_restart_failed_build(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    state.build_repair_attempt_limit = 3
    await app.state.repository.save(state)
    fake_build.get_response = {
        "status": "failed",
        "progress": 100,
        "error_message": "packer still failed",
    }

    response = await http.post(f"/v1/sessions/{state.session_id}/download-url", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "machine is not ready"
    assert fake_build.submitted_requests == []
    assert state.session_id not in app.state.workflow.tasks


@pytest.mark.asyncio
async def test_failed_packer_build_repairs_source(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    assert state.scenario is not None
    authoritative_graph = state.scenario.attack_graph
    fake_build.packer_log_response = "+ command before failure\nerror detail"

    async def synchronize_scenario(machine, scenario, current) -> ScenarioRevision:
        rewritten_graph = scenario.attack_graph.model_copy(
            update={
                "steps": [
                    step.model_copy(update={"description": "rewritten to match repaired code"})
                    for step in scenario.attack_graph.steps
                ]
            }
        )
        return ScenarioRevision(
            scenario_description="Updated player introduction after source repair.",
            definition="retry synchronized with repaired source",
            attack_graph=rewritten_graph,
            summary="Updated the scenario after source repair.",
        )

    app.state.workflow.generator.synchronize_scenario = synchronize_scenario

    accepted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "generating_code"
    assert accepted.json()["build_id"] == "f4122fe0-ca91-4ba6-813b-0f6acba0e8d5"
    assert accepted.json()["source_checksum"] == state.source_checksum
    assert accepted.json()["build_repair_attempts"] == 0

    for _ in range(50):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)
    assert fake_build.submitted_request is not None
    submitted_state = await app.state.repository.get(state.session_id)
    assert submitted_state.build_repair_attempts == 1
    assert submitted_state.build_repair_attempt_limit == 3
    assert submitted_state.scenario is not None
    assert submitted_state.scenario.attack_graph == authoritative_graph
    assert (
        submitted_state.scenario.scenario_description
        == "Updated player introduction after source repair."
    )
    assert submitted_state.scenario.definition == "retry synchronized with repaired source"
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
    assert '"failed_commands"' in repair_report
    assert '"failure_log_context"' in repair_report
    assert '"scenario_sync_status": "approved"' in repair_report


@pytest.mark.asyncio
async def test_scenario_review_feedback_revises_scenario_without_another_code_patch(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_reports: list[dict] = []
    sync_feedback: list[dict | None] = []
    review_calls = 0

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_reports.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + "\nSingle source repair.\n",
                    mode=readme.mode,
                )
            ]
        )

    async def synchronize(_machine, scenario, _current, review_feedback=None) -> ScenarioRevision:
        sync_feedback.append(review_feedback)
        return ScenarioRevision(
            scenario_description="Reviewed scenario introduction.",
            definition="review feedback applied" if review_feedback else "initial synchronization",
            attack_graph=scenario.attack_graph,
            summary="Scenario synchronized without changing source.",
        )

    async def review(_machine, _scenario, review_context="generation") -> ScenarioReview:
        assert review_context == "source_sync"
        nonlocal review_calls
        review_calls += 1
        if review_calls == 1:
            return ScenarioReview(
                approved=False,
                summary="The scenario omits the negative control.",
                findings=[
                    ScenarioReviewFinding(
                        step_id="web-entry",
                        severity="error",
                        category="acceptance_test_gap",
                        evidence="No negative control is described.",
                        remediation="Describe the negative control in the scenario.",
                    )
                ],
            )
        return ScenarioReview(approved=True, summary="Scenario feedback was applied.")

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.synchronize_scenario = synchronize
    app.state.workflow.generator.review_scenario = review

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert len(repair_reports) == 1
    assert sync_feedback[0] is None
    assert sync_feedback[1]["kind"] == "scenario_sync_review"
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.scenario is not None
    assert submitted.scenario.definition == "review feedback applied"


@pytest.mark.asyncio
async def test_repeated_scenario_rejection_never_routes_feedback_to_code_repair(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_reports: list[dict] = []
    feedback_seen: list[dict | None] = []

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_reports.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[SourceFile(path=readme.path, content=readme.content + "\nrepair\n")]
        )

    async def synchronize(_machine, scenario, _current, review_feedback=None) -> ScenarioRevision:
        feedback_seen.append(review_feedback)
        return ScenarioRevision(
            scenario_description="Still rejected.",
            definition="still rejected",
            attack_graph=scenario.attack_graph,
            summary="Attempted scenario-only repair.",
        )

    async def reject(_machine, _scenario, review_context="generation") -> ScenarioReview:
        assert review_context == "source_sync"
        return ScenarioReview(
            approved=False,
            summary="Scenario remains inconsistent.",
            findings=[
                ScenarioReviewFinding(
                    severity="error",
                    category="semantic_mismatch",
                    evidence=(
                        "Scenario prose mentions implementation and generated code, but is "
                        "internally inconsistent."
                    ),
                    remediation="Revise scenario prose only.",
                )
            ],
        )

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.synchronize_scenario = synchronize
    app.state.workflow.generator.review_scenario = reject
    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        current = await app.state.repository.get(state.session_id)
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert current.status == SessionStatus.FAILED
    assert len(repair_reports) == 1
    assert len(feedback_seen) == 2
    assert feedback_seen[0] is None
    assert all(feedback is not None for feedback in feedback_seen[1:])
    assert fake_build.submitted_request is None


@pytest.mark.asyncio
async def test_source_finding_from_scenario_sync_does_not_reopen_source(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_reports: list[dict] = []
    review_calls = 0

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_reports.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + f"\nrepair {len(repair_reports)}\n",
                    mode=readme.mode,
                )
            ]
        )

    async def synchronize(_machine, scenario, _current, review_feedback=None) -> ScenarioRevision:
        return ScenarioRevision(
            scenario_description=scenario.scenario_description or "Training scenario.",
            definition="Synchronized scenario.",
            attack_graph=scenario.attack_graph,
            summary="Synchronized the scenario with the current source.",
        )

    async def review(_machine, _scenario, review_context="generation") -> ScenarioReview:
        assert review_context == "source_sync"
        nonlocal review_calls
        review_calls += 1
        if review_calls <= app.state.workflow.scenario_sync_attempts:
            return ScenarioReview(
                approved=False,
                summary=(
                    "The configured CVE-2026-42533 condition conflicts with the official "
                    "description."
                ),
                findings=[
                    ScenarioReviewFinding(
                        step_id="web-entry",
                        severity="error",
                        category="semantic_mismatch",
                        repair_target="source_code",
                        evidence=(
                            "The implemented configuration does not satisfy the CVE-2026-42533 "
                            "trigger condition."
                        ),
                        remediation="Repair the source configuration to match the official record.",
                    )
                ],
            )
        return ScenarioReview(approved=True, summary="The repaired source matches the CVE.")

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.synchronize_scenario = synchronize
    app.state.workflow.generator.review_scenario = review
    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert len(repair_reports) == 1
    assert review_calls == 1
    assert fake_build.submitted_archive is not None
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        report = json.loads(archive.read("repair_report.json"))
    assert report["attempts"][-1]["scenario_sync_status"] == "approved"
    assert "CVE-2026-42533" in json.dumps(report, ensure_ascii=False)
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.status in {SessionStatus.BUILD_QUEUED, SessionStatus.COMPLETED}
    assert submitted.source_generation_attempts < submitted.source_generation_attempt_limit


@pytest.mark.asyncio
async def test_invalid_persisted_flag_regenerates_scenario(client) -> None:
    http, app, _ = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    created = await http.post("/v1/sessions", headers=headers)
    session_id = created.json()["session_id"]
    machine = {
        "name": "Flag regeneration",
        "visibility": "private",
        "theme": "Web security",
        "difficulty": "Easy",
        "needs_user_flag": True,
        "user_flag_details": "/home/student/user.txt after exploitation",
        "needs_system_flag": False,
    }
    await http.put(f"/v1/sessions/{session_id}/machine-information", json=machine, headers=headers)
    state = await app.state.repository.get(session_id)
    invalid_id = "scenario-invalid-flag"
    state.scenario = ScenarioDraft(
        scenario_id=invalid_id,
        title="Invalid flag",
        definition="invalid persisted scenario",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="entry",
                    title="Entry",
                    kind="custom",
                    phase="initial_access",
                    description="Training entry",
                    implementation_steps=["Provision entry"],
                )
            ]
        ),
        user_flag="flag{wrong_0123456789abcdef0123456789abcdef}",
    )
    state.status = SessionStatus.SCENARIO_READY
    await app.state.repository.save(state)

    events = await http.get(f"/v1/sessions/{session_id}/scenarios/events", headers=headers)
    assert events.status_code == 200
    regenerated = await app.state.repository.get(session_id)
    assert regenerated.scenario is not None
    assert regenerated.scenario.scenario_id != invalid_id
    assert re.fullmatch(r"flag\{user_[0-9a-f]{32}\}", regenerated.scenario.user_flag or "")


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
    assert response.json()["build_repair_attempts"] == 0

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
    assert restarted.json()["build_repair_attempts"] == 3

    for _ in range(100):
        current = await app.state.repository.get(state.session_id)
        if current.status == SessionStatus.COMPLETED:
            break
        await asyncio.sleep(0.01)
    assert current.status == SessionStatus.COMPLETED
    assert current.build_repair_attempts == 4
    assert current.build_repair_attempt_limit == 6
    assert len(fake_build.submitted_requests) == 4


@pytest.mark.asyncio
async def test_validation_failures_do_not_consume_build_repair_attempts(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_calls = 0

    async def invalid_repair(*_args, **_kwargs) -> SourcePatch:
        nonlocal repair_calls
        repair_calls += 1
        return SourcePatch(
            files=[
                SourceFile(
                    path="contents/scenario_manifest.json",
                    content="{}",
                    mode="0644",
                )
            ]
        )

    app.state.workflow.generator.repair_source = invalid_repair

    accepted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert accepted.status_code == 202
    assert accepted.json()["build_repair_attempts"] == 0
    for _ in range(100):
        if state.session_id not in app.state.workflow.tasks:
            break
        await asyncio.sleep(0.01)
    failed = await app.state.repository.get(state.session_id)
    assert failed.status == SessionStatus.FAILED
    assert failed.build_repair_attempts == 0
    assert failed.build_repair_attempt_limit == 0
    assert failed.source_generation_attempts == repair_calls
    assert failed.source_generation_attempt_limit == repair_calls
    assert repair_calls == 2

    assert fake_build.submitted_requests == []
    status_response = await http.get(f"/v1/sessions/{state.session_id}", headers=headers)
    assert status_response.status_code == 200
    await asyncio.sleep(0)
    assert repair_calls == 2


@pytest.mark.asyncio
async def test_validation_continues_into_next_build_slot(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_calls = 0

    async def repair_after_first_validation_batch(
        _machine, _scenario, current, _failure_report, _skills=None
    ) -> SourcePatch:
        nonlocal repair_calls
        repair_calls += 1
        if repair_calls <= app.state.workflow.source_generation_attempts:
            return SourcePatch(
                files=[
                    SourceFile(
                        path="contents/scenario_manifest.json",
                        content=json.dumps({"attempt": repair_calls}),
                        mode="0644",
                    )
                ]
            )
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + "\nRecovered in the next build slot.\n",
                    mode=readme.mode,
                )
            ]
        )

    app.state.workflow.generator.repair_source = repair_after_first_validation_batch

    accepted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert accepted.status_code == 202

    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert repair_calls == app.state.workflow.source_generation_attempts + 1
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.build_repair_attempts == 1
    assert submitted.source_generation_attempts == repair_calls
    assert submitted.source_generation_attempt_limit == (
        app.state.workflow.build_repair_max_attempts * app.state.workflow.source_generation_attempts
    )


@pytest.mark.asyncio
async def test_unsafe_absolute_repair_path_is_retried(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []

    async def repair_with_unsafe_path_then_recover(
        _machine, _scenario, current, failure_report, _skills=None
    ) -> SourcePatch:
        repair_contexts.append(failure_report)
        if len(repair_contexts) == 1:
            return SourcePatch(
                files=[
                    SourceFile(
                        path="/var/www/html/sqli_app/index.php",
                        content="<?php echo 'unsafe destination path';\n",
                        mode="0644",
                    )
                ]
            )
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + "\nRecovered from unsafe repair path.\n",
                    mode=readme.mode,
                )
            ]
        )

    app.state.workflow.generator.repair_source = repair_with_unsafe_path_then_recover

    accepted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert accepted.status_code == 202

    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert len(repair_contexts) == 2
    assert repair_contexts[1]["kind"] == "source_patch_validation"
    assert (
        repair_contexts[1]["error_message"]
        == "unsafe repair path: /var/www/html/sqli_app/index.php"
    )
    assert repair_contexts[1]["original_trigger"]["kind"] == "packer_build"
    assert "/var/www/html/sqli_app/index.php" in repair_contexts[1]["rejected_patch"]
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.build_repair_attempts == 1
    assert submitted.build_repair_attempt_limit == 3
    assert fake_build.submitted_archive is not None
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        readme = archive.read("contents/README.md").decode()
    assert "Recovered from unsafe repair path." in readme


@pytest.mark.asyncio
async def test_failed_semantic_review_is_repaired_before_build_submission(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []
    review_calls = 0

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_contexts.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + f"\nSemantic repair {len(repair_contexts)}.\n",
                    mode=readme.mode,
                )
            ]
        )

    async def review(*_args, **_kwargs) -> SourceReview:
        nonlocal review_calls
        review_calls += 1
        if review_calls == 1:
            return SourceReview(
                approved=False,
                summary="A benign request exposes the next-step credential.",
                findings=[
                    SourceReviewFinding(
                        step_id="web-entry",
                        severity="error",
                        category="unintended_shortcut",
                        evidence="The normal route returns the credential without exploitation.",
                        remediation="Separate benign output from exploit-only evidence.",
                    )
                ],
            )
        return SourceReview(approved=True, summary="Exploit chain and controls are consistent.")

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.review_source = review

    accepted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert accepted.status_code == 202

    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert review_calls == 2
    assert len(repair_contexts) == 2
    assert repair_contexts[1]["kind"] == "source_semantic_review"
    assert repair_contexts[1]["checks"][0]["name"] == ("semantic:unintended_shortcut:web-entry")
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.build_repair_attempts == 1


@pytest.mark.asyncio
async def test_source_repair_regression_gets_a_fresh_semantic_review(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []
    review_calls = 0

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_contexts.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        if len(repair_contexts) == 1:
            return SourcePatch(
                files=[
                    SourceFile(
                        path=readme.path,
                        content=readme.content + "\nInitial build repair.\n",
                        mode=readme.mode,
                    )
                ]
            )
        if len(repair_contexts) == 2:
            return SourcePatch(
                files=[
                    SourceFile(
                        path="contents/app/index.php",
                        content="<?php while ($row = $result->fetch_assoc()) { echo '<td>';",
                    )
                ]
            )
        index = next(
            (file for file in current.files if file.path == "contents/app/index.php"),
            None,
        )
        assert index is None or "echo '<td>';" not in index.content
        return SourcePatch(
            files=[
                SourceFile(
                    path="contents/app/index.php",
                    content=(
                        "<?php while ($row = $result->fetch_assoc()) { "
                        "echo '<td>' . htmlspecialchars($row['username']) . '</td>'; } ?>"
                    ),
                )
            ]
        )

    async def review(*_args, **_kwargs) -> SourceReview:
        nonlocal review_calls
        review_calls += 1
        if review_calls == 1:
            return SourceReview(
                approved=False,
                summary="The SQL injection acceptance test bypasses the web application.",
                findings=[
                    SourceReviewFinding(
                        step_id="web-entry",
                        severity="error",
                        category="acceptance_test_gap",
                        affected_files=["contents/app/index.php"],
                        evidence="The test queries the database directly instead of using SQLi.",
                        remediation="Exercise the vulnerable web route and assert leaked data.",
                    )
                ],
            )
        if review_calls == 2:
            return SourceReview(
                approved=False,
                summary="The repair left the PHP application incomplete.",
                findings=[
                    SourceReviewFinding(
                        step_id="web-entry",
                        severity="error",
                        category="implementation_mismatch",
                        affected_files=["contents/app/index.php"],
                        evidence="contents/app/index.php ends in the middle of result rendering.",
                        remediation="Complete the PHP result loop and response markup.",
                    )
                ],
            )
        return SourceReview(approved=True, summary="The repaired application is complete.")

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.review_source = review

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert review_calls == 3
    assert repair_contexts[1]["checks"][0]["name"] == ("semantic:acceptance_test_gap:web-entry")
    assert repair_contexts[2]["kind"] == "source_semantic_repair_retry"
    assert repair_contexts[2]["candidate_review"]["checks"][0]["name"] == (
        "semantic:implementation_mismatch:web-entry"
    )
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        index = archive.read("contents/app/index.php").decode()
    assert "htmlspecialchars" in index


@pytest.mark.asyncio
async def test_unrelated_late_semantic_findings_do_not_expand_fixed_scope(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []
    review_calls = 0

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_contexts.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + f"\nRepair {len(repair_contexts)}.\n",
                    mode=readme.mode,
                )
            ]
        )

    async def review(*_args, **_kwargs) -> SourceReview:
        nonlocal review_calls
        categories = ["acceptance_test_gap", "implementation_mismatch", "wrong_technique"]
        category = categories[min(review_calls, len(categories) - 1)]
        review_calls += 1
        return SourceReview(
            approved=False,
            summary=f"Late review finding {review_calls}.",
            findings=[
                SourceReviewFinding(
                    step_id="web-entry",
                    severity="error",
                    category=category,
                    evidence=f"A different late-stage concern was raised ({category}).",
                    remediation="Request another unrelated source change.",
                )
            ],
        )

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.review_source = review

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert review_calls == 2
    assert len(repair_contexts) == 2
    assert fake_build.submitted_archive is not None
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        report = json.loads(archive.read("repair_report.json"))
    semantic_review = report["source_semantic_review"]
    assert semantic_review["status"] == "approved"
    assert semantic_review["report"]["checks"][0]["status"] == "warn"
    assert "out-of-scope late finding" in semantic_review["report"]["error_message"]


def test_full_source_reaudit_depends_on_contract_or_repair_surface_changes() -> None:
    manifest = {
        "target_os": "debian-12",
        "required_files": [
            "contents/build.sh",
            "contents/scripts/provision.sh",
        ],
        "services": [{"name": "web", "protocol": "http", "port": 80}],
        "acceptance_tests": [{"command": "curl -fsS http://127.0.0.1/"}],
        "expected_vulnerabilities": [{"name": "SQLi", "description": "SQL injection"}],
        "health_checks": [{"command": "systemctl is-active apache2"}],
        "attack_steps": [
            {
                "step_id": "web-entry",
                "kind": "sqli",
                "requires": [],
                "achieves": ["credential"],
            }
        ],
        "objectives": [],
    }

    def source(current_manifest: dict, provision: str = "install web\n") -> GeneratedSource:
        return GeneratedSource(
            files=[
                SourceFile(
                    path="contents/scenario_manifest.json",
                    content=json.dumps(current_manifest),
                ),
                SourceFile(path="contents/build.sh", content="run provision\n"),
                SourceFile(path="contents/scripts/provision.sh", content=provision),
                SourceFile(path="contents/app/index.php", content="<?php vulnerable();"),
            ]
        )

    review = SourceReview(
        approved=False,
        summary="Provisioning needs a local repair.",
        findings=[
            SourceReviewFinding(
                step_id="web-entry",
                severity="error",
                category="implementation_mismatch",
                affected_files=["contents/scripts/provision.sh"],
                evidence="The provision command is incomplete.",
                remediation="Repair the provision command.",
            )
        ],
    )
    base = source(manifest)
    local_candidate = source(manifest, provision="install web\nconfigure web\n")
    assert _source_review_scope_invalidation_reasons(
        base,
        local_candidate,
        review,
        {"contents/scripts/provision.sh"},
    ) == []

    test_only_manifest = {**manifest, "acceptance_tests": [{"command": "test exploit"}]}
    manifest_review = review.model_copy(
        update={
            "findings": [
                review.findings[0].model_copy(
                    update={"affected_files": ["contents/scenario_manifest.json"]}
                )
            ]
        }
    )
    assert _source_review_scope_invalidation_reasons(
        base,
        source(test_only_manifest),
        manifest_review,
        {"contents/scenario_manifest.json"},
    ) == []

    changed_contract = {
        **manifest,
        "services": [{"name": "web", "protocol": "http", "port": 8080}],
    }
    assert "review contract changed" in " ".join(
        _source_review_scope_invalidation_reasons(
            base,
            source(changed_contract),
            manifest_review,
            {"contents/scenario_manifest.json"},
        )
    )
    assert "expanded beyond" in " ".join(
        _source_review_scope_invalidation_reasons(
            base,
            source(manifest),
            review,
            {"contents/app/index.php"},
        )
    )


@pytest.mark.asyncio
async def test_source_repair_review_receives_a_fixed_scope(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []
    reconsiderations: list[dict] = []
    review_calls = 0

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_contexts.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + f"\nRepair {len(repair_contexts)}.\n",
                    mode=readme.mode,
                )
            ]
        )

    async def review(
        _machine,
        _scenario,
        _current,
        _skills=None,
        reconsideration=None,
    ) -> SourceReview:
        nonlocal review_calls
        review_calls += 1
        if reconsideration is not None:
            reconsiderations.append(reconsideration)
            return SourceReview(
                approved=True,
                summary="The persistent finding was based on the wrong installation premise.",
            )
        return SourceReview(
            approved=False,
            summary="The same installation mismatch remains.",
            findings=[
                SourceReviewFinding(
                    step_id="web-entry",
                    severity="error",
                    repair_target="source_code",
                    category="implementation_mismatch",
                    evidence="The reviewer still claims the package source is inconsistent.",
                    remediation="Rewrite the package installation again.",
                )
            ],
        )

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.review_source = review

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert review_calls == 2
    assert len(repair_contexts) == 2
    assert len(reconsiderations) == 1
    assert reconsiderations[0]["kind"] == "source_repair_verification"
    assert reconsiderations[0]["blocking_review"]["checks"][0]["repair_target"] == (
        "source_code"
    )
    assert reconsiderations[0]["changed_files"] == ["contents/README.md"]


@pytest.mark.asyncio
async def test_persisted_attack_graph_source_review_is_revalidated_not_patched(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []
    reconsiderations: list[dict] = []
    state.repair_failure_report = {
        "kind": "source_semantic_review",
        "status": "fail",
        "error_message": "The graph allegedly needs different installation metadata.",
        "checks": [
            {
                "status": "fail",
                "name": "semantic:implementation_mismatch:web-entry",
                "repair_target": "attack_graph",
                "evidence": "The implementation uses Apache from the OS repository.",
                "remediation": "Change the attack graph installation metadata.",
            }
        ],
    }
    await app.state.repository.save(state)

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_contexts.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + "\nInitial build repair.\n",
                    mode=readme.mode,
                )
            ]
        )

    async def review(
        _machine,
        _scenario,
        _current,
        _skills=None,
        reconsideration=None,
    ) -> SourceReview:
        assert reconsideration is not None
        reconsiderations.append(reconsideration)
        return SourceReview(
            approved=True,
            summary="The requested graph field is not required by the model.",
        )

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.review_source = review

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert repair_contexts == []
    assert len(reconsiderations) == 1
    assert reconsiderations[0]["kind"] == "source_review_revalidation"
    assert reconsiderations[0]["previous_review"]["checks"][0]["repair_target"] == ("attack_graph")


@pytest.mark.asyncio
async def test_scenario_text_source_review_finding_routes_to_scenario_sync(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []
    sync_feedback: list[dict | None] = []
    reconsiderations: list[dict] = []
    review_calls = 0

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_contexts.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        return SourcePatch(
            files=[
                SourceFile(
                    path=readme.path,
                    content=readme.content + "\nInitial build repair.\n",
                    mode=readme.mode,
                )
            ]
        )

    async def review(*_args, **_kwargs) -> SourceReview:
        nonlocal review_calls
        review_calls += 1
        reconsideration = _kwargs.get("reconsideration")
        if reconsideration is not None:
            reconsiderations.append(reconsideration)
            return SourceReview(
                approved=True,
                summary="The synchronized prose already uses MariaDB.",
            )
        return SourceReview(
            approved=False,
            summary="The prose still names the old service.",
            findings=[
                SourceReviewFinding(
                    step_id="web-entry",
                    severity="error",
                    repair_target="scenario_text",
                    category="implementation_mismatch",
                    evidence="The implementation uses MariaDB but the prose says MySQL.",
                    remediation="Update only the scenario prose to MariaDB.",
                )
            ],
        )

    async def synchronize(_machine, scenario, _current, review_feedback=None) -> ScenarioRevision:
        sync_feedback.append(review_feedback)
        return ScenarioRevision(
            scenario_description=scenario.scenario_description or "Training scenario.",
            definition="The target uses MariaDB.",
            attack_graph=scenario.attack_graph,
            summary="Updated only the stale service name in the prose.",
        )

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.review_source = review
    app.state.workflow.generator.synchronize_scenario = synchronize

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert len(repair_contexts) == 1
    assert review_calls == 1
    assert sync_feedback[0]["kind"] == "source_semantic_review"
    assert sync_feedback[0]["checks"][0]["repair_target"] == "scenario_text"
    assert reconsiderations == []
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.scenario is not None
    assert submitted.scenario.definition == "The target uses MariaDB."


@pytest.mark.asyncio
async def test_repeated_invalid_source_repair_is_returned_to_source_reviewer(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []
    reconsiderations: list[dict] = []

    async def repair(_machine, _scenario, current, failure_report, _skills=None) -> SourcePatch:
        repair_contexts.append(failure_report)
        readme = next(file for file in current.files if file.path == "contents/README.md")
        if len(repair_contexts) == 1:
            return SourcePatch(
                files=[
                    SourceFile(
                        path=readme.path,
                        content=readme.content + "\nInitial build repair.\n",
                        mode=readme.mode,
                    )
                ]
            )
        return SourcePatch(
            files=[SourceFile(path=readme.path, content=readme.content, mode=readme.mode)]
        )

    async def review(
        _machine,
        _scenario,
        _current,
        _skills=None,
        reconsideration=None,
    ) -> SourceReview:
        if reconsideration is not None:
            reconsiderations.append(reconsideration)
            return SourceReview(
                approved=True,
                summary="The previous remediation cannot produce a valid source change.",
            )
        return SourceReview(
            approved=False,
            summary="The acceptance test allegedly needs a source change.",
            findings=[
                SourceReviewFinding(
                    step_id="web-entry",
                    severity="error",
                    category="acceptance_test_gap",
                    evidence="The current acceptance test is allegedly insufficient.",
                    remediation="Rewrite the source without changing its behavior.",
                )
            ],
        )

    app.state.workflow.generator.repair_source = repair
    app.state.workflow.generator.review_source = review

    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)

    assert fake_build.submitted_request is not None
    assert len(repair_contexts) == 3
    assert repair_contexts[1]["kind"] == "source_semantic_review"
    assert repair_contexts[2]["kind"] == "source_patch_validation"
    assert repair_contexts[2]["original_trigger"]["kind"] == "source_semantic_review"
    assert "did not make any effective changes" in repair_contexts[2]["error_message"]
    assert len(reconsiderations) == 1
    assert reconsiderations[0]["previous_review"]["kind"] == "source_semantic_review"
    assert reconsiderations[0]["validation_failure"]["kind"] == ("source_patch_validation")
    assert "contents/README.md" in reconsiderations[0]["attempted_patch"]
    with zipfile.ZipFile(fake_build.submitted_archive) as archive:
        report = json.loads(archive.read("repair_report.json"))
    failed_attempts = [
        attempt
        for attempt in report["attempts"]
        if attempt.get("validation_status_after") == "fail"
    ]
    assert len(failed_attempts) == 2
    assert report["source_semantic_review"]["status"] == "approved"


@pytest.mark.asyncio
async def test_final_semantic_rejection_is_persisted_when_attempts_are_exhausted(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    app.state.workflow.source_generation_attempts = 1
    app.state.workflow.build_repair_max_attempts = 1

    async def reject(*_args, **_kwargs) -> SourceReview:
        return SourceReview(
            approved=False,
            summary="Exploit verification uses a test-only shortcut.",
            findings=[
                SourceReviewFinding(
                    step_id="web-entry",
                    severity="error",
                    category="unproven_exploit",
                    evidence="A marker branch creates the success artifact directly.",
                    remediation="Exercise the real vulnerable data flow.",
                )
            ],
        )

    app.state.workflow.generator.review_source = reject
    response = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert response.status_code == 202
    for _ in range(100):
        current = await app.state.repository.get(state.session_id)
        if current.status == SessionStatus.FAILED:
            break
        await asyncio.sleep(0.01)

    assert current.status == SessionStatus.FAILED
    assert fake_build.submitted_request is None
    report_path = Path(current.source_path or "") / "repair_report.json"
    report = json.loads(report_path.read_text())
    assert report["source_semantic_review"]["status"] == "rejected"
    assert (
        report["source_semantic_review"]["report"]["checks"][0]["name"]
        == "semantic:unproven_exploit:web-entry"
    )


@pytest.mark.asyncio
async def test_explicit_reaccess_preserves_and_increments_build_repair_count(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    state.build_repair_attempts = 2
    state.scenario_sync_attempts = 4
    state.scenario_sync_attempt_limit = 4
    await app.state.repository.save(state)

    restarted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert restarted.status_code == 202
    assert restarted.json()["status"] == "generating_code"
    assert restarted.json()["build_repair_attempts"] == 2
    restarted_state = await app.state.repository.get(state.session_id)
    assert restarted_state.scenario_sync_attempts == 4
    assert restarted_state.scenario_sync_attempt_limit == (
        4 + app.state.workflow.scenario_sync_attempts
    )

    for _ in range(100):
        if fake_build.submitted_request is not None:
            break
        await asyncio.sleep(0.01)
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.build_repair_attempts == 3
    assert submitted.build_repair_attempt_limit == 5


@pytest.mark.asyncio
async def test_explicit_reaccess_adds_a_full_automatic_repair_cycle(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    state.build_repair_attempts = 3
    state.build_repair_attempt_limit = 3
    await app.state.repository.save(state)
    fake_build.get_response = {
        "status": "failed",
        "progress": 100,
        "error_message": "packer failed",
    }

    restarted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert restarted.status_code == 202
    assert restarted.json()["build_repair_attempts"] == 3

    for _ in range(200):
        if (
            len(fake_build.submitted_requests) == 3
            and state.session_id not in app.state.workflow.tasks
        ):
            break
        await asyncio.sleep(0.01)

    exhausted = await app.state.repository.get(state.session_id)
    assert exhausted.status == SessionStatus.FAILED
    assert exhausted.build_repair_attempts == 6
    assert exhausted.build_repair_attempt_limit == 6
    assert len(fake_build.submitted_requests) == 3


@pytest.mark.asyncio
async def test_explicit_reaccess_cancels_stale_build_instead_of_synchronizing(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app, status=SessionStatus.BUILDING)
    state.build_status = "building"
    state.build_repair_attempts = 2
    await app.state.repository.save(state)
    fake_build.get_response = {
        "status": "failed",
        "progress": 100,
        "error_message": "packer failed while ai_server was offline",
    }

    restarted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert restarted.status_code == 409
    assert restarted.json()["detail"].startswith("stopped machine generation")
    cancelled = await app.state.repository.get(state.session_id)
    assert cancelled.status == SessionStatus.CANCELLED
    assert cancelled.build_status == "cancelled"
    assert fake_build.cancelled_build_ids == [state.build_id]
    assert fake_build.submitted_requests == []


def test_build_repair_limit_can_be_set_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("BUILD_REPAIR_MAX_ATTEMPTS", "2")
    assert Settings(_env_file=None).build_repair_max_attempts == 2


def test_source_generation_attempts_can_be_set_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_GENERATION_ATTEMPTS", "5")
    assert Settings(_env_file=None).source_generation_attempts == 5
