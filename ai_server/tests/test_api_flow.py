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
    MachineInformation,
    ScenarioDraft,
    ScenarioRevision,
    SessionState,
    SessionStatus,
    SourceFile,
    SourcePatch,
    SourceReview,
    SourceReviewFinding,
)
from ai_server.repository import SessionNotFoundError
from ai_server.services.workflow import MachineWorkflow


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
        self.packer_log_response = ""
        self.download_requests: list[tuple[str, str]] = []
        self.download_headers: list[tuple[str | None, str | None]] = []

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
        return {
            "build_id": build_id,
            "status": "completed",
            "progress": 100,
            "machine_password": "test-generated-machine-password",
        }

    async def packer_log(self, build_id: str) -> str:
        return self.packer_log_response

    async def artifacts(self, build_id: str) -> list[Artifact]:
        return [
            Artifact(
                artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
                artifact_type="tar.zst",
                file_name="slsg-machine.tar.zst",
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
            "Content-Type": "application/zstd",
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
    with pytest.raises(RuntimeError, match=r"without a tar\.zst"):
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

    scenario = (await app.state.repository.get(session_id)).scenario
    assert scenario is not None
    assert scenario.user_flag is not None
    assert re.fullmatch(r"flag\{user_[0-9a-f]{32}\}", scenario.user_flag)
    assert scenario.system_flag is None
    assert scenario.user_flag not in events.text
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
    download_url = completed.json()["download_url"]
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
    assert download.headers["content-type"] == "application/zstd"
    assert download.headers["content-disposition"] == (
        'attachment; filename="slsg-machine.tar.zst"'
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

    unsatisfiable = await http.get(
        issued.json()["download_url"], headers={"Range": "bytes=99-"}
    )
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
    fake_build.packer_log_response = "command before failure\nerror detail"

    async def synchronize_scenario(machine, scenario, current) -> ScenarioRevision:
        return ScenarioRevision(
            scenario_description="Updated player introduction after source repair.",
            definition="retry synchronized with repaired source",
            attack_graph=scenario.attack_graph,
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
    assert '"scenario_sync_status": "approved"' in repair_report


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
                    path="contents/scripts/provision.sh",
                    content="#!/bin/bash\nset -euo pipefail\necho invalid mode\n",
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
    assert repair_calls == (
        app.state.workflow.build_repair_max_attempts
        * app.state.workflow.source_generation_attempts
    )

    assert fake_build.submitted_requests == []
    status_response = await http.get(f"/v1/sessions/{state.session_id}", headers=headers)
    assert status_response.status_code == 200
    await asyncio.sleep(0)
    assert repair_calls == (
        app.state.workflow.build_repair_max_attempts
        * app.state.workflow.source_generation_attempts
    )


@pytest.mark.asyncio
async def test_validation_continues_into_next_build_slot(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_calls = 0

    async def repair_after_first_validation_batch(
        _machine, _scenario, current, _failure_report
    ) -> SourcePatch:
        nonlocal repair_calls
        repair_calls += 1
        if repair_calls <= app.state.workflow.source_generation_attempts:
            return SourcePatch(
                files=[
                    SourceFile(
                        path="contents/scripts/provision.sh",
                        content="#!/bin/bash\nset -euo pipefail\necho invalid mode\n",
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


@pytest.mark.asyncio
async def test_unsafe_absolute_repair_path_is_retried(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    repair_contexts: list[dict] = []

    async def repair_with_unsafe_path_then_recover(
        _machine, _scenario, current, failure_report
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

    async def repair(_machine, _scenario, current, failure_report) -> SourcePatch:
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
async def test_explicit_reaccess_preserves_and_increments_build_repair_count(client) -> None:
    http, app, fake_build = client
    headers = {"X-Authenticated-User-ID": "user-123"}
    state = await create_failed_build_state(app)
    state.build_repair_attempts = 2
    await app.state.repository.save(state)

    restarted = await http.post(
        f"/v1/sessions/{state.session_id}/machines", json={}, headers=headers
    )
    assert restarted.status_code == 202
    assert restarted.json()["status"] == "generating_code"
    assert restarted.json()["build_repair_attempts"] == 2

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
async def test_explicit_reaccess_refreshes_stale_status_before_extending_cycle(client) -> None:
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
    assert restarted.status_code == 202
    assert restarted.json()["status"] == "generating_code"
    assert restarted.json()["build_status"] == "failed"
    assert restarted.json()["build_repair_attempts"] == 2

    for _ in range(200):
        if (
            len(fake_build.submitted_requests) == 3
            and state.session_id not in app.state.workflow.tasks
        ):
            break
        await asyncio.sleep(0.01)
    submitted = await app.state.repository.get(state.session_id)
    assert submitted.build_repair_attempts == 5
    assert submitted.build_repair_attempt_limit == 5


def test_build_repair_limit_can_be_set_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("BUILD_REPAIR_MAX_ATTEMPTS", "2")
    assert Settings(_env_file=None).build_repair_max_attempts == 2


def test_source_generation_attempts_can_be_set_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_GENERATION_ATTEMPTS", "5")
    assert Settings(_env_file=None).source_generation_attempts == 5
