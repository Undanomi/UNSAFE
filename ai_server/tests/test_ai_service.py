from __future__ import annotations

import json

import httpx
import pytest

from ai_server.config import Settings
from ai_server.models import CVEInstallationPlan, MachineInformation, ScenarioDraft
from ai_server.services.ai import GeminiGenerator
from ai_server.services.errors import exception_detail


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
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(generated)}]},
                    }
                ]
            },
        )

    settings = Settings(gemini_api_key="test-key", gemini_max_output_tokens=65536)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(settings, client)
        result = await generator.generate_source(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy"),
            ScenarioDraft(scenario_id="scenario-test", title="Test", definition="# Test"),
        )

    assert result.files[0].path == "contents/build.sh"
    assert requests[0]["generationConfig"]["maxOutputTokens"] == 65536
    assert requests[0]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.asyncio
async def test_cve_selection_rejects_candidates_before_minimum_year() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        selected = {
            "initial_cve": "CVE-2023-1234",
            "privesc_cve": "CVE-2024-5678",
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(selected)}]},
                    }
                ]
            },
        )

    settings = Settings(gemini_api_key="test-key", cve_min_year=2024)
    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(settings, client)
        with pytest.raises(ValueError, match="older than minimum year 2024"):
            await generator._select_cves(machine, [])


@pytest.mark.asyncio
async def test_cve_selection_accepts_candidates_from_minimum_year() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        selected = {
            "initial_cve": "CVE-2024-1234",
            "privesc_cve": "CVE-2025-5678",
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(selected)}]},
                    }
                ]
            },
        )

    settings = Settings(gemini_api_key="test-key", cve_min_year=2024)
    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(settings, client)
        selected = await generator._select_cves(machine, [])

    assert selected == ("CVE-2024-1234", "CVE-2025-5678")


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
    plan = CVEInstallationPlan(
        cve_id="CVE-2016-5195",
        role="privilege_escalation",
        software="Linux kernel",
        vulnerable_version="4.4.0",
        os_compatible=True,
        compatibility_reason="candidate",
        installation_method="package",
        installation_steps=["install"],
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

    GeminiGenerator._enforce_kernel_evidence([plan], [evidence])

    assert plan.os_compatible is False
    assert "Ubuntu:26.04:LTS" in plan.compatibility_reason


def test_incompatible_cve_can_explain_rejection_without_install_steps() -> None:
    plan = CVEInstallationPlan(
        cve_id="CVE-2016-5195",
        role="privilege_escalation",
        software="Linux kernel",
        vulnerable_version="before 4.8.3",
        os_compatible=False,
        compatibility_reason="not affected on target OS",
        installation_method=None,
        installation_steps=[],
    )
    assert plan.os_compatible is False


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [True, False])
async def test_installation_plans_accepts_wrapped_or_bare_array(wrapped: bool) -> None:
    plans = [
        {
            "cve_id": "CVE-2024-1234",
            "role": "initial_access",
            "software": "Example web app",
            "vulnerable_version": "1.0.0",
            "os_compatible": True,
            "compatibility_reason": "source build works on the target OS",
            "installation_method": "source build",
            "installation_steps": ["download 1.0.0", "build", "start and verify"],
            "references": [],
        },
        {
            "cve_id": "CVE-2024-5678",
            "role": "privilege_escalation",
            "software": "Example helper",
            "vulnerable_version": "2.0.0",
            "os_compatible": True,
            "compatibility_reason": "binary runs on the target OS",
            "installation_method": "release archive",
            "installation_steps": ["download 2.0.0", "install", "start and verify"],
            "references": [],
        },
    ]
    payload = {"plans": plans} if wrapped else plans

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(payload)}]},
                    }
                ]
            },
        )

    settings = Settings(gemini_api_key="test-key")
    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    evidence = [
        {"cve_id": "CVE-2024-1234", "descriptions": [], "affected": []},
        {"cve_id": "CVE-2024-5678", "descriptions": [], "affected": []},
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(settings, client)
        parsed = await generator._installation_plans(machine, *evidence)

    assert [plan.cve_id for plan in parsed] == ["CVE-2024-1234", "CVE-2024-5678"]


@pytest.mark.asyncio
async def test_installation_plans_normalizes_order_and_roles_from_selected_cves() -> None:
    plans = [
        {
            "cve_id": "CVE-2024-5678",
            "role": "initial_access",
            "software": "Example helper",
            "vulnerable_version": "2.0.0",
            "os_compatible": True,
            "compatibility_reason": "binary runs on the target OS",
            "installation_method": "release archive",
            "installation_steps": ["download", "install", "verify"],
        },
        {
            "cve_id": "CVE-2024-1234",
            "role": "privilege_escalation",
            "software": "Example web app",
            "vulnerable_version": "1.0.0",
            "os_compatible": True,
            "compatibility_reason": "source build works on the target OS",
            "installation_method": "source build",
            "installation_steps": ["download", "build", "verify"],
        },
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps({"plans": plans})}]},
                    }
                ]
            },
        )

    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    evidence = [
        {"cve_id": "CVE-2024-1234", "descriptions": [], "affected": []},
        {"cve_id": "CVE-2024-5678", "descriptions": [], "affected": []},
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)
        parsed = await generator._installation_plans(machine, *evidence)

    assert [(plan.cve_id, plan.role) for plan in parsed] == [
        ("CVE-2024-1234", "initial_access"),
        ("CVE-2024-5678", "privilege_escalation"),
    ]
