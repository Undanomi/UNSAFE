from __future__ import annotations

import io
import struct
import tarfile

import pytest
from fastapi import HTTPException

from ai_server.models import (
    AttackGraph,
    AttackStep,
    GeneratedSource,
    MachineInformation,
    ScenarioDraft,
    SourceFile,
    SourcePatch,
    SourceWorkbenchCommand,
    SourceWorkbenchDecision,
)
from ai_server.sandbox_app import (
    _container_configuration,
    _demultiplex,
    _read_workspace_tar,
    _source_tar,
    _validate_command,
)
from ai_server.services.source_sandbox import SourceSandboxExecution
from ai_server.services.workflow import MachineWorkflow


def test_source_tar_round_trip_preserves_text_files() -> None:
    source = GeneratedSource(
        files=[
            SourceFile(
                path="contents/build.sh",
                content="#!/bin/bash\nset -euo pipefail\n",
                mode="0755",
            )
        ]
    )

    restored = _read_workspace_tar(_source_tar(source))

    assert restored == {"contents/build.sh": source.files[0]}


def test_source_tar_makes_candidate_directories_owned_by_non_root_user() -> None:
    source = GeneratedSource(
        files=[SourceFile(path="contents/app/main.py", content="print('ok')\n")]
    )

    with tarfile.open(fileobj=io.BytesIO(_source_tar(source)), mode="r:") as archive:
        members = {member.name: member for member in archive}

    assert members["contents"].isdir()
    assert members["contents/app"].isdir()
    assert members["contents"].uid == 65534
    assert members["contents/app"].uid == 65534


def test_candidate_container_has_private_ephemeral_filesystems_and_no_host_mounts() -> None:
    configuration = _container_configuration("debian:13-slim", "candidate-1")

    assert configuration["Image"] == "debian:13-slim"
    assert configuration["HostConfig"]["NetworkMode"] == "slsg-source-net-candidate-1"
    assert configuration["HostConfig"]["Tmpfs"].keys() == {"/tmp"}
    assert configuration["HostConfig"]["ReadonlyRootfs"] is False
    assert "Binds" not in configuration["HostConfig"]
    assert "VolumesFrom" not in configuration["HostConfig"]


def test_workbench_command_rejects_inline_shell_and_unrestricted_network() -> None:
    with pytest.raises(HTTPException, match="inline code"):
        _validate_command(
            SourceWorkbenchCommand(
                argv=["bash", "-c", "id"],
                purpose="Do not permit inline shell commands.",
            )
        )
    with pytest.raises(HTTPException, match="limited to OS package tools"):
        _validate_command(
            SourceWorkbenchCommand(
                argv=["bash", "script.sh"],
                purpose="Do not run arbitrary code as root.",
                run_as_root=True,
            )
        )


def test_workbench_command_allows_fresh_container_package_installation() -> None:
    _validate_command(
        SourceWorkbenchCommand(
            argv=["apt-get", "install", "-y", "python3"],
            purpose="Install the runtime declared by provisioning.",
            network_access=True,
            run_as_root=True,
        )
    )
    with pytest.raises(HTTPException, match="disable lifecycle scripts"):
        _validate_command(
            SourceWorkbenchCommand(
                argv=["npm", "install"],
                purpose="Resolve dependencies.",
                network_access=True,
            )
        )


def test_docker_stream_demultiplexes_bounded_output() -> None:
    payload = (
        bytes([1, 0, 0, 0]) + struct.pack(">I", 3) + b"out"
        + bytes([2, 0, 0, 0]) + struct.pack(">I", 3) + b"err"
    )

    assert _demultiplex(payload) == ("out", "err")


class FakeSourceSandbox:
    def __init__(self) -> None:
        self.destroyed: list[str] = []

    async def create(self, source: GeneratedSource) -> str:
        assert source.files
        return "sandbox-1"

    async def execute(
        self, sandbox_id: str, command: SourceWorkbenchCommand
    ) -> SourceSandboxExecution:
        assert sandbox_id == "sandbox-1"
        assert command.argv == ["npm", "run", "build"]
        return SourceSandboxExecution(exit_code=0, stdout="build passed\n", stderr="")

    async def changes(self, sandbox_id: str) -> SourcePatch:
        assert sandbox_id == "sandbox-1"
        return SourcePatch(
            files=[
                SourceFile(
                    path="contents/package-lock.json",
                    content='{"lockfileVersion":3}\n',
                )
            ]
        )

    async def destroy(self, sandbox_id: str) -> None:
        self.destroyed.append(sandbox_id)


class FakeWorkbenchGenerator:
    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision:
        del machine, scenario, current, commands_remaining
        if not observations:
            return SourceWorkbenchDecision(
                action="run",
                command=SourceWorkbenchCommand(
                    argv=["npm", "run", "build"],
                    purpose="Compile the generated application.",
                ),
                summary="Compile the application.",
            )
        return SourceWorkbenchDecision(
            action="finish",
            summary="The application compiled successfully.",
        )


@pytest.mark.asyncio
async def test_workbench_agent_imports_generated_files_and_destroys_sandbox() -> None:
    sandbox = FakeSourceSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 3
    workflow.generator = FakeWorkbenchGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/package.json", content='{"scripts":{}}\n')]
    )

    updated, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Workbench",
            visibility="private",
            theme="Build validation",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-workbench",
            title="Workbench",
            definition="# Workbench",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="inspect-source",
                        title="Inspect source",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Inspect the generated source.",
                        implementation_steps=["Create a deterministic source fixture."],
                    )
                ]
            ),
        ),
        source,
    )

    assert report["status"] == "pass"
    assert report["observations"][0]["exit_code"] == 0
    assert {file.path for file in updated.files} == {
        "contents/package.json",
        "contents/package-lock.json",
    }
    assert sandbox.destroyed == ["sandbox-1"]
