from __future__ import annotations

import json

import httpx
import pytest

from ai_server.config import Settings
from ai_server.models import (
    AttackGraph,
    AttackStep,
    MachineInformation,
    ScenarioDraft,
)
from ai_server.services.ai import CVEVerification, GeminiGenerator
from ai_server.services.errors import exception_detail


def graph_without_objectives() -> AttackGraph:
    return AttackGraph(
        steps=[
            AttackStep(
                step_id="enumerate-web",
                title="Enumerate web service",
                kind="reconnaissance",
                phase="reconnaissance",
                description="Inspect the training service",
                implementation_steps=["Expose a deterministic training service"],
            )
        ]
    )


@pytest.mark.asyncio
async def test_vm_source_generation_uses_large_output_budget() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        generated = {
            "files": [
                {
                    "path": "contents/build.sh",
                    "content": "#!/bin/bash\nset -euo pipefail\n",
                    "mode": "0755",
                }
            ]
        }
        return gemini_response(generated)

    settings = Settings(gemini_api_key="test-key", gemini_max_output_tokens=65536)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(settings, client)
        result = await generator.generate_source(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy"),
            ScenarioDraft(
                scenario_id="scenario-test",
                title="Test",
                definition="# Test",
                attack_graph=graph_without_objectives(),
            ),
        )

    assert result.files[0].path == "contents/build.sh"
    assert requests[0]["generationConfig"]["maxOutputTokens"] == 65536
    assert requests[0]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.asyncio
async def test_attack_graph_generation_allows_non_cve_attack_chain() -> None:
    graph = {
        "objectives": [
            {
                "objective_id": "user-flag",
                "objective_type": "user_flag",
                "description": "/home/student/user.txt",
            }
        ],
        "steps": [
            {
                "step_id": "upload-bypass",
                "title": "Upload validation bypass",
                "kind": "web_vulnerability",
                "phase": "initial_access",
                "description": "Bypass extension validation in the training application",
                "requires": [],
                "achieves": [],
                "cve_id": None,
                "implementation_steps": ["Implement intentionally weak extension validation"],
            },
            {
                "step_id": "read-user-flag",
                "title": "Read user flag",
                "kind": "credential",
                "phase": "objective",
                "description": "Use the application identity to read the user flag",
                "requires": ["upload-bypass"],
                "achieves": ["user-flag"],
                "cve_id": None,
                "implementation_steps": ["Grant the training identity access to the flag"],
            },
        ],
    }

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: gemini_response(graph))
    ) as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)
        machine = MachineInformation(
            name="Test",
            visibility="private",
            theme="Web",
            difficulty="Easy",
            needs_user_flag=True,
            user_flag_details="/home/student/user.txt",
            needs_system_flag=False,
        )
        parsed = await generator._draft_attack_graph(machine, [])

    assert [step.kind for step in parsed.steps] == ["web_vulnerability", "credential"]
    assert all(step.cve_id is None for step in parsed.steps)


@pytest.mark.asyncio
async def test_cve_candidate_rejects_id_before_minimum_year() -> None:
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(cve_min_year=2024), client)
        with pytest.raises(ValueError, match="older than minimum year 2024"):
            generator._validate_cve_id("CVE-2023-1234")


@pytest.mark.asyncio
async def test_cve_candidate_accepts_id_from_minimum_year() -> None:
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(cve_min_year=2024), client)
        generator._validate_cve_id("CVE-2024-1234")


def test_empty_exception_message_still_has_diagnostic_value() -> None:
    assert exception_detail(httpx.ReadTimeout("")) == "ReadTimeout"


def test_machine_information_defaults_to_ubuntu_2604() -> None:
    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    assert machine.operating_system == "Ubuntu 26.04"
    assert (
        MachineInformation(
            name="Test",
            visibility="private",
            theme="Web",
            difficulty="Easy",
            operating_system="  ",
        ).operating_system
        == "Ubuntu 26.04"
    )


@pytest.mark.asyncio
async def test_ubuntu_osv_evidence_is_filtered_by_target_release() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "affected": [
                    {"package": {"ecosystem": "Ubuntu:16.04:LTS", "name": "linux"}},
                    {"package": {"ecosystem": "Ubuntu:26.04:LTS", "name": "linux"}},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(Settings(), client)
        evidence = await generator._ubuntu_evidence("CVE-2026-0001", "Ubuntu 26.04")

    assert evidence is not None
    assert evidence["ecosystem"] == "Ubuntu:26.04:LTS"
    assert len(evidence["affected"]) == 1


def test_kernel_cve_requires_target_release_osv_evidence() -> None:
    verification = CVEVerification(
        software="Linux kernel",
        vulnerable_version="4.4.0",
        os_compatible=True,
        compatibility_reason="candidate",
        installation_method="package",
        implementation_steps=["install"],
    )
    evidence = {
        "descriptions": [{"value": "A race condition in the Linux kernel"}],
        "affected": [],
        "ubuntu_osv": {
            "ecosystem": "Ubuntu:26.04:LTS",
            "tracked": True,
            "affected": [],
        },
    }

    GeminiGenerator._enforce_kernel_evidence(verification, evidence)

    assert verification.os_compatible is False
    assert "Ubuntu:26.04:LTS" in verification.compatibility_reason


@pytest.mark.asyncio
async def test_only_cve_steps_are_enriched_with_external_evidence() -> None:
    verification = {
        "software": "Example service",
        "vulnerable_version": "1.2.3",
        "os_compatible": True,
        "compatibility_reason": "The release archive runs on the target OS",
        "installation_method": "release archive",
        "implementation_steps": ["download 1.2.3", "configure", "verify"],
        "references": ["https://www.cve.org/CVERecord?id=CVE-2026-1234"],
    }
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host or "")
        if request.url.host == "cveawg.mitre.org":
            return httpx.Response(
                200,
                json={
                    "containers": {
                        "cna": {
                            "descriptions": [{"value": "Example application issue"}],
                            "affected": [{"product": "Example service"}],
                            "references": [],
                        }
                    }
                },
            )
        if request.url.host == "api.osv.dev":
            return httpx.Response(404)
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"items": []})
        return gemini_response(verification)

    graph = AttackGraph(
        steps=[
            AttackStep(
                step_id="web-cve",
                title="Exploit example service",
                kind="cve",
                phase="initial_access",
                description="Exploit the isolated training service",
                cve_id="CVE-2026-1234",
                implementation_steps=["candidate plan"],
            ),
            AttackStep(
                step_id="reuse-credential",
                title="Reuse credential",
                kind="credential",
                phase="post_exploitation",
                description="Use the credential exposed by the first step",
                requires=["web-cve"],
                implementation_steps=["provision a training credential"],
            ),
        ]
    )
    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verified = await GeminiGenerator(
            Settings(gemini_api_key="test-key", cve_min_year=2024), client
        )._verify_attack_graph(machine, graph)

    assert verified.steps[0].software == "Example service"
    assert verified.steps[0].implementation_steps[0] == "download 1.2.3"
    assert verified.steps[1] == graph.steps[1]
    assert requested_hosts.count("cveawg.mitre.org") == 1


@pytest.mark.asyncio
async def test_generate_scenario_without_cve_does_not_request_cve_services() -> None:
    requests: list[str] = []
    graph = {
        "objectives": [],
        "steps": [
            {
                "step_id": "weak-web-route",
                "title": "Weak web route",
                "kind": "logic_flaw",
                "phase": "initial_access",
                "description": "Abuse application logic",
                "requires": [],
                "achieves": [],
                "cve_id": None,
                "implementation_steps": ["Implement the intentional logic flaw"],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if len(requests) == 1:
            return gemini_response(graph)
        return gemini_response("# Generated scenario")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)
        scenario = await generator.generate_scenario(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
        )

    assert scenario.definition == "# Generated scenario"
    assert scenario.attack_graph.steps[0].kind == "logic_flaw"
    assert len(requests) == 2
    assert all("cveawg" not in url and "osv.dev" not in url for url in requests)


def gemini_response(value) -> httpx.Response:
    generated_text = value if isinstance(value, str) else json.dumps(value)
    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": generated_text}]},
                }
            ]
        },
    )
