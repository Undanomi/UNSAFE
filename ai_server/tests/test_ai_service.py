from __future__ import annotations

import json

import httpx
import pytest

from ai_server.config import Settings
from ai_server.models import (
    AttackGraph,
    AttackStep,
    GeneratedSource,
    MachineInformation,
    ScenarioDraft,
    ScenarioReview,
    SourceFile,
    SourceReview,
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
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    assert schema["properties"]["files"]["minItems"] == 1
    assert "maxItems" not in schema["properties"]["files"]
    assert schema["$defs"]["SourceFile"]["properties"]["mode"]["enum"] == [
        "0600",
        "0640",
        "0644",
        "0700",
        "0750",
        "0755",
    ]
    assert "default" not in schema["$defs"]["SourceFile"]["properties"]["mode"]


@pytest.mark.asyncio
async def test_vm_source_repair_uses_source_patch_schema() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return gemini_response(
            {
                "files": [
                    {
                        "path": "contents/scripts/provision.sh",
                        "content": "#!/bin/bash\nprintf '%s\\n' repaired\n",
                        "mode": "0755",
                    }
                ],
                "delete_paths": [],
            }
        )

    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    scenario = ScenarioDraft(
        scenario_id="scenario-test",
        title="Test",
        definition="# Test",
        attack_graph=graph_without_objectives(),
    )
    current = GeneratedSource(
        files=[SourceFile(path="contents/scripts/provision.sh", content="exit 1")]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GeminiGenerator(Settings(gemini_api_key="test-key"), client).repair_source(
            machine, scenario, current, {"error": "build failed"}
        )

    assert result.files[0].content.endswith("repaired\n")
    assert requests[0]["generationConfig"]["responseMimeType"] == "application/json"
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    assert "maxItems" not in schema["properties"]["files"]
    assert "maxItems" not in schema["properties"]["delete_paths"]
    assert "default" not in schema["properties"]["delete_paths"]


@pytest.mark.asyncio
async def test_vm_source_generation_retries_duplicate_embedded_paths() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        build_file = {
            "path": "contents/build.sh",
            "content": "#!/bin/bash\nset -euo pipefail\n",
            "mode": "0755",
        }
        files = [build_file, build_file] if len(requests) == 1 else [build_file]
        return gemini_response({"files": files})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GeminiGenerator(
            Settings(gemini_api_key="test-key", generation_retries=2), client
        ).generate_source(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy"),
            ScenarioDraft(
                scenario_id="scenario-test",
                title="Test",
                definition="# Test",
                attack_graph=graph_without_objectives(),
            ),
        )

    assert len(result.files) == 1
    assert len(requests) == 2
    second_prompt = requests[1]["contents"][0]["parts"][0]["text"]
    assert "duplicate generated path: contents/build.sh" in second_prompt


@pytest.mark.asyncio
async def test_vm_source_repair_retries_invalid_embedded_manifest_json() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        manifest = (
            r'{"command":"find /tmp -exec test -f {} \;"}'
            if len(requests) == 1
            else '{"target_os":"Debian 13.7.0"}'
        )
        return gemini_response(
            {
                "files": [
                    {
                        "path": "contents/scenario_manifest.json",
                        "content": manifest,
                        "mode": "0644",
                    }
                ],
                "delete_paths": [],
            }
        )

    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    scenario = ScenarioDraft(
        scenario_id="scenario-test",
        title="Test",
        definition="# Test",
        attack_graph=graph_without_objectives(),
    )
    current = GeneratedSource(
        files=[SourceFile(path="contents/scenario_manifest.json", content="{}")]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        patch = await GeminiGenerator(
            Settings(gemini_api_key="test-key", generation_retries=2), client
        ).repair_source(machine, scenario, current, {"error": "validation failed"})

    assert json.loads(patch.files[0].content)["target_os"] == "Debian 13.7.0"
    assert len(requests) == 2
    second_prompt = requests[1]["contents"][0]["parts"][0]["text"]
    assert "model_output_validation_error" in second_prompt
    assert "scenario_manifest.json is not valid JSON" in second_prompt


@pytest.mark.asyncio
async def test_vm_source_review_uses_independent_structured_verdict() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return gemini_response(
            {
                "approved": False,
                "summary": "Normal input exposes the credential before exploitation.",
                "findings": [
                    {
                        "step_id": "extract-credential",
                        "severity": "error",
                        "category": "unintended_shortcut",
                        "evidence": "contents/app/index.php returns the password for id=1.",
                        "remediation": "Keep credentials out of benign responses.",
                    }
                ],
            }
        )

    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    scenario = ScenarioDraft(
        scenario_id="scenario-test",
        title="Test",
        definition="# Test",
        attack_graph=graph_without_objectives(),
    )
    current = GeneratedSource(
        files=[SourceFile(path="contents/app/index.php", content="<?php echo 'test';")]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await GeminiGenerator(Settings(gemini_api_key="test-key"), client).review_source(
            machine, scenario, current
        )

    assert review == SourceReview.model_validate(
        {
            "approved": False,
            "summary": "Normal input exposes the credential before exploitation.",
            "findings": [
                {
                    "step_id": "extract-credential",
                    "severity": "error",
                    "category": "unintended_shortcut",
                    "evidence": "contents/app/index.php returns the password for id=1.",
                    "remediation": "Keep credentials out of benign responses.",
                }
            ],
        }
    )
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    assert schema["properties"]["approved"]["type"] == "boolean"
    assert "unintended_shortcut" in json.dumps(schema)


@pytest.mark.asyncio
async def test_scenario_review_uses_independent_permission_focused_verdict() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return gemini_response(
            {
                "approved": False,
                "summary": "The web identity cannot traverse the flag's parent directory.",
                "findings": [
                    {
                        "step_id": "read-user-flag",
                        "severity": "error",
                        "category": "permission_blocker",
                        "evidence": "www-data needs directory search permission on /home/student before it can read user.txt.",
                        "remediation": "Define the owner, group, and mode for the directory and flag, then test access as www-data.",
                    }
                ],
            }
        )

    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    scenario = ScenarioDraft(
        scenario_id="scenario-test",
        title="Test",
        definition="# Test",
        attack_graph=graph_without_objectives(),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await GeminiGenerator(Settings(gemini_api_key="test-key"), client).review_scenario(
            machine, scenario
        )

    assert review == ScenarioReview.model_validate(
        {
            "approved": False,
            "summary": "The web identity cannot traverse the flag's parent directory.",
            "findings": [
                {
                    "step_id": "read-user-flag",
                    "severity": "error",
                    "category": "permission_blocker",
                    "evidence": "www-data needs directory search permission on /home/student before it can read user.txt.",
                    "remediation": "Define the owner, group, and mode for the directory and flag, then test access as www-data.",
                }
            ],
        }
    )
    request_prompt = requests[0]["contents"][0]["parts"][0]["text"]
    assert "独立した敵対的レビュー担当" in request_prompt
    assert "全親ディレクトリ" in request_prompt
    assert "permission_blocker" in request_prompt
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    assert "permission_shortcut" in json.dumps(schema)


@pytest.mark.asyncio
async def test_generate_scenario_retries_after_semantic_review_rejection() -> None:
    graph = {
        "objectives": [],
        "steps": [
            {
                "step_id": "permission-step",
                "title": "Traverse protected directory",
                "kind": "misconfiguration",
                "phase": "initial_access",
                "description": "Read a protected training artifact.",
                "requires": [],
                "achieves": [],
                "cve_id": None,
                "implementation_steps": ["Configure explicit directory permissions"],
            }
        ],
    }
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        request_number = len(requests)
        if request_number == 1:
            return gemini_response(graph)
        if request_number in {2, 4}:
            return gemini_response(f"# Generated scenario attempt {request_number}")
        if request_number == 3:
            return gemini_response(
                {
                    "approved": False,
                    "summary": "The required parent-directory search permission is missing.",
                    "findings": [
                        {
                            "step_id": "permission-step",
                            "severity": "error",
                            "category": "permission_blocker",
                            "evidence": "No mode is specified for the parent directory.",
                            "remediation": "Specify and validate owner, group, and mode.",
                        }
                    ],
                }
            )
        return gemini_response(
            {
                "approved": True,
                "summary": "The revised permission model is consistent.",
                "findings": [],
            }
        )

    settings = Settings(gemini_api_key="test-key", scenario_generation_attempts=2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        scenario = await GeminiGenerator(settings, client).generate_scenario(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
        )

    assert scenario.definition == "# Generated scenario attempt 4"
    assert len(requests) == 5
    retry_prompt = requests[3]["contents"][0]["parts"][0]["text"]
    assert "scenario_semantic_review" in retry_prompt
    assert "permission_blocker" in retry_prompt
    assert "No mode is specified for the parent directory." in retry_prompt
    assert "Specify and validate owner, group, and mode." in retry_prompt
    graph_prompts = [
        request
        for request in requests
        if "攻撃経路を設計するアーキテクト" in request["contents"][0]["parts"][0]["text"]
    ]
    assert len(graph_prompts) == 1


@pytest.mark.asyncio
async def test_generate_scenario_regenerates_graph_after_broken_chain_review() -> None:
    graph = {
        "objectives": [],
        "steps": [
            {
                "step_id": "credential-step",
                "title": "Recover a credential",
                "kind": "credential",
                "phase": "initial_access",
                "description": "Recover the training credential.",
                "requires": [],
                "achieves": [],
                "cve_id": None,
                "implementation_steps": ["Configure a reproducible credential path"],
            }
        ],
    }
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        request_number = len(requests)
        if request_number in {1, 4}:
            return gemini_response(graph)
        if request_number in {2, 5}:
            return gemini_response(f"# Generated scenario attempt {request_number}")
        if request_number == 3:
            return gemini_response(
                {
                    "approved": False,
                    "summary": "A prerequisite can be bypassed.",
                    "findings": [
                        {
                            "step_id": "credential-step",
                            "severity": "error",
                            "category": "broken_chain",
                            "evidence": "The credential is available without the prerequisite.",
                            "remediation": "Make the prerequisite output necessary.",
                        }
                    ],
                }
            )
        return gemini_response(
            {
                "approved": True,
                "summary": "The revised chain is consistent.",
                "findings": [],
            }
        )

    settings = Settings(gemini_api_key="test-key", scenario_generation_attempts=2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        scenario = await GeminiGenerator(settings, client).generate_scenario(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
        )

    assert scenario.definition == "# Generated scenario attempt 5"
    assert len(requests) == 6
    regenerated_graph_prompt = requests[3]["contents"][0]["parts"][0]["text"]
    regenerated_scenario_prompt = requests[4]["contents"][0]["parts"][0]["text"]
    assert "broken_chain" in regenerated_graph_prompt
    assert "broken_chain" in regenerated_scenario_prompt


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
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return gemini_response(graph)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    schema_json = json.dumps(schema)
    assert "$defs" in schema
    for filtered_key in ("default", "maxItems", "maxLength", "minLength", "pattern"):
        assert f'"{filtered_key}":' not in schema_json


@pytest.mark.asyncio
async def test_gemini_http_error_includes_response_detail() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Invalid JSON schema"}})

    settings = Settings(gemini_api_key="test-key", scenario_generation_attempts=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(settings, client)
        with pytest.raises(RuntimeError, match="Invalid JSON schema"):
            await generator.generate_scenario(
                MachineInformation(
                    name="Test",
                    visibility="private",
                    theme="Web",
                    difficulty="Easy",
                )
            )


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


def test_machine_information_defaults_to_debian_1370() -> None:
    machine = MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
    assert machine.operating_system == "Debian 13.7.0"
    assert (
        MachineInformation(
            name="Test",
            visibility="private",
            theme="Web",
            difficulty="Easy",
            operating_system="  ",
        ).operating_system
        == "Debian 13.7.0"
    )


@pytest.mark.asyncio
async def test_debian_osv_evidence_is_filtered_by_target_release() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.osv.dev/v1/vulns/DEBIAN-CVE-2026-0001"
        return httpx.Response(
            200,
            json={
                "affected": [
                    {"package": {"ecosystem": "Debian:12", "name": "linux"}},
                    {"package": {"ecosystem": "Debian:13", "name": "linux"}},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(Settings(), client)
        evidence = await generator._debian_evidence("CVE-2026-0001", "Debian 13.7.0")

    assert evidence is not None
    assert evidence["ecosystem"] == "Debian:13"
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
        "debian_osv": {
            "ecosystem": "Debian:13",
            "tracked": True,
            "affected": [],
        },
    }

    GeminiGenerator._enforce_kernel_evidence(verification, evidence)

    assert verification.os_compatible is False
    assert "Debian:13" in verification.compatibility_reason


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
        if len(requests) == 2:
            return gemini_response("# Generated scenario")
        return gemini_response(
            {"approved": True, "summary": "Scenario is internally consistent.", "findings": []}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)
        scenario = await generator.generate_scenario(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
        )

    assert scenario.definition == "# Generated scenario"
    assert scenario.attack_graph.steps[0].kind == "logic_flaw"
    assert len(requests) == 3
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
