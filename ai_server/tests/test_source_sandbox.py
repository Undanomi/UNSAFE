from __future__ import annotations

import asyncio
import io
import struct
import tarfile

import pytest
from fastapi import HTTPException

import ai_server.services.workflow as workflow_module
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
    _declared_download_hosts,
    _demultiplex,
    _execution_argv,
    _make_workspace_writable,
    _read_workspace_tar,
    _source_tar,
    _validate_command,
    _validate_public_download_hosts,
    _validate_workbench_patch,
)
from ai_server.services.source_sandbox import SourceSandboxError, SourceSandboxExecution
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


class WorkspaceOwnershipResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class WorkspaceOwnershipEngine:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict]] = []
        self.next_exec = 0

    async def request(self, method: str, path: str, **kwargs) -> WorkspaceOwnershipResponse:
        self.requests.append((method, path, kwargs))
        if path.endswith("/exec"):
            self.next_exec += 1
            return WorkspaceOwnershipResponse({"Id": f"exec-{self.next_exec}"})
        if path.endswith("/json"):
            return WorkspaceOwnershipResponse({"ExitCode": 0})
        return WorkspaceOwnershipResponse({})


@pytest.mark.asyncio
async def test_workspace_is_owned_and_writable_by_sandbox_user_after_archive_upload() -> None:
    engine = WorkspaceOwnershipEngine()

    await _make_workspace_writable(  # type: ignore[arg-type]
        engine,
        "container-1",
        ["contents/app/package.json"],
    )

    create_payloads = [
        kwargs["json"]
        for method, path, kwargs in engine.requests
        if method == "POST" and path == "/containers/container-1/exec"
    ]
    assert [payload["Cmd"] for payload in create_payloads] == [
        [
            "chown",
            "65534:65534",
            "/workspace/contents",
            "/workspace/contents/app",
            "/workspace/contents/app/package.json",
        ],
        [
            "chmod",
            "u+rwX",
            "/workspace/contents",
            "/workspace/contents/app",
            "/workspace/contents/app/package.json",
        ],
    ]
    assert all(payload["User"] == "0:0" for payload in create_payloads)


def test_workspace_reader_ignores_dependency_symlinks_but_rejects_source_symlinks() -> None:
    dependency_archive = io.BytesIO()
    with tarfile.open(fileobj=dependency_archive, mode="w") as archive:
        link = tarfile.TarInfo("workspace/contents/app/node_modules/.bin/next")
        link.type = tarfile.SYMTYPE
        link.linkname = "../next/dist/bin/next"
        archive.addfile(link)

    assert _read_workspace_tar(dependency_archive.getvalue()) == {}

    source_archive = io.BytesIO()
    with tarfile.open(fileobj=source_archive, mode="w") as archive:
        link = tarfile.TarInfo("workspace/contents/app/next-link")
        link.type = tarfile.SYMTYPE
        link.linkname = "outside"
        archive.addfile(link)

    with pytest.raises(HTTPException, match="symbolic link"):
        _read_workspace_tar(source_archive.getvalue())


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


@pytest.mark.parametrize(
    "executable",
    ["systemd-analyze", "systemd-run", "journalctl", "loginctl", "udevadm"],
)
def test_workbench_command_rejects_target_vm_integration_tools(executable: str) -> None:
    with pytest.raises(HTTPException, match="target VM integration command"):
        _validate_command(
            SourceWorkbenchCommand(
                argv=[executable, "--help"],
                purpose="Do not emulate target VM integration in Docker.",
                intent="verify",
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


@pytest.mark.parametrize("executable", ["curl", "wget"])
def test_workbench_command_allows_declared_https_artifact_download(executable: str) -> None:
    source = GeneratedSource(
        files=[
            SourceFile(
                path="contents/scripts/provision.sh",
                content=(
                    "node_base_url='https://nodejs.org/dist/v22.14.0'\n"
                    "curl --fail \"$node_base_url/node.tar.xz\"\n"
                ),
                mode="0755",
            )
        ]
    )
    command = SourceWorkbenchCommand(
        argv=[executable, "https://nodejs.org/dist/v22.14.0/SHASUMS256.txt"],
        purpose="Download the checksummed runtime declared by provisioning.",
        network_access=True,
    )

    declared_hosts = _declared_download_hosts(source)
    _validate_command(command, declared_download_hosts=declared_hosts)

    assert declared_hosts == frozenset({"nodejs.org"})
    executed = _execution_argv(command)
    if executable == "curl":
        assert executed[:9] == [
            "curl",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--max-redirs",
            "0",
            "--max-filesize",
            "536870912",
        ]
    else:
        assert executed[:4] == [
            "wget",
            "--https-only",
            "--max-redirect=0",
            "--max-filesize=536870912",
        ]


@pytest.mark.parametrize(
    ("argv", "declared_hosts", "error"),
    [
        (
            ["curl", "http://nodejs.org/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "credential-free HTTPS",
        ),
        (
            ["curl", "https://nodejs.org/runtime.tar.xz?token=value"],
            frozenset({"nodejs.org"}),
            "without query strings",
        ),
        (
            ["curl", "https://nodejs.org:8443/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "credential-free HTTPS",
        ),
        (
            ["curl", "https://[invalid/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "malformed",
        ),
        (
            ["curl", "--location", "https://nodejs.org/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "download-only access",
        ),
        (
            ["curl", "-fsSL", "https://nodejs.org/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "option is not permitted",
        ),
        (
            ["curl", "--json", "{}", "https://nodejs.org/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "download-only access",
        ),
        (
            ["curl", "-Asecret", "https://nodejs.org/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "option is not permitted",
        ),
        (
            ["wget", "--post-data=value", "https://nodejs.org/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "download-only access",
        ),
        (
            ["wget", "https://example.com/runtime.tar.xz"],
            frozenset({"nodejs.org"}),
            "must be declared",
        ),
        (
            [
                "wget",
                "https://nodejs.org/runtime.tar.xz",
                "127.0.0.1/internal",
            ],
            frozenset({"nodejs.org"}),
            "exactly one explicit HTTPS URL",
        ),
    ],
)
def test_workbench_command_restricts_network_downloaders(
    argv: list[str], declared_hosts: frozenset[str], error: str
) -> None:
    with pytest.raises(HTTPException, match=error):
        _validate_command(
            SourceWorkbenchCommand(
                argv=argv,
                purpose="Reject unsafe downloader behavior.",
                network_access=True,
            ),
            declared_download_hosts=declared_hosts,
        )


@pytest.mark.asyncio
async def test_network_download_dns_rejects_local_and_private_addresses() -> None:
    with pytest.raises(HTTPException, match="non-public address"):
        await _validate_public_download_hosts(frozenset({"127.0.0.1"}))
    with pytest.raises(HTTPException, match="non-public address"):
        await _validate_public_download_hosts(frozenset({"169.254.169.254"}))

    await _validate_public_download_hosts(frozenset({"93.184.216.34"}))


def test_network_download_allows_retry_timeout_and_output_options() -> None:
    declared_hosts = frozenset({"nodejs.org"})
    for argv in (
        [
            "curl",
            "--fail",
            "--retry",
            "3",
            "--connect-timeout=10",
            "--output",
            "node_modules/node.tar.xz",
            "https://nodejs.org/dist/v22.14.0/node.tar.xz",
        ],
        [
            "wget",
            "--tries=3",
            "--timeout",
            "10",
            "--output-document",
            "node_modules/node.tar.xz",
            "https://nodejs.org/dist/v22.14.0/node.tar.xz",
        ],
    ):
        _validate_command(
            SourceWorkbenchCommand(
                argv=argv,
                purpose="Download a declared runtime into an ignored dependency directory.",
                network_access=True,
            ),
            declared_download_hosts=declared_hosts,
        )


def test_localhost_curl_does_not_require_external_network_access() -> None:
    command = SourceWorkbenchCommand(
        argv=["curl", "http://127.0.0.1/health"],
        purpose="Check the candidate service inside the offline sandbox.",
        network_access=False,
    )

    _validate_command(command)
    assert _execution_argv(command) == command.argv


def test_workbench_command_allows_safe_candidate_relative_executable() -> None:
    _validate_command(
        SourceWorkbenchCommand(
            argv=["./node_modules/.bin/next", "build"],
            cwd="contents/app",
            purpose="Build with the candidate-local executable.",
        )
    )
    with pytest.raises(HTTPException, match="safe relative path"):
        _validate_command(
            SourceWorkbenchCommand(
                argv=["../outside"],
                purpose="Do not escape the candidate working directory.",
            )
        )
    with pytest.raises(HTTPException, match="invoked by executable name"):
        _validate_command(
            SourceWorkbenchCommand(
                argv=["bin/apt-get", "update"],
                purpose="Do not run a candidate-controlled executable as root.",
                network_access=True,
                run_as_root=True,
            )
        )


def test_workbench_patch_updates_source_but_rejects_generated_dependencies() -> None:
    source = GeneratedSource(
        files=[SourceFile(path="contents/check.py", content="raise SystemExit(1)\n")]
    )
    patch = SourcePatch(
        files=[SourceFile(path="contents/check.py", content="print('fixed')\n")]
    )

    normalized, updated = _validate_workbench_patch(source, patch)

    assert normalized.files[0].path == "contents/check.py"
    assert updated.files[0].content == "print('fixed')\n"
    with pytest.raises(HTTPException, match="ignored path"):
        _validate_workbench_patch(
            source,
            SourcePatch(
                files=[
                    SourceFile(
                        path="contents/node_modules/example/index.js",
                        content="module.exports = true;\n",
                    )
                ]
            ),
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
                    intent="verify",
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


class PolicyRetrySandbox(FakeSourceSandbox):
    def __init__(self) -> None:
        super().__init__()
        self.execute_attempts = 0

    async def execute(
        self, sandbox_id: str, command: SourceWorkbenchCommand
    ) -> SourceSandboxExecution:
        assert sandbox_id == "sandbox-1"
        self.execute_attempts += 1
        if self.execute_attempts == 1:
            raise SourceSandboxError(
                "source sandbox returned 400: command rejected",
                status_code=400,
            )
        assert command.argv == ["npm", "run", "build"]
        return SourceSandboxExecution(exit_code=0, stdout="build passed\n", stderr="")

    async def changes(self, sandbox_id: str) -> SourcePatch | None:
        assert sandbox_id == "sandbox-1"
        return None


class PolicyRetryGenerator:
    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision:
        del machine, scenario, current
        assert commands_remaining == 1
        if not observations:
            return SourceWorkbenchDecision(
                action="run",
                command=SourceWorkbenchCommand(
                    argv=["candidate-tool"],
                    purpose="Try a command rejected by policy.",
                ),
                summary="Try the candidate tool.",
            )
        assert observations[-1]["policy_rejected"] is True
        return SourceWorkbenchDecision(
            action="run",
            command=SourceWorkbenchCommand(
                argv=["npm", "run", "build"],
                purpose="Use an allowed build command.",
                intent="verify",
            ),
            summary="Use the allowed command instead.",
        )


@pytest.mark.asyncio
async def test_workbench_policy_rejection_is_observed_and_retried() -> None:
    sandbox = PolicyRetrySandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 1
    workflow.generator = PolicyRetryGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/package.json", content='{"scripts":{}}\n')]
    )

    _, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Policy retry",
            visibility="private",
            theme="Build validation",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-policy-retry",
            title="Policy retry",
            definition="# Policy retry",
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
    assert report["observations"][0]["policy_rejected"] is True
    assert report["observations"][1]["exit_code"] == 0
    assert sandbox.execute_attempts == 2
    assert sandbox.destroyed == ["sandbox-1"]


class RepairingWorkbenchSandbox(FakeSourceSandbox):
    def __init__(self) -> None:
        super().__init__()
        self.patched = False
        self.applied_patches: list[SourcePatch] = []

    async def execute(
        self, sandbox_id: str, command: SourceWorkbenchCommand
    ) -> SourceSandboxExecution:
        assert sandbox_id == "sandbox-1"
        assert command.argv == ["python3", "check.py"]
        if not self.patched:
            return SourceSandboxExecution(exit_code=1, stdout="", stderr="broken\n")
        return SourceSandboxExecution(exit_code=0, stdout="fixed\n", stderr="")

    async def apply_patch(self, sandbox_id: str, patch: SourcePatch) -> None:
        assert sandbox_id == "sandbox-1"
        self.applied_patches.append(patch)
        self.patched = True

    async def changes(self, sandbox_id: str) -> SourcePatch:
        assert sandbox_id == "sandbox-1"
        return self.applied_patches[-1]


class RepairingWorkbenchGenerator:
    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision:
        del machine, scenario, commands_remaining
        kinds = [item.get("kind") for item in observations]
        if not kinds:
            return SourceWorkbenchDecision(
                action="run",
                command=SourceWorkbenchCommand(
                    argv=["python3", "check.py"],
                    cwd="contents",
                    purpose="Reproduce the candidate failure.",
                    intent="verify",
                ),
                summary="Reproduce before editing.",
            )
        if kinds == ["command"]:
            assert observations[-1]["accepted"] is False
            return SourceWorkbenchDecision(
                action="patch",
                patch=SourcePatch(
                    files=[SourceFile(path="contents/check.py", content="print('fixed')\n")]
                ),
                summary="The observed script is the root cause; patch it.",
            )
        if kinds == ["command", "patch"]:
            assert current.files[0].content == "print('fixed')\n"
            return SourceWorkbenchDecision(
                action="finish",
                summary="Finish and let the controller rerun the failed verification.",
            )
        return SourceWorkbenchDecision(
            action="finish",
            summary="The original failing command now passes.",
        )


@pytest.mark.asyncio
async def test_workbench_diagnoses_patches_and_rechecks_in_same_sandbox() -> None:
    sandbox = RepairingWorkbenchSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 5
    workflow.generator = RepairingWorkbenchGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/check.py", content="raise SystemExit(1)\n")]
    )

    updated, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Repair loop",
            visibility="private",
            theme="Persistent sandbox repair",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-repair-loop",
            title="Repair loop",
            definition="# Repair loop",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="inspect-source",
                        title="Inspect source",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Inspect the generated source.",
                        implementation_steps=["Repair an observed deterministic failure."],
                    )
                ]
            ),
        ),
        source,
    )

    assert report["status"] == "pass"
    assert [item["kind"] for item in report["observations"]] == [
        "command",
        "patch",
        "command",
    ]
    assert report["observations"][-1]["automatic_recheck"] is True
    assert report["observations"][-1]["resolved_failure_index"] == 1
    assert updated.files[0].content == "print('fixed')\n"
    assert len(sandbox.applied_patches) == 1
    assert sandbox.destroyed == ["sandbox-1"]


class DiagnosticFailureSandbox(FakeSourceSandbox):
    async def execute(
        self, sandbox_id: str, command: SourceWorkbenchCommand
    ) -> SourceSandboxExecution:
        assert sandbox_id == "sandbox-1"
        if command.argv == ["bash", "-n", "build.sh"]:
            return SourceSandboxExecution(exit_code=0, stdout="", stderr="")
        assert command.argv == ["stat", "scripts/verify.sh"]
        return SourceSandboxExecution(
            exit_code=1,
            stdout="",
            stderr="stat: scripts/verify.sh: No such file or directory\n",
        )

    async def changes(self, sandbox_id: str) -> SourcePatch | None:
        assert sandbox_id == "sandbox-1"
        return None


class DiagnosticFailureGenerator:
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
                    argv=["stat", "scripts/verify.sh"],
                    cwd="contents",
                    purpose="Inspect whether the server-generated verifier is present.",
                    intent="inspect",
                ),
                summary="Inspect an optional file.",
            )
        if len(observations) == 1:
            return SourceWorkbenchDecision(
                action="run",
                command=SourceWorkbenchCommand(
                    argv=["bash", "-n", "build.sh"],
                    cwd="contents",
                    purpose="Verify the candidate build script syntax.",
                    intent="verify",
                ),
                summary="Run a real candidate verification.",
            )
        return SourceWorkbenchDecision(
            action="finish",
            summary="The candidate verification passed despite the failed inspection.",
        )


@pytest.mark.asyncio
async def test_failed_inspection_does_not_block_workbench_completion() -> None:
    sandbox = DiagnosticFailureSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 3
    workflow.generator = DiagnosticFailureGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/build.sh", content="#!/bin/bash\n", mode="0755")]
    )

    _, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Inspection",
            visibility="private",
            theme="Non-blocking diagnostics",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-inspection",
            title="Inspection",
            definition="# Inspection",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="inspect-source",
                        title="Inspect source",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Inspect the generated source.",
                        implementation_steps=["Inspect a server-generated path."],
                    )
                ]
            ),
        ),
        source,
    )

    assert report["status"] == "pass"
    assert report["observations"][0]["accepted"] is False
    assert report["observations"][0]["blocking"] is False
    assert report["successful_verifications"] == 1
    assert sandbox.destroyed == ["sandbox-1"]


class PreservingFailureSandbox(FakeSourceSandbox):
    async def execute(
        self, sandbox_id: str, command: SourceWorkbenchCommand
    ) -> SourceSandboxExecution:
        assert sandbox_id == "sandbox-1"
        assert command.argv == ["npm", "run", "build"]
        return SourceSandboxExecution(exit_code=1, stdout="", stderr="build failed\n")

    async def apply_patch(self, sandbox_id: str, patch: SourcePatch) -> None:
        assert sandbox_id == "sandbox-1"
        assert patch.files[0].path == "contents/package.json"

    async def changes(self, sandbox_id: str) -> SourcePatch:
        assert sandbox_id == "sandbox-1"
        return SourcePatch(
            files=[
                SourceFile(
                    path="contents/package.json",
                    content='{"scripts":{"build":"next build"}}\n',
                ),
                SourceFile(
                    path="contents/package-lock.json",
                    content='{"lockfileVersion":3}\n',
                ),
            ]
        )


class PreservingFailureGenerator:
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
                    cwd="contents",
                    purpose="Reproduce the build failure.",
                    intent="verify",
                ),
                summary="Reproduce the failure.",
            )
        return SourceWorkbenchDecision(
            action="patch",
            patch=SourcePatch(
                files=[
                    SourceFile(
                        path="contents/package.json",
                        content='{"scripts":{"build":"next build"}}\n',
                    )
                ]
            ),
            summary="Repair the package manifest.",
        )


@pytest.mark.asyncio
async def test_workbench_preserves_candidate_changes_when_verification_remains() -> None:
    sandbox = PreservingFailureSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 2
    workflow.generator = PreservingFailureGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/package.json", content='{"scripts":{}}\n')]
    )

    updated, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Preserve candidate",
            visibility="private",
            theme="Checkpoint workbench changes",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-preserve",
            title="Preserve candidate",
            definition="# Preserve candidate",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="build-source",
                        title="Build source",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Build the generated source.",
                        implementation_steps=["Repair the package manifest."],
                    )
                ]
            ),
        ),
        source,
    )

    assert report["status"] == "fail"
    assert report["candidate_changes_preserved"] is True
    assert report["changed_files"] == [
        "contents/package-lock.json",
        "contents/package.json",
    ]
    assert {file.path for file in updated.files} == {
        "contents/package-lock.json",
        "contents/package.json",
    }
    assert sandbox.destroyed == ["sandbox-1"]


class KeepaliveSandbox(FakeSourceSandbox):
    def __init__(self) -> None:
        super().__init__()
        self.touches = 0

    async def touch(self, sandbox_id: str) -> None:
        assert sandbox_id == "sandbox-1"
        self.touches += 1

    async def changes(self, sandbox_id: str) -> SourcePatch | None:
        assert sandbox_id == "sandbox-1"
        return None


class SlowWorkbenchGenerator:
    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision:
        del machine, scenario, current, observations, commands_remaining
        await asyncio.sleep(0.03)
        return SourceWorkbenchDecision(
            action="finish",
            summary="No executable validation is available for this fixture.",
        )


@pytest.mark.asyncio
async def test_workbench_keeps_sandbox_alive_while_waiting_for_ai(monkeypatch) -> None:
    monkeypatch.setattr(workflow_module, "SOURCE_SANDBOX_KEEPALIVE_SECONDS", 0.005)
    sandbox = KeepaliveSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 2
    workflow.generator = SlowWorkbenchGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/check.py", content="print('ok')\n")]
    )

    _, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Keepalive",
            visibility="private",
            theme="Rate-limit waiting",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-keepalive",
            title="Keepalive",
            definition="# Keepalive",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="inspect-source",
                        title="Inspect source",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Inspect the generated source.",
                        implementation_steps=["Wait for the shared AI request queue."],
                    )
                ]
            ),
        ),
        source,
    )

    assert report["status"] == "fail"
    assert report["successful_verifications"] == 0
    assert "without a successful verification" in report["error_message"]
    assert sandbox.touches >= 2
    assert sandbox.destroyed == ["sandbox-1"]


class BlockedWorkbenchGenerator:
    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision:
        del machine, scenario, current, observations, commands_remaining
        return SourceWorkbenchDecision(
            action="finish",
            finish_status="blocked",
            summary="Candidate verification cannot be performed.",
        )


@pytest.mark.asyncio
async def test_workbench_technical_blocker_is_reported_as_retryable_failure() -> None:
    sandbox = KeepaliveSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 3
    workflow.generator = BlockedWorkbenchGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/check.py", content="print('ok')\n")]
    )

    _, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Blocked verification",
            visibility="private",
            theme="Honest verification status",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-blocked",
            title="Blocked verification",
            definition="# Blocked verification",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="verify-source",
                        title="Verify source",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Verify the generated source.",
                        implementation_steps=["Report unavailable verification honestly."],
                    )
                ]
            ),
        ),
        source,
    )

    assert report["status"] == "fail"
    assert report["blocked_summary"] == "Candidate verification cannot be performed."
    assert report["successful_verifications"] == 0
    assert report["observations"][-1]["kind"] == "finish_blocked"
    assert sandbox.destroyed == ["sandbox-1"]


class VmDeferredGenerator:
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
                    argv=["bash", "-n", "build.sh"],
                    cwd="contents",
                    purpose="Verify the portable build script syntax.",
                    intent="verify",
                ),
                summary="Run the portable verification first.",
            )
        return SourceWorkbenchDecision(
            action="finish",
            finish_status="deferred_to_vm",
            summary="Service activation and boot ordering require the target VM.",
        )


@pytest.mark.asyncio
async def test_workbench_can_defer_vm_only_checks_after_portable_verification() -> None:
    sandbox = DiagnosticFailureSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 3
    workflow.generator = VmDeferredGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/build.sh", content="#!/bin/bash\n", mode="0755")]
    )

    _, report = await workflow._run_source_workbench(
        MachineInformation(
            name="VM deferred verification",
            visibility="private",
            theme="VM integration",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-vm-deferred",
            title="VM deferred verification",
            definition="# VM deferred verification",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="verify-service",
                        title="Verify service",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Verify the generated service.",
                        implementation_steps=["Start the service in the target VM."],
                    )
                ]
            ),
        ),
        source,
    )

    assert report["status"] == "pass"
    assert report["successful_verifications"] == 1
    assert report["deferred_to_vm"] == (
        "Service activation and boot ordering require the target VM."
    )
    assert report["observations"][-1]["kind"] == "finish_deferred_to_vm"
    assert sandbox.destroyed == ["sandbox-1"]


class RepeatedVmCommandGenerator:
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
                    argv=["bash", "-n", "build.sh"],
                    cwd="contents",
                    purpose="Verify portable shell syntax.",
                    intent="verify",
                ),
                summary="Run a portable verification.",
            )
        return SourceWorkbenchDecision(
            action="run",
            command=SourceWorkbenchCommand(
                argv=["systemd-analyze", "verify", "config/example.service"],
                cwd="contents",
                purpose="Verify a service in the target VM.",
                intent="verify",
            ),
            summary="Try a target VM integration command.",
        )


@pytest.mark.asyncio
async def test_repeated_vm_only_commands_do_not_exhaust_policy_rejection_limit() -> None:
    sandbox = DiagnosticFailureSandbox()
    workflow = object.__new__(MachineWorkflow)
    workflow.source_sandbox = sandbox
    workflow.source_workbench_action_limit = 6
    workflow.generator = RepeatedVmCommandGenerator()
    source = GeneratedSource(
        files=[SourceFile(path="contents/build.sh", content="#!/bin/bash\n", mode="0755")]
    )

    _, report = await workflow._run_source_workbench(
        MachineInformation(
            name="Repeated VM command",
            visibility="private",
            theme="VM integration",
            difficulty="Easy",
        ),
        ScenarioDraft(
            scenario_id="scenario-repeated-vm-command",
            title="Repeated VM command",
            definition="# Repeated VM command",
            attack_graph=AttackGraph(
                steps=[
                    AttackStep(
                        step_id="verify-service",
                        title="Verify service",
                        kind="reconnaissance",
                        phase="reconnaissance",
                        description="Verify the generated service.",
                        implementation_steps=["Start the service in the target VM."],
                    )
                ]
            ),
        ),
        source,
    )

    deferred = [
        item for item in report["observations"] if item["kind"] == "command_deferred_to_vm"
    ]
    assert report["status"] == "pass"
    assert report["successful_verifications"] == 1
    assert report["deferred_to_vm"] is not None
    assert len(deferred) == 5
    assert all(item["blocking"] is False for item in deferred)
    assert sandbox.destroyed == ["sandbox-1"]
