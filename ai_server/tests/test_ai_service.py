from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from ai_server.config import Settings
from ai_server.models import (
    ROCKYOU_PASSWORD_PLACEHOLDER,
    AttackGraph,
    AttackStep,
    GeneratedSource,
    MachineInformation,
    PasswordCrackingSpec,
    ScenarioDraft,
    ScenarioReview,
    ScenarioReviewFinding,
    SourceFile,
    SourceReview,
)
from ai_server.prompts import attack_graph_json_for_ai
from ai_server.services.ai import (
    AIProviderRequestError,
    AIProviderSafetyRefusalError,
    CVEVerification,
    GeminiGenerator,
    OpenAIGenerator,
    begin_token_usage_session,
    end_token_usage_session,
)
from ai_server.services.errors import ScenarioInputRevisionRequiredError, exception_detail


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


def test_ai_graph_serialization_redacts_late_bound_password() -> None:
    spec = PasswordCrackingSpec(
        wordlist="rockyou.txt",
        password="22062531",
        line_number=150_000,
        search_space_lines=200_000,
        hash_algorithm="MD5",
        hash_runtime="php",
        hash_api="md5",
        hashcat_mode=0,
        target_crack_seconds=150,
    )
    graph = AttackGraph(
        steps=[
            AttackStep(
                step_id="crack-password",
                title="Crack password",
                kind="password_cracking",
                phase="initial_access",
                description="Crack the database credential.",
                implementation_steps=["Generate the credential hash"],
                password_cracking=spec,
            )
        ]
    )

    serialized = attack_graph_json_for_ai(graph)
    assert "22062531" not in serialized
    assert '"password": null' in serialized
    assert ROCKYOU_PASSWORD_PLACEHOLDER not in serialized
    assert '"line_number": null' in serialized
    assert '"search_space_lines": null' in serialized


def verified_cve_graph() -> AttackGraph:
    return AttackGraph(
        steps=[
            AttackStep(
                step_id="nginx-cve",
                title="Exploit Nginx",
                kind="cve",
                phase="initial_access",
                description="Trigger the verified Nginx vulnerability.",
                cve_id="CVE-2026-42533",
                cve_title="Verified Nginx vulnerability",
                cve_description="Official CVE description.",
                cwe_ids=["CWE-123"],
                installation_artifact="vendor_release_binary",
                artifact_source="https://example.invalid/nginx-1.26.3.tar.gz",
                software="Nginx",
                vulnerable_version="1.26.3-3",
                os_compatible=True,
                compatibility_reason="The verified package runs on Debian 13.",
                installation_method="Install the verified vendor package.",
                implementation_steps=[
                    "Install Nginx 1.20.1.",
                    "Configure return 200 '$var'.",
                ],
                references=["https://www.cve.org/CVERecord?id=CVE-2026-42533"],
            )
        ]
    )


@pytest.mark.asyncio
async def test_openai_generation_uses_responses_api_and_structured_output() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return openai_response(
            {"approved": True, "summary": "The source is consistent.", "findings": []}
        )

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        openai_reasoning_effort="low",
        openai_max_output_tokens=32000,
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await OpenAIGenerator(settings, client)._generate(
            "Return the source review as JSON.",
            json_output=True,
            response_schema=SourceReview,
            max_output_tokens=settings.openai_max_output_tokens,
        )

    assert SourceReview.model_validate_json(review).approved is True
    request = requests[0]
    assert request.url == "https://api.openai.com/v1/responses"
    assert request.headers["Authorization"] == "Bearer test-openai-key"
    payload = json.loads(request.content)
    assert payload["model"] == "gpt-5.6-luna"
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["max_output_tokens"] == 32000
    assert payload["store"] is False
    response_format = payload["text"]["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert response_format["schema"]["additionalProperties"] is False
    assert response_format["schema"]["required"] == ["approved", "summary", "findings"]


@pytest.mark.asyncio
async def test_openai_generation_reports_incomplete_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
            },
        )

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="max_output_tokens"):
            await OpenAIGenerator(settings, client)._generate("Generate JSON", json_output=True)


@pytest.mark.asyncio
async def test_openai_generation_reports_safety_refusal_distinctly() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "status": "completed",
                        "content": [
                            {
                                "type": "refusal",
                                "refusal": "This request cannot be processed safely.",
                            }
                        ],
                    }
                ],
            },
        )

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIProviderSafetyRefusalError, match="安全ポリシー"):
            await OpenAIGenerator(settings, client)._generate("Generate JSON", json_output=True)


@pytest.mark.asyncio
async def test_openai_generation_retries_temporary_rate_limit_without_changing_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0", "x-request-id": "req-rate-limited"},
                json={
                    "error": {
                        "type": "rate_limit_error",
                        "code": "slow_down",
                        "message": "Reduce request rate.",
                    }
                },
            )
        return openai_response("generated")

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        ai_request_min_interval_seconds=0,
        ai_transient_retry_attempts=3,
        ai_transient_retry_jitter_seconds=0,
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await OpenAIGenerator(settings, client)._generate("unchanged prompt")

    assert result == "generated"
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    assert requests[0].headers["X-Client-Request-Id"] == requests[1].headers[
        "X-Client-Request-Id"
    ]


@pytest.mark.asyncio
async def test_openai_generation_does_not_retry_spend_limit() -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            429,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "project_spend_limit_exceeded",
                    "message": "Project spend limit reached.",
                }
            },
        )

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        ai_request_min_interval_seconds=0,
        ai_transient_retry_attempts=3,
        ai_transient_retry_jitter_seconds=0,
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIProviderRequestError, match="non-retryable") as raised:
            await OpenAIGenerator(settings, client)._generate("prompt")

    assert raised.value.error_code == "project_spend_limit_exceeded"
    assert raised.value.retryable is False
    assert requests == 1


@pytest.mark.asyncio
async def test_provider_failure_does_not_consume_model_output_retries() -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            429,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "organization_usage_limit_exceeded",
                    "message": "Organization usage limit reached.",
                }
            },
        )

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        generation_retries=3,
        ai_request_min_interval_seconds=0,
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIProviderRequestError):
            await OpenAIGenerator(settings, client).generate_source(
                MachineInformation(
                    name="Provider failure",
                    visibility="private",
                    theme="Retry separation",
                    difficulty="Easy",
                ),
                ScenarioDraft(
                    scenario_id="scenario-provider-failure",
                    title="Provider failure",
                    definition="# Provider failure",
                    attack_graph=graph_without_objectives(),
                ),
            )

    assert requests == 1


@pytest.mark.asyncio
async def test_openai_generator_serializes_shared_requests() -> None:
    active = 0
    max_active = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return openai_response("generated")

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        ai_max_concurrent_requests=1,
        ai_request_min_interval_seconds=0,
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = OpenAIGenerator(settings, client)
        results = await asyncio.gather(
            generator._generate("first"),
            generator._generate("second"),
        )

    assert results == ["generated", "generated"]
    assert max_active == 1


@pytest.mark.asyncio
async def test_openai_generator_uses_shared_source_generation_workflow() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return openai_response(
            {
                "files": [
                    {
                        "path": "contents/build.sh",
                        "content": "#!/bin/bash\nset -euo pipefail\n",
                        "mode": "0755",
                    }
                ]
            }
        )

    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = await OpenAIGenerator(settings, client).generate_source(
            MachineInformation(
                name="OpenAI source",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            ),
            ScenarioDraft(
                scenario_id="scenario-openai-source",
                title="OpenAI source",
                definition="# OpenAI source",
                attack_graph=graph_without_objectives(),
            ),
        )

    assert source.files[0].path == "contents/build.sh"


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
async def test_attack_graph_defers_rockyou_selection_until_after_source_generation(
    tmp_path: Path,
) -> None:
    requests: list[dict] = []
    wordlist = tmp_path / "rockyou.txt"
    wordlist.write_text("password01\npassword02\npassword03\n")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        return gemini_response(
            {
                "objectives": [],
                "steps": [
                    {
                        "step_id": "crack-password",
                        "title": "Crack the password hash with Hashcat",
                        "kind": "password_cracking",
                        "phase": "initial_access",
                        "description": "Dictionary attack against a late-bound password.",
                        "requires": [],
                        "achieves": [],
                        "cve_id": None,
                        "implementation_steps": [
                            "Provision a hash for the server-managed placeholder"
                        ],
                        "password_cracking": {
                            "wordlist": "rockyou.txt",
                            "password": "invented01",
                            "line_number": 1,
                            "search_space_lines": 1,
                            "hash_algorithm": "bcrypt",
                            "hash_runtime": "php",
                            "hash_api": "password_hash",
                            "hashcat_mode": 3200,
                            "john_format": "bcrypt",
                            "target_crack_seconds": 150,
                        },
                    }
                ],
            }
        )

    settings = Settings(
        gemini_api_key="test-key",
        rockyou_path=wordlist,
        rockyou_min_line=1,
        rockyou_max_line=3,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph = await GeminiGenerator(settings, client)._draft_attack_graph(
            MachineInformation(name="Test", visibility="private", theme="Hash", difficulty="Easy"),
            [],
        )

    assert len(requests) == 1
    assert "responseJsonSchema" in requests[0]["generationConfig"]
    assert "tools" not in requests[0]
    spec = graph.steps[0].password_cracking
    assert spec is not None
    assert spec.password is None
    assert spec.line_number is None
    assert spec.search_space_lines is None


@pytest.mark.asyncio
async def test_hash_cracking_graph_accepts_explicit_unbound_selection(tmp_path: Path) -> None:
    wordlist = tmp_path / "rockyou.txt"
    wordlist.write_text("password01\n")

    def handler(_request: httpx.Request) -> httpx.Response:
        return gemini_response(
            {
                "objectives": [],
                "steps": [
                    {
                        "step_id": "crack-password",
                        "title": "Use Hashcat",
                        "kind": "password_cracking",
                        "phase": "initial_access",
                        "description": "Run a dictionary attack.",
                        "requires": [],
                        "achieves": [],
                        "cve_id": None,
                        "implementation_steps": ["Store a password hash"],
                        "password_cracking": {
                            "wordlist": "rockyou.txt",
                            "password": None,
                            "line_number": None,
                            "search_space_lines": None,
                            "hash_algorithm": "bcrypt",
                            "hash_runtime": "php",
                            "hash_api": "password_hash",
                            "hashcat_mode": 3200,
                            "john_format": "bcrypt",
                            "target_crack_seconds": 150,
                        },
                    }
                ],
            }
        )

    settings = Settings(
        gemini_api_key="test-key",
        rockyou_path=wordlist,
        rockyou_min_line=1,
        rockyou_max_line=1,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph = await GeminiGenerator(settings, client)._draft_attack_graph(
            MachineInformation(
                name="Test", visibility="private", theme="Hash", difficulty="Easy"
            ),
            [],
        )

    spec = graph.steps[0].password_cracking
    assert spec is not None and not spec.selection_bound


@pytest.mark.asyncio
async def test_guidance_retries_when_model_exposes_flag() -> None:
    requests: list[dict] = []
    flag = "flag{user_0123456789abcdef0123456789abcdef}"
    responses = [
        {
            "introduction": "確認します。",
            "items": [
                {
                    "target_flag": "user",
                    "title": "漏えい",
                    "question": flag,
                    "hint": "答えです。",
                }
            ],
        },
        {
            "introduction": "段階的に確認します。",
            "items": [
                {
                    "target_flag": "user",
                    "title": "列挙",
                    "question": "どのサービスが公開されていますか？",
                    "hint": "ポートを調査してください。",
                }
            ],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return gemini_response(responses.pop(0))

    scenario = ScenarioDraft(
        scenario_id="scenario-guidance",
        title="Guidance",
        definition="# Guidance",
        attack_graph=graph_without_objectives(),
        user_flag=flag,
    )
    source = GeneratedSource(
        files=[SourceFile(path="contents/scripts/provision.sh", content="#!/bin/bash\n")]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        guidance = await GeminiGenerator(
            Settings(gemini_api_key="test-key", generation_retries=2), client
        ).generate_guidance(
            MachineInformation(
                name="Guidance", visibility="private", theme="Web", difficulty="Easy"
            ),
            scenario,
            source,
            [],
        )

    assert guidance.items[0].title == "列挙"
    assert len(requests) == 2
    assert (
        "guidance must not expose a correct flag value"
        in requests[1]["contents"][0]["parts"][0]["text"]
    )


@pytest.mark.asyncio
async def test_overlong_scenario_is_compacted_instead_of_regenerated(monkeypatch) -> None:
    overlong_definition = "# Scenario\n\n" + ("Repeated detail. " * 800)
    compacted_definition = "# Scenario\n\n" + ("Required detail. " * 500)
    prompts: list[str] = []
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)

        async def compact(prompt, **_kwargs):
            prompts.append(prompt)
            return json.dumps(
                {
                    "scenario_description": "Investigate the machine.",
                    "definition": compacted_definition,
                }
            )

        monkeypatch.setattr(generator, "_generate", compact)
        result = await generator._parse_or_compact_scenario_generation(
            MachineInformation(
                name="Test",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            ),
            json.dumps(
                {
                    "scenario_description": "Investigate the machine.",
                    "definition": overlong_definition,
                }
            ),
        )

    assert len(overlong_definition) > 12_000
    assert len(result.definition) <= 10_500
    assert result.definition == compacted_definition
    assert "新しい案へ作り直さず" in prompts[0]
    assert overlong_definition in prompts[0]


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
async def test_scenario_sync_keeps_authoritative_graph_and_ignores_returned_copy() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return gemini_response(
            {
                "scenario_description": "Investigate the synchronized machine.",
                "definition": "# Synchronized scenario",
                "summary": "Updated implementation details.",
                # This reproduces the malformed copy that previously aborted sync.
                "attack_graph": {
                    "objectives": [],
                    "steps": [
                        {
                            "step_id": "sqli-user-hash",
                            "title": "Extract a user hash",
                            "kind": "web_vulnerability",
                            "phase": "initial_access",
                            "description": "Use the intended SQL injection.",
                            "cve_title": "CVE metadata copied onto a non-CVE step",
                            "cve_description": "This must not be parsed during prose sync.",
                            "cwe_ids": ["CWE-89"],
                            "implementation_steps": ["Send the training request."],
                        }
                    ],
                },
            }
        )

    machine = MachineInformation(
        name="Test", visibility="private", theme="Web", difficulty="Easy"
    )
    scenario = ScenarioDraft(
        scenario_id="scenario-test",
        title="Test",
        scenario_description="Investigate the machine.",
        definition="# Original scenario",
        attack_graph=graph_without_objectives(),
    )
    current = GeneratedSource(files=[SourceFile(path="contents/README.md", content="test")])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        revision = await GeminiGenerator(
            Settings(gemini_api_key="test-key"), client
        ).synchronize_scenario(machine, scenario, current)

    assert revision.attack_graph == scenario.attack_graph
    assert revision.definition == "# Synchronized scenario"
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    assert "attack_graph" not in schema["properties"]


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
    assert "受理されなかった前回出力" in second_prompt
    assert '"path": "contents/build.sh"' in second_prompt


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
    assert "rejected_model_output" in second_prompt
    assert "scenario_manifest.json is not valid JSON" in second_prompt
    assert "find /tmp -exec test" in second_prompt


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
async def test_vm_source_review_reconsiders_failed_repair_validation() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return gemini_response(
            {
                "approved": True,
                "summary": "The prior remediation conflicted with source validation.",
                "findings": [],
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
    reconsideration = {
        "kind": "source_repair_validation_failure",
        "previous_review": {"status": "fail"},
        "validation_failure": {
            "kind": "source_patch_validation",
            "error_message": "repair patch did not make any effective changes",
        },
        "attempted_patch": '{"files":[]}',
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await GeminiGenerator(Settings(gemini_api_key="test-key"), client).review_source(
            machine,
            scenario,
            current,
            reconsideration=reconsideration,
        )

    assert review.approved is True
    prompt = requests[0]["contents"][0]["parts"][0]["text"]
    assert "前回レビューの再検討資料" in prompt
    assert "source_repair_validation_failure" in prompt
    assert "did not make any effective changes" in prompt
    assert "元の指摘が" in prompt


@pytest.mark.asyncio
async def test_vm_source_review_regenerates_invalid_attack_graph_repair_target() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return gemini_response(
                {
                    "approved": False,
                    "summary": "The attack graph allegedly needs to change.",
                    "findings": [
                        {
                            "step_id": "enumerate-web",
                            "severity": "error",
                            "repair_target": "attack_graph",
                            "category": "implementation_mismatch",
                            "evidence": "The implementation and graph use different labels.",
                            "remediation": "Change the attack graph.",
                        }
                    ],
                }
            )
        return gemini_response(
            {
                "approved": True,
                "summary": "The graph is immutable and the implementation is consistent.",
                "findings": [],
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
        review = await GeminiGenerator(
            Settings(gemini_api_key="test-key", generation_retries=2), client
        ).review_source(machine, scenario, current)

    assert review.approved is True
    assert len(requests) == 2
    retry_prompt = requests[1]["contents"][0]["parts"][0]["text"]
    assert "前回の出力は次の理由で受理できませんでした" in retry_prompt
    assert "repair_target" in retry_prompt
    assert "attack_graph" in retry_prompt
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    repair_target_schema = schema["$defs"]["SourceReviewFinding"]["properties"]["repair_target"]
    assert set(repair_target_schema["enum"]) == {"source_code", "scenario_text"}


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
                        "step_id": "enumerate-web",
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
                    "step_id": "enumerate-web",
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
async def test_scenario_review_discards_framework_owned_rockyou_findings() -> None:
    graph = AttackGraph(
        steps=[
            AttackStep(
                step_id="crack-user-hash",
                title="Crack user hash",
                kind="password_cracking",
                phase="credential_access",
                description="Crack the leaked password hash.",
                implementation_steps=["Store a runtime-generated password hash."],
                password_cracking=PasswordCrackingSpec(
                    wordlist="rockyou.txt",
                    hash_algorithm="SHA-256",
                    hash_runtime="php",
                    hash_api="hash",
                    hashcat_mode=1400,
                    target_crack_seconds=150,
                ),
            )
        ]
    )
    scenario = ScenarioDraft(
        scenario_id="scenario-rockyou-review",
        title="Rockyou review",
        definition="# Scenario",
        attack_graph=graph,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return gemini_response(
            {
                "approved": False,
                "summary": "The reviewer mixed framework and implementation responsibilities.",
                "findings": [
                    {
                        "step_id": "crack-user-hash",
                        "severity": "error",
                        "category": "implementation_gap",
                        "repair_target": "scenario_text",
                        "repair_fields": [],
                        "evidence": (
                            "rockyou.txtの取得元、プロビジョニングへの受け渡し、配置先が"
                            "定義されていません。"
                        ),
                        "remediation": "固定した取得元とchecksumを設計書へ記載してください。",
                    },
                    {
                        "step_id": "crack-user-hash",
                        "severity": "warning",
                        "category": "implementation_gap",
                        "repair_target": "scenario_text",
                        "repair_fields": [],
                        "evidence": (
                            "約150秒の測定に使うHashcat CPU実行環境とハードウェアが"
                            "特定されていません。"
                        ),
                        "remediation": "ベンチマーク条件を記録してください。",
                    },
                    {
                        "step_id": "crack-user-hash",
                        "severity": "error",
                        "category": "broken_chain",
                        "repair_target": "scenario_text",
                        "repair_fields": [],
                        "evidence": (
                            "The login handler compares the submitted plaintext directly to the "
                            "stored digest, so the cracked plaintext cannot authenticate."
                        ),
                        "remediation": "Use the declared hash verification API in the login path.",
                    },
                ],
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await GeminiGenerator(Settings(gemini_api_key="test-key"), client).review_scenario(
            MachineInformation(
                name="Rockyou boundary",
                visibility="private",
                theme="Hash cracking",
                difficulty="Medium",
            ),
            scenario,
        )

    assert review.approved is False
    assert len(review.findings) == 1
    assert review.findings[0].category == "broken_chain"
    assert "Removed 2 finding(s)" in review.summary


@pytest.mark.asyncio
async def test_source_review_discards_framework_owned_rockyou_test_request() -> None:
    scenario = ScenarioDraft(
        scenario_id="scenario-rockyou-source-review",
        title="Rockyou source review",
        definition="# Scenario",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="crack-user-hash",
                    title="Crack user hash",
                    kind="password_cracking",
                    phase="credential_access",
                    description="Crack the leaked password hash.",
                    implementation_steps=["Store a runtime-generated password hash."],
                    password_cracking=PasswordCrackingSpec(
                        wordlist="rockyou.txt",
                        hash_algorithm="SHA-256",
                        hash_runtime="php",
                        hash_api="hash",
                        hashcat_mode=1400,
                        target_crack_seconds=150,
                    ),
                )
            ]
        ),
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return gemini_response(
            {
                "approved": False,
                "summary": "The generated test does not inspect the server wordlist.",
                "findings": [
                    {
                        "step_id": "crack-user-hash",
                        "severity": "error",
                        "category": "acceptance_test_gap",
                        "repair_target": "source_code",
                        "affected_files": ["contents/scenario_manifest.json"],
                        "evidence": (
                            "No acceptance test proves that the selected password is contained "
                            "in rockyou.txt or checks its line_number."
                        ),
                        "remediation": "Add a test that reads the wordlist and verifies membership.",
                    }
                ],
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await GeminiGenerator(Settings(gemini_api_key="test-key"), client).review_source(
            MachineInformation(
                name="Rockyou boundary",
                visibility="private",
                theme="Hash cracking",
                difficulty="Medium",
            ),
            scenario,
            GeneratedSource(
                files=[SourceFile(path="contents/build.sh", content="#!/bin/bash\n")]
            ),
        )

    assert review.approved is True
    assert review.findings == []
    assert "Removed 1 finding(s)" in review.summary


@pytest.mark.asyncio
async def test_invalid_non_cve_cwe_review_is_rejected_before_routing() -> None:
    requests: list[dict] = []
    scenario = ScenarioDraft(
        scenario_id="scenario-sqli",
        title="SQL injection",
        definition="# SQL injection scenario",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="exploit-sqli-credentials",
                    title="Extract credentials with SQL injection",
                    kind="web_vulnerability",
                    phase="initial_access",
                    description="Use SQL injection to recover a training credential.",
                    implementation_steps=["Provision the vulnerable query."],
                    references=["https://cwe.mitre.org/data/definitions/89.html"],
                )
            ]
        ),
    )
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return gemini_response(
                {
                    "approved": False,
                    "summary": "The SQL injection step omits CWE-89.",
                    "findings": [
                        {
                            "step_id": "exploit-sqli-credentials",
                            "severity": "error",
                            "category": "semantic_mismatch",
                            "repair_target": "attack_graph",
                            "repair_fields": ["cwe_ids"],
                            "evidence": "The non-CVE step omits CWE-89.",
                            "remediation": "Add CWE-89 to cwe_ids.",
                        }
                    ],
                }
            )
        return gemini_response(
            {
                "approved": True,
                "summary": "The previous finding requested a schema-forbidden repair.",
                "findings": [],
            }
        )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await GeminiGenerator(
            Settings(
                gemini_api_key="test-key",
                generation_retries=2,
            ),
            client,
        ).review_scenario(
            MachineInformation(
                name="SQL injection",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            ),
            scenario,
        )

    assert review.approved is True
    assert len(requests) == 2
    second_prompt = requests[1]["contents"][0]["parts"][0]["text"]
    assert "attack_graph repair_fields must only contain" in second_prompt


@pytest.mark.asyncio
async def test_prose_mismatch_cannot_trigger_attack_graph_regeneration() -> None:
    scenario = ScenarioDraft(
        scenario_id="scenario-prose-mismatch",
        title="Prose mismatch",
        definition="# Scenario\n\nThe prose uses a different step name.",
        attack_graph=graph_without_objectives(),
    )
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return gemini_response(
                {
                    "approved": False,
                    "summary": "The prose and graph use different names.",
                    "findings": [
                        {
                            "step_id": "enumerate-web",
                            "severity": "error",
                            "category": "semantic_mismatch",
                            "repair_target": "attack_graph_regeneration",
                            "repair_fields": ["step_id"],
                            "evidence": "The scenario prose renamed the graph step.",
                            "remediation": "Regenerate the graph to match the prose.",
                        }
                    ],
                }
            )
        return gemini_response(
            {
                "approved": False,
                "summary": "The prose must use the authoritative graph ID.",
                "findings": [
                    {
                        "step_id": "enumerate-web",
                        "severity": "error",
                        "category": "semantic_mismatch",
                        "repair_target": "scenario_text",
                        "repair_fields": [],
                        "evidence": "The scenario prose renamed enumerate-web.",
                        "remediation": "Rename the prose step to enumerate-web.",
                    }
                ],
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        review = await GeminiGenerator(
            Settings(gemini_api_key="test-key", generation_retries=2), client
        ).review_scenario(
            MachineInformation(
                name="Prose mismatch",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            ),
            scenario,
        )

    assert review.findings[0].repair_target == "scenario_text"
    assert len(requests) == 2
    assert "prose mismatches must target scenario_text" in requests[1]["contents"][0][
        "parts"
    ][0]["text"]


@pytest.mark.asyncio
async def test_repeated_invalid_text_patch_is_returned_to_reviewer() -> None:
    requests: list[dict] = []
    scenario = ScenarioDraft(
        scenario_id="scenario-text-patch",
        title="Text patch",
        scenario_description="Inspect the machine and recover the flag.",
        definition="# Scenario\n\nThe existing sentence remains here.",
        attack_graph=graph_without_objectives(),
    )
    rejected = ScenarioReview(
        approved=False,
        summary="The negative control is missing.",
        findings=[
            ScenarioReviewFinding(
                severity="error",
                category="acceptance_test_gap",
                repair_target="scenario_text",
                evidence="No negative control is documented.",
                remediation="Add a negative control to the validation plan.",
            )
        ],
    )
    invalid_correction = {
        "scenario_description": None,
        "definition_replacements": [
            {
                "old": "This sentence does not exist in the document.",
                "new": "This sentence includes a negative control.",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) <= 2:
            return gemini_response(invalid_correction)
        return gemini_response(
            {
                "approved": True,
                "summary": "The prior text finding cannot be applied as requested.",
                "findings": [],
            }
        )

    class Observer:
        resume_scenario = scenario
        resume_review = rejected

        async def __call__(self) -> None:
            return None

        async def record_draft(self, *_args, **_kwargs) -> None:
            return None

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GeminiGenerator(
            Settings(
                gemini_api_key="test-key",
                generation_retries=2,
                scenario_generation_attempts=2,
            ),
            client,
        ).generate_scenario(
            MachineInformation(
                name="Text patch",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            ),
            on_attempt=Observer(),
        )

    assert result == scenario
    assert len(requests) == 3
    retry_prompt = requests[1]["contents"][0]["parts"][0]["text"]
    reconsideration_prompt = requests[2]["contents"][0]["parts"][0]["text"]
    assert 'rejected old="This sentence does not exist' in retry_prompt
    assert "受理されなかった前回出力" in retry_prompt
    assert "scenario_correction_validation_failure" in reconsideration_prompt
    assert "This sentence does not exist" in reconsideration_prompt
    assert "found 0 occurrences" in reconsideration_prompt


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
        if request_number == 2:
            return gemini_response(
                {
                    "scenario_description": f"Player introduction attempt {request_number}.",
                    "definition": (
                        f"# Generated scenario attempt {request_number}\n\n"
                        "Parent directory mode is unspecified."
                    ),
                }
            )
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
        if request_number == 4:
            return gemini_response(
                {
                    "scenario_description": None,
                    "definition_replacements": [
                        {
                            "old": "Parent directory mode is unspecified.",
                            "new": "Specify and validate the parent directory owner, group, and mode.",
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
    attempts = 0

    async def record_attempt() -> None:
        nonlocal attempts
        attempts += 1

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        scenario = await GeminiGenerator(settings, client).generate_scenario(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy"),
            on_attempt=record_attempt,
        )

    assert scenario.definition.endswith("parent directory owner, group, and mode.")
    assert scenario.scenario_description == "Player introduction attempt 2."
    assert attempts == 2
    assert len(requests) == 5
    retry_prompt = requests[3]["contents"][0]["parts"][0]["text"]
    verification_prompt = requests[4]["contents"][0]["parts"][0]["text"]
    assert "scenario_semantic_review" in retry_prompt
    assert "permission_blocker" in retry_prompt
    assert "No mode is specified for the parent directory." in retry_prompt
    assert "Specify and validate owner, group, and mode." in retry_prompt
    assert "# Generated scenario attempt 2" in retry_prompt
    assert "文書全体を生成し直してはいけません" in retry_prompt
    assert "scenario_repair_verification" in verification_prompt
    assert "新しいフル監査ではなく" in verification_prompt
    assert "より細かい実装要件を後出し" in verification_prompt
    graph_prompts = [
        request
        for request in requests
        if "攻撃経路を設計するアーキテクト" in request["contents"][0]["parts"][0]["text"]
    ]
    assert len(graph_prompts) == 1


@pytest.mark.asyncio
async def test_generate_scenario_resumes_persisted_rejected_draft(monkeypatch) -> None:
    machine = MachineInformation(
        name="Resume Test", visibility="private", theme="Web", difficulty="Easy"
    )
    persisted = ScenarioDraft(
        scenario_id="scenario-persisted",
        title="Resume Test",
        scenario_description="Persisted introduction.",
        definition="# Persisted scenario\n\nKeep this implementation plan.",
        attack_graph=graph_without_objectives(),
    )
    rejected = ScenarioReview(
        approved=False,
        summary="The negative control is missing.",
        findings=[
            ScenarioReviewFinding(
                severity="error",
                category="acceptance_test_gap",
                evidence="No negative control is defined.",
                remediation="Add a negative control without changing the attack path.",
            )
        ],
    )

    class Observer:
        resume_scenario = persisted
        resume_review = rejected

        def __init__(self) -> None:
            self.attempts = 0
            self.recorded: list[tuple[ScenarioDraft, ScenarioReview | None]] = []

        async def __call__(self) -> None:
            self.attempts += 1

        async def record_draft(
            self, scenario: ScenarioDraft, review: ScenarioReview | None = None
        ) -> None:
            self.recorded.append((scenario, review))

    observer = Observer()
    prompts: list[str] = []
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)

        async def should_not_generate_graph(*_args, **_kwargs):
            raise AssertionError("persisted attack graph should be reused")

        async def generate(prompt, **_kwargs):
            prompts.append(prompt)
            return json.dumps(
                {
                    "scenario_description": None,
                    "definition_replacements": [
                        {
                            "old": "Keep this implementation plan.",
                            "new": "Keep this implementation plan and add a negative control.",
                        }
                    ],
                }
            )

        async def approve(_machine, _scenario, **_kwargs):
            return ScenarioReview(approved=True, summary="Persisted draft was repaired.")

        monkeypatch.setattr(generator, "_draft_attack_graph", should_not_generate_graph)
        monkeypatch.setattr(generator, "_generate", generate)
        monkeypatch.setattr(generator, "review_scenario", approve)
        revised = await generator.generate_scenario(machine, on_attempt=observer)

    assert observer.attempts == 1
    assert revised.scenario_id == "scenario-persisted"
    assert revised.definition.endswith("add a negative control.")
    assert revised.scenario_description == "Persisted introduction."
    assert "# Persisted scenario" in prompts[0]
    assert "No negative control is defined." in prompts[0]
    assert len(observer.recorded) == 2
    assert observer.recorded[-1][1] is not None
    assert observer.recorded[-1][1].approved is True


@pytest.mark.asyncio
async def test_scenario_correction_uses_only_the_current_review(monkeypatch) -> None:
    machine = MachineInformation(
        name="Focused Repair", visibility="private", theme="Web", difficulty="Easy"
    )
    persisted = ScenarioDraft(
        scenario_id="scenario-focused-repair",
        title="Focused Repair",
        scenario_description="Inspect the machine and obtain the flags.",
        definition="# Scenario\n\nBase implementation plan.",
        attack_graph=graph_without_objectives(),
    )
    first_review = ScenarioReview(
        approved=False,
        summary="First issue.",
        findings=[
            ScenarioReviewFinding(
                step_id="enumerate",
                severity="error",
                category="implementation_gap",
                evidence="OBSOLETE_FIRST_DIAGNOSTIC",
                remediation="Apply the first focused repair.",
            )
        ],
    )

    class Observer:
        resume_scenario = persisted
        resume_review = first_review

        async def __call__(self) -> None:
            return None

        async def record_draft(self, *_args, **_kwargs) -> None:
            return None

    correction_prompts: list[str] = []
    review_calls = 0
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(
            Settings(gemini_api_key="test-key", scenario_generation_attempts=2), client
        )

        async def generate(prompt, **_kwargs):
            correction_prompts.append(prompt)
            if len(correction_prompts) == 1:
                old = "Base implementation plan."
                new = "Base implementation plan with the first repair."
            else:
                old = "Base implementation plan with the first repair."
                new = "Base implementation plan with both repairs."
            return json.dumps(
                {
                    "scenario_description": None,
                    "definition_replacements": [{"old": old, "new": new}],
                }
            )

        async def review(_machine, _scenario, **_kwargs):
            nonlocal review_calls
            review_calls += 1
            if review_calls == 1:
                return ScenarioReview(
                    approved=False,
                    summary="Second issue.",
                    findings=[
                        ScenarioReviewFinding(
                            step_id="enumerate",
                            severity="error",
                            category="implementation_gap",
                            evidence="CURRENT_SECOND_DIAGNOSTIC",
                            remediation="Apply the second focused repair.",
                        )
                    ],
                )
            return ScenarioReview(approved=True, summary="Focused repairs are complete.")

        monkeypatch.setattr(generator, "_generate", generate)
        monkeypatch.setattr(generator, "review_scenario", review)
        scenario = await generator.generate_scenario(machine, on_attempt=Observer())

    assert scenario.definition.endswith("both repairs.")
    assert "OBSOLETE_FIRST_DIAGNOSTIC" in correction_prompts[0]
    assert "CURRENT_SECOND_DIAGNOSTIC" in correction_prompts[1]
    assert "OBSOLETE_FIRST_DIAGNOSTIC" not in correction_prompts[1]


@pytest.mark.asyncio
async def test_attack_graph_revision_repairs_instructions_but_preserves_verified_facts(
    monkeypatch,
) -> None:
    original = verified_cve_graph()
    revised_payload = original.model_dump(mode="json")
    revised_payload["steps"][0]["description"] = (
        "Trigger the verified vulnerability using the consistent configuration."
    )
    revised_payload["steps"][0]["implementation_steps"] = [
        "Install Nginx 1.26.3-3.",
        'Configure return 200 "$id - $var".',
    ]
    review = ScenarioReview(
        approved=False,
        summary="The attack graph still contains stale setup instructions.",
        findings=[
            ScenarioReviewFinding(
                step_id="nginx-cve",
                severity="error",
                category="semantic_mismatch",
                repair_target="attack_graph",
                repair_fields=["description", "implementation_steps"],
                evidence=(
                    "The attack graph implementation_steps says 1.20.1 and return 200 '$var'."
                ),
                remediation=("Use 1.26.3-3 and the same return 200 configuration as the scenario."),
            )
        ],
    )
    prompts: list[str] = []
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)

        async def generate(prompt, **_kwargs):
            prompts.append(prompt)
            return json.dumps(revised_payload)

        monkeypatch.setattr(generator, "_generate", generate)
        revised = await generator._revise_attack_graph(
            MachineInformation(
                name="Nginx Engine",
                visibility="private",
                theme="Web security",
                difficulty="Very Easy",
            ),
            original,
            review,
        )

    assert revised.steps[0].implementation_steps[0] == "Install Nginx 1.26.3-3."
    assert revised.steps[0].vulnerable_version == original.steps[0].vulnerable_version
    assert revised.steps[0].cve_description == original.steps[0].cve_description
    assert "公式検証済み情報なので変更しない" in prompts[0]
    assert "モデル制約または上記の変更禁止フィールドと衝突" in prompts[0]


def test_review_model_rejects_immutable_targeted_graph_field() -> None:
    with pytest.raises(ValueError, match="attack_graph repair_fields must only contain"):
        ScenarioReview(
            approved=False,
            summary="An immutable field must change.",
            findings=[
                ScenarioReviewFinding(
                    step_id="enumerate-web",
                    severity="error",
                    category="semantic_mismatch",
                    repair_target="attack_graph",
                    repair_fields=["cwe_ids"],
                    evidence="The immutable cwe_ids field is allegedly wrong.",
                    remediation="Change cwe_ids.",
                )
            ],
        )


@pytest.mark.asyncio
async def test_attack_graph_revision_retries_output_shape_errors(monkeypatch) -> None:
    graph = graph_without_objectives()
    review = ScenarioReview(
        approved=False,
        summary="Clarify the step description.",
        findings=[
            ScenarioReviewFinding(
                step_id="enumerate-web",
                severity="error",
                category="semantic_mismatch",
                repair_target="attack_graph",
                repair_fields=["description"],
                evidence="The current description is ambiguous.",
                remediation="Clarify the description.",
            )
        ],
    )
    malformed = graph.model_dump(mode="json")
    del malformed["steps"][0]["title"]
    corrected = graph.model_dump(mode="json")
    corrected["steps"][0]["description"] = "Inspect the exposed training service."
    responses = [malformed, corrected]
    prompts: list[str] = []
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(
            Settings(gemini_api_key="test-key", generation_retries=2), client
        )

        async def generate(prompt, **_kwargs):
            prompts.append(prompt)
            return json.dumps(responses.pop(0))

        monkeypatch.setattr(generator, "_generate", generate)
        revised = await generator._revise_attack_graph(
            MachineInformation(
                name="Test",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            ),
            graph,
            review,
        )

    assert revised.steps[0].description == "Inspect the exposed training service."
    assert len(prompts) == 2
    assert "Field required" in prompts[1]


def test_review_model_rejects_phase_change_before_reconsideration_cycle() -> None:
    with pytest.raises(ValueError, match="attack_graph repair_fields must only contain"):
        ScenarioReview(
            approved=False,
            summary="The phase must change.",
            findings=[
                ScenarioReviewFinding(
                    step_id="enumerate-web",
                    severity="error",
                    category="semantic_mismatch",
                    repair_target="attack_graph",
                    repair_fields=["phase"],
                    evidence="The phase is allegedly incorrect.",
                    remediation="Change the immutable phase field.",
                )
            ],
        )


@pytest.mark.asyncio
async def test_resumed_graph_review_revises_graph_before_scenario_text(monkeypatch) -> None:
    original_graph = verified_cve_graph()
    persisted = ScenarioDraft(
        scenario_id="scenario-persisted",
        title="Nginx Engine",
        scenario_description="Persisted introduction.",
        definition="# Persisted scenario\n\nInstall Nginx 1.20.1.",
        attack_graph=original_graph,
    )
    rejected = ScenarioReview(
        approved=False,
        summary="The attack graph contains a stale version.",
        findings=[
            ScenarioReviewFinding(
                step_id="nginx-cve",
                severity="error",
                category="semantic_mismatch",
                repair_target="attack_graph",
                repair_fields=["implementation_steps"],
                evidence="The attack graph implementation_steps still says Nginx 1.20.1.",
                remediation="Change that setup instruction to Nginx 1.26.3-3.",
            )
        ],
    )

    class Observer:
        resume_scenario = persisted
        resume_review = rejected

        def __init__(self) -> None:
            self.recorded: list[tuple[ScenarioDraft, ScenarioReview | None]] = []

        async def __call__(self) -> None:
            return None

        async def record_draft(
            self, scenario: ScenarioDraft, review: ScenarioReview | None = None
        ) -> None:
            self.recorded.append((scenario, review))

    observer = Observer()
    revised_graph = original_graph.model_copy(deep=True)
    revised_graph.steps[0].implementation_steps[0] = "Install Nginx 1.26.3-3."
    revision_calls = 0
    scenario_prompts: list[str] = []
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)

        async def should_not_generate_graph(*_args, **_kwargs):
            raise AssertionError("the persisted graph should be revised, not regenerated")

        async def revise(_machine, graph, review):
            nonlocal revision_calls
            revision_calls += 1
            assert graph == original_graph
            assert review == rejected
            return revised_graph

        async def generate(prompt, **_kwargs):
            scenario_prompts.append(prompt)
            return json.dumps(
                {
                    "scenario_description": None,
                    "definition_replacements": [
                        {
                            "old": "Install Nginx 1.20.1.",
                            "new": "Install Nginx 1.26.3-3.",
                        }
                    ],
                }
            )

        async def approve(_machine, _scenario, **_kwargs):
            return ScenarioReview(approved=True, summary="The mismatch was repaired.")

        monkeypatch.setattr(generator, "_draft_attack_graph", should_not_generate_graph)
        monkeypatch.setattr(generator, "_revise_attack_graph", revise)
        monkeypatch.setattr(generator, "_generate", generate)
        monkeypatch.setattr(generator, "review_scenario", approve)
        result = await generator.generate_scenario(
            MachineInformation(
                name="Nginx Engine",
                visibility="private",
                theme="Web security",
                difficulty="Very Easy",
            ),
            on_attempt=observer,
        )

    assert revision_calls == 1
    assert result.attack_graph == revised_graph
    assert "Install Nginx 1.26.3-3." in scenario_prompts[0]
    assert observer.recorded[0][0].attack_graph == revised_graph
    assert observer.recorded[0][1] is None


def test_attack_graph_revision_rejects_changes_to_verified_facts() -> None:
    original = verified_cve_graph()
    changed = original.model_copy(deep=True)
    changed.steps[0].vulnerable_version = "1.20.1"

    with pytest.raises(ValueError, match="vulnerable_version"):
        GeminiGenerator._validate_attack_graph_revision(original, changed)


def test_graph_revision_routing_uses_repair_target_not_finding_text() -> None:
    prose_only = ScenarioReview(
        approved=False,
        summary="The attack graph wording appears in this summary.",
        findings=[
            ScenarioReviewFinding(
                severity="error",
                category="semantic_mismatch",
                repair_target="scenario_text",
                evidence="The attack graph and implementation steps are discussed here.",
                remediation="Revise only the scenario prose.",
            )
        ],
    )
    structured_graph_repair = ScenarioReview(
        approved=False,
        summary="A verified field needs a targeted correction.",
        findings=[
            ScenarioReviewFinding(
                severity="error",
                category="semantic_mismatch",
                repair_target="attack_graph",
                repair_fields=["implementation_steps"],
                evidence="The recorded setup instruction is stale.",
                remediation="Correct the structured setup instruction.",
            )
        ],
    )

    assert GeminiGenerator._review_requires_graph_revision(prose_only) is False
    assert GeminiGenerator._review_requires_graph_revision(structured_graph_repair) is True


def test_structural_graph_review_routes_to_regeneration() -> None:
    review = ScenarioReview(
        approved=False,
        summary="The dependency graph must be rebuilt.",
        findings=[
            ScenarioReviewFinding(
                severity="error",
                category="semantic_mismatch",
                repair_target="attack_graph_regeneration",
                repair_fields=["kind", "requires"],
                evidence="The current step kind cannot represent the required dependency.",
                remediation="Regenerate the graph with a valid dependency structure.",
            )
        ],
    )

    assert GeminiGenerator._review_requires_graph_regeneration(review) is True
    assert GeminiGenerator._review_requires_graph_revision(review) is False


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
        if request_number == 2:
            return gemini_response(
                {
                    "scenario_description": f"Player introduction attempt {request_number}.",
                    "definition": (
                        f"# Generated scenario attempt {request_number}\n\n"
                        "The credential is available without the prerequisite."
                    ),
                }
            )
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
                            "repair_target": "attack_graph_regeneration",
                            "repair_fields": ["requires"],
                            "evidence": "The credential is available without the prerequisite.",
                            "remediation": "Make the prerequisite output necessary.",
                        }
                    ],
                }
            )
        if request_number == 5:
            return gemini_response(
                {
                    "scenario_description": None,
                    "definition_replacements": [
                        {
                            "old": "The credential is available without the prerequisite.",
                            "new": "The regenerated prerequisite output is required for the credential.",
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

    assert scenario.definition.endswith("is required for the credential.")
    assert len(requests) == 6
    regenerated_graph_prompt = requests[3]["contents"][0]["parts"][0]["text"]
    regenerated_scenario_prompt = requests[4]["contents"][0]["parts"][0]["text"]
    assert "broken_chain" in regenerated_graph_prompt
    assert "broken_chain" in regenerated_scenario_prompt


@pytest.mark.asyncio
async def test_generated_graph_issue_cannot_be_routed_to_user_input() -> None:
    graph = {
        "objectives": [],
        "steps": [
            {
                "step_id": "exploit-cve",
                "title": "Exploit the service",
                "kind": "custom",
                "phase": "initial_access",
                "description": "Exercise the requested training path.",
                "requires": [],
                "achieves": [],
                "cve_id": None,
                "implementation_steps": ["Prepare the service."],
            }
        ],
    }
    responses = [
        graph,
        {
            "scenario_description": "Training scenario.",
            "definition": "# Training scenario",
        },
        {
            "approved": False,
            "summary": "Stable RCE is not justified at the requested difficulty.",
            "findings": [
                {
                    "step_id": "exploit-cve",
                    "severity": "error",
                    "category": "unsupported_assumption",
                    "repair_target": "user_input",
                    "repair_fields": ["difficulty"],
                    "evidence": "The design assumes a stable RCE without an exploit method.",
                    "remediation": "Raise the difficulty or relax the required impact.",
                }
            ],
        },
        {
            "approved": True,
            "summary": "The generated design must be repaired without changing user input.",
            "findings": [],
        },
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return gemini_response(responses.pop(0))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(
            Settings(gemini_api_key="test-key", scenario_generation_attempts=3),
            client,
        )
        scenario = await generator.generate_scenario(
            MachineInformation(
                name="Test",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            )
        )

    assert scenario.scenario_id
    assert responses == []


@pytest.mark.asyncio
async def test_explicit_input_contradiction_requests_input_revision() -> None:
    graph = {
        "objectives": [
            {
                "objective_id": "system-flag",
                "objective_type": "system_flag",
                "description": (
                    "Do not grant sudo for vim, and obtain the flag through sudo vim."
                ),
            }
        ],
        "steps": [
            {
                "step_id": "privilege-escalation",
                "title": "Escalate privileges",
                "kind": "privilege_escalation",
                "phase": "privilege_escalation",
                "description": "Exercise the requested training path.",
                "requires": [],
                "achieves": ["system-flag"],
                "cve_id": None,
                "implementation_steps": ["Prepare the service."],
            }
        ],
    }
    responses = [
        graph,
        {
            "scenario_description": "Training scenario.",
            "definition": "# Training scenario",
        },
        {
            "approved": False,
            "summary": "The two explicit flag requirements contradict each other.",
            "findings": [
                {
                    "step_id": None,
                    "severity": "error",
                    "category": "input_contradiction",
                    "repair_target": "user_input",
                    "repair_fields": ["system_flag_details"],
                    "evidence": "The input both forbids sudo vim and requires sudo vim.",
                    "remediation": "Remove either of the contradictory sudo vim requirements.",
                }
            ],
        },
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return gemini_response(responses.pop(0))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(
            Settings(gemini_api_key="test-key", scenario_generation_attempts=3),
            client,
        )
        with pytest.raises(ScenarioInputRevisionRequiredError) as captured:
            await generator.generate_scenario(
                MachineInformation(
                    name="Test",
                    visibility="private",
                    theme="Web",
                    difficulty="Easy",
                    needs_system_flag=True,
                    system_flag_details=(
                        "Do not grant sudo for vim, and obtain the flag through sudo vim."
                    ),
                )
            )

    assert captured.value.code == "scenario_input_revision_required"
    assert captured.value.findings[0]["category"] == "input_contradiction"
    assert captured.value.findings[0]["repair_fields"] == ["system_flag_details"]
    assert responses == []


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
    assert "responseJsonSchema" in requests[0]["generationConfig"]
    assert "tools" not in requests[0]


@pytest.mark.asyncio
async def test_attack_graph_generation_clears_misplaced_cve_installation_metadata() -> None:
    graph = {
        "objectives": [],
        "steps": [
            {
                "step_id": "setup-vulnerable-nginx",
                "title": "Set up Nginx",
                "kind": "setup",
                "phase": "reconnaissance",
                "description": "Prepare the service used by the following CVE step.",
                "requires": [],
                "achieves": [],
                "cve_id": None,
                "cve_title": "Incorrectly copied CVE title",
                "cve_description": "Incorrectly copied CVE description",
                "cwe_ids": ["CWE-123"],
                "installation_artifact": "vendor_release_binary",
                "artifact_source": "https://example.invalid/nginx.tar.gz",
                "source_build_reason": "Incorrectly copied build evidence",
                "software": "Nginx",
                "vulnerable_version": "1.26.3-3",
                "os_compatible": True,
                "compatibility_reason": "Runs on the target OS.",
                "installation_method": "Install the package.",
                "implementation_steps": ["Install the service."],
                "references": [],
            }
        ],
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return gemini_response(graph)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        parsed = await GeminiGenerator(
            Settings(gemini_api_key="test-key"), client
        )._draft_attack_graph(
            MachineInformation(
                name="Nginx Engine",
                visibility="private",
                theme="Web security",
                difficulty="Very Easy",
            ),
            [],
        )

    step = parsed.steps[0]
    assert step.kind == "setup"
    assert step.installation_artifact is None
    assert step.artifact_source is None
    assert step.source_build_reason is None
    assert step.cve_title is None
    assert step.cve_description is None
    assert step.cwe_ids == []
    assert step.installation_method == "Install the package."


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


def test_debian_package_requires_target_release_osv_evidence() -> None:
    verification = CVEVerification(
        software="Linux kernel",
        vulnerable_version="4.4.0",
        os_compatible=True,
        compatibility_reason="candidate",
        installation_artifact="os_repository_package",
        artifact_source="Debian package repository",
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

    GeminiGenerator._enforce_debian_package_evidence(verification, evidence)

    assert verification.os_compatible is False
    assert "Debian:13" in verification.compatibility_reason


def test_official_cve_facts_derive_title_from_description_when_cna_title_is_missing() -> None:
    facts = GeminiGenerator._official_cve_facts(
        "CVE-2025-55182",
        {
            "state": "PUBLISHED",
            "title": None,
            "descriptions": [
                {
                    "lang": "en",
                    "value": (
                        "React Server Components contain a remote code execution issue. "
                        "An unauthenticated attacker can exploit it."
                    ),
                }
            ],
            "problem_types": [],
            "references": [],
            "official_cve_url": "https://www.cve.org/CVERecord?id=CVE-2025-55182",
        },
    )

    assert facts["title"] == (
        "React Server Components contain a remote code execution issue."
    )
    assert facts["description"] == (
        "React Server Components contain a remote code execution issue. "
        "An unauthenticated attacker can exploit it."
    )


def test_official_cve_facts_still_require_an_official_description() -> None:
    with pytest.raises(
        ValueError, match="CVE-2025-55182 official record is missing a description"
    ):
        GeminiGenerator._official_cve_facts(
            "CVE-2025-55182",
            {
                "state": "PUBLISHED",
                "title": None,
                "descriptions": [],
            },
        )


def test_cve_verification_rejects_unjustified_source_build() -> None:
    with pytest.raises(ValueError, match="source build requires evidence"):
        CVEVerification(
            software="Example service",
            vulnerable_version="1.2.3",
            os_compatible=True,
            compatibility_reason="Source compiles on the target OS",
            installation_artifact="source_build",
            artifact_source="official source archive",
            installation_method="compile from source",
            implementation_steps=["configure", "make", "install"],
        )


def test_cve_verification_accepts_source_build_after_binary_sources_checked() -> None:
    verification = CVEVerification(
        software="Example service",
        vulnerable_version="1.2.3",
        os_compatible=True,
        compatibility_reason="Source compiles on the target OS",
        installation_artifact="source_build",
        artifact_source="official source archive",
        source_build_reason=(
            "Debian snapshot and vendor repositories have no package for this architecture; "
            "the vendor release publishes source only."
        ),
        installation_method="compile from source",
        implementation_steps=["configure", "make", "install"],
    )

    assert verification.installation_artifact == "source_build"


@pytest.mark.asyncio
async def test_only_cve_steps_are_enriched_with_external_evidence() -> None:
    verification = {
        "software": "Example service",
        "vulnerable_version": "1.2.3",
        "os_compatible": True,
        "compatibility_reason": "The release archive runs on the target OS",
        "installation_artifact": "vendor_release_binary",
        "artifact_source": "official vendor release",
        "source_build_reason": None,
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
                    "cveMetadata": {"state": "PUBLISHED"},
                    "containers": {
                        "cna": {
                            "title": "Example application vulnerability",
                            "descriptions": [{"lang": "en", "value": "Example application issue"}],
                            "problemTypes": [{"descriptions": [{"cweId": "CWE-79"}]}],
                            "affected": [{"product": "Example service"}],
                            "references": [],
                        }
                    },
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
    assert verified.steps[0].title == ("CVE-2026-1234: Example application vulnerability")
    assert verified.steps[0].description == "Example application issue"
    assert verified.steps[0].cve_title == "Example application vulnerability"
    assert verified.steps[0].cve_description == "Example application issue"
    assert verified.steps[0].cwe_ids == ["CWE-79"]
    assert verified.steps[0].installation_artifact == "vendor_release_binary"
    assert verified.steps[0].artifact_source == "official vendor release"
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
            return gemini_response(
                {
                    "scenario_description": "Investigate the training machine and capture the flag.",
                    "definition": "# Generated scenario",
                }
            )
        return gemini_response(
            {"approved": True, "summary": "Scenario is internally consistent.", "findings": []}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)
        scenario = await generator.generate_scenario(
            MachineInformation(name="Test", visibility="private", theme="Web", difficulty="Easy")
        )

    assert scenario.definition == "# Generated scenario"
    assert scenario.scenario_description == (
        "Investigate the training machine and capture the flag."
    )
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


def openai_response(value) -> httpx.Response:
    generated_text = value if isinstance(value, str) else json.dumps(value)
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": generated_text}],
                }
            ],
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["gemini", "openai"])
async def test_provider_usage_is_recorded_for_current_session(provider: str) -> None:
    recorded: list[tuple[str, int, int, int]] = []

    async def record(session_id: str, input_tokens: int, output_tokens: int, total: int):
        recorded.append((session_id, input_tokens, output_tokens, total))

    if provider == "gemini":
        response = gemini_response("generated")
        payload = json.loads(response.content)
        payload["usageMetadata"] = {
            "promptTokenCount": 120,
            "candidatesTokenCount": 30,
            "totalTokenCount": 155,
        }
        response = httpx.Response(200, json=payload)
        settings = Settings(gemini_api_key="test-key")
        generator_type = GeminiGenerator
    else:
        response = openai_response("generated")
        payload = json.loads(response.content)
        payload["usage"] = {
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
        }
        response = httpx.Response(200, json=payload)
        settings = Settings(
            ai_provider="openai", openai_api_key="test-openai-key", _env_file=None
        )
        generator_type = OpenAIGenerator

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: response)
    ) as client:
        generator = generator_type(settings, client)
        generator.set_token_usage_recorder(record)
        token = begin_token_usage_session("session-token-test")
        try:
            assert await generator._generate("prompt") == "generated"
        finally:
            end_token_usage_session(token)

    expected_total = 155 if provider == "gemini" else 150
    assert recorded == [("session-token-test", 120, 30, expected_total)]
