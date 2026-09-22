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
    ScenarioReviewFinding,
    SourceFile,
    SourceReview,
)
from ai_server.services.ai import CVEVerification, GeminiGenerator
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
async def test_invalid_non_cve_cwe_revision_is_returned_to_reviewer() -> None:
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
    rejected = ScenarioReview(
        approved=False,
        summary="The SQL injection step omits CWE-89.",
        findings=[
            ScenarioReviewFinding(
                step_id="exploit-sqli-credentials",
                severity="error",
                category="semantic_mismatch",
                repair_target="attack_graph",
                repair_fields=["cwe_ids"],
                evidence=(
                    "The non-CVE step has cwe_ids=[] while references contains "
                    "https://cwe.mitre.org/data/definitions/89.html (CWE-89)."
                ),
                remediation="Add CWE-89 to cwe_ids.",
            )
        ],
    )
    invalid_revision = scenario.attack_graph.model_dump(mode="json")
    invalid_revision["steps"][0]["cwe_ids"] = ["CWE-89"]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return gemini_response(invalid_revision)
        return gemini_response(
            {
                "approved": True,
                "summary": "The previous CWE finding conflicted with the graph model.",
                "findings": [],
            }
        )

    class Observer:
        resume_scenario = scenario
        resume_review = rejected

        def __init__(self) -> None:
            self.attempts = 0

        async def __call__(self) -> None:
            self.attempts += 1

        async def record_draft(self, *_args, **_kwargs) -> None:
            return None

    observer = Observer()
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
                name="SQL injection",
                visibility="private",
                theme="Web",
                difficulty="Easy",
            ),
            on_attempt=observer,
        )

    assert result == scenario
    assert observer.attempts == 1
    assert len(requests) == 2
    second_prompt = requests[1]["contents"][0]["parts"][0]["text"]
    assert "前回レビューの再検討資料" in second_prompt
    assert "The SQL injection step omits CWE-89" in second_prompt
    assert "official CVE facts are only valid when kind is cve" in second_prompt
    assert '"attempted_revision"' in second_prompt
    assert '\\"cwe_ids\\": [' in second_prompt


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
    assert "scenario_semantic_review" in retry_prompt
    assert "permission_blocker" in retry_prompt
    assert "No mode is specified for the parent directory." in retry_prompt
    assert "Specify and validate owner, group, and mode." in retry_prompt
    assert "# Generated scenario attempt 2" in retry_prompt
    assert "文書全体を生成し直してはいけません" in retry_prompt
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

        async def approve(_machine, _scenario):
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
                remediation=(
                    "Use 1.26.3-3 and the same return 200 configuration as the scenario."
                ),
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


@pytest.mark.asyncio
async def test_attack_graph_revision_surfaces_semantic_validation_without_retrying(
    monkeypatch,
) -> None:
    graph = graph_without_objectives()
    review = ScenarioReview(
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
    invalid_revision = graph.model_dump(mode="json")
    invalid_revision["steps"][0]["cwe_ids"] = ["CWE-89"]
    calls = 0
    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test-key"), client)

        async def generate(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return json.dumps(invalid_revision)

        monkeypatch.setattr(generator, "_generate", generate)
        with pytest.raises(ValueError, match="revision validation failed"):
            await generator._revise_attack_graph(
                MachineInformation(
                    name="Test",
                    visibility="private",
                    theme="Web",
                    difficulty="Easy",
                ),
                graph,
                review,
            )

    assert calls == 1


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


@pytest.mark.asyncio
async def test_repeated_revision_validation_failure_stops_reconsideration_cycle() -> None:
    scenario = ScenarioDraft(
        scenario_id="scenario-cycle",
        title="Cycle test",
        definition="# Cycle test",
        attack_graph=graph_without_objectives(),
    )
    rejected = ScenarioReview(
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
    invalid_revision = scenario.attack_graph.model_dump(mode="json")
    invalid_revision["steps"][0]["phase"] = "initial_access"
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) in {1, 3}:
            return gemini_response(invalid_revision)
        return gemini_response(rejected.model_dump(mode="json"))

    class Observer:
        resume_scenario = scenario
        resume_review = rejected

        async def __call__(self) -> None:
            return None

        async def record_draft(self, *_args, **_kwargs) -> None:
            return None

        async def record_failure(self, *_args, **_kwargs) -> None:
            return None

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiGenerator(
            Settings(gemini_api_key="test-key", scenario_generation_attempts=3), client
        )
        with pytest.raises(RuntimeError, match="could not pass attack-graph validation"):
            await generator.generate_scenario(
                MachineInformation(
                    name="Cycle test",
                    visibility="private",
                    theme="Web",
                    difficulty="Easy",
                ),
                on_attempt=Observer(),
            )

    assert len(requests) == 3


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

        async def approve(_machine, _scenario):
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
async def test_terminal_unsupported_assumption_requests_input_revision() -> None:
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
                    "evidence": "The design assumes a stable RCE without an exploit method.",
                    "remediation": "Raise the difficulty or relax the required impact.",
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
                )
            )

    assert captured.value.code == "scenario_input_revision_required"
    assert captured.value.findings[0]["category"] == "unsupported_assumption"
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
    schema = requests[0]["generationConfig"]["responseJsonSchema"]
    schema_json = json.dumps(schema)
    assert "$defs" in schema
    for filtered_key in ("default", "maxItems", "maxLength", "minLength", "pattern"):
        assert f'"{filtered_key}":' not in schema_json


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
                            "descriptions": [
                                {"lang": "en", "value": "Example application issue"}
                            ],
                            "problemTypes": [
                                {"descriptions": [{"cweId": "CWE-79"}]}
                            ],
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
    assert verified.steps[0].title == (
        "CVE-2026-1234: Example application vulnerability"
    )
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
