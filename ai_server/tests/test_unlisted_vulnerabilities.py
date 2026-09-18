from __future__ import annotations

import json

import httpx
import pytest
from test_api_flow import FakeSessionRepository
from test_skill_planning import Generator, catalog, decision, graph
from test_skills import FakeSkillRepository, machine, scenario

from ai_server.config import Settings
from ai_server.main import create_app
from ai_server.models import MachineInformation
from ai_server.prompts import attack_graph_prompt, code_prompt
from ai_server.services.ai import GeminiGenerator
from ai_server.services.stub_ai import StubGenerator
from ai_server.skills.models import ScenarioSkillContexts, SkillPhase
from ai_server.skills.planning import SemanticSkillPlanner, context_for_graph, context_from_plan
from ai_server.skills.service import NoopSkillService, SkillService


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_catalog", [False, True])
async def test_no_reference_can_still_generate_all_phases(tmp_path, empty_catalog):
    items = [] if empty_catalog else catalog(tmp_path)
    generate = Generator(decision())
    repository = FakeSkillRepository(items)
    service = SkillService(
        repository,
        max_active=32,
        max_per_phase=8,
        max_context_chars=50000,
        planner=SemanticSkillPlanner(generate, model="test"),
    )
    for phase in SkillPhase:
        assert (await service.resolve("session", phase, machine())).skills == []
    assert len(generate.prompts) == 1
    report = await service.selection_report("session")
    assert report["selection_policy"] == "advisory"
    assert report["plan"]["skills"] == [] and report["plan"]["reason"]


@pytest.mark.asyncio
async def test_no_matching_reference_keeps_common_cve_guidance(tmp_path):
    plan = await SemanticSkillPlanner(Generator(decision("cve"), decision()), model="test").plan(
        machine(), catalog(tmp_path)
    )
    assert plan.skills[0].name == "cve"
    assert plan.skills[0].selected_reference_ids == []
    assert plan.skills[0].reference_mode == "candidates"
    context = context_from_plan(
        plan, SkillPhase.SCENARIO, machine(), max_per_phase=8, max_context_chars=50000
    )
    assert (
        context_for_graph(context, scenario().attack_graph).skills[0].selected_reference_ids == []
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("choices", [None, []])
async def test_unlisted_explicit_cve_is_required_even_without_skills(choices):
    m = MachineInformation.model_validate(
        machine().model_dump() | {"skill_names": choices, "cve_ids": ["CVE-2025-9999"]}
    )
    plan = await SemanticSkillPlanner(Generator(), model="test").plan(m, [])
    assert plan.skills == []
    contexts = ScenarioSkillContexts()
    GeminiGenerator._validate_skill_cves(graph("CVE-2025-9999", "CVE-2025-8888"), contexts, m)
    with pytest.raises(ValueError, match="requested CVEs"):
        GeminiGenerator._validate_skill_cves(graph("CVE-2025-8888"), contexts, m)
    assert "CVE-2025-9999" in attack_graph_prompt(m, [], 2024)
    assert (await NoopSkillService().resolve("session", SkillPhase.ATTACK_GRAPH, m)).skills == []


@pytest.mark.asyncio
async def test_mixed_explicit_cves_only_load_available_reference(tmp_path):
    m = machine().model_copy(update={"cve_ids": ["CVE-2025-1111", "CVE-2025-9999"]})
    plan = await SemanticSkillPlanner(Generator(), model="test").plan(m, catalog(tmp_path))
    assert plan.skills[0].selected_reference_ids == ["CVE-2025-1111"]
    context = context_from_plan(
        plan, SkillPhase.ATTACK_GRAPH, m, max_per_phase=8, max_context_chars=50000
    )
    GeminiGenerator._validate_skill_cves(
        graph(*m.cve_ids), ScenarioSkillContexts(attack_graph=context), m
    )
    with pytest.raises(ValueError, match="requested CVEs"):
        GeminiGenerator._validate_skill_cves(
            graph("CVE-2025-1111"), ScenarioSkillContexts(attack_graph=context), m
        )


def test_generation_policy_applies_with_and_without_reference():
    for body in ("", "referenceが存在しないCVEを使わない。"):
        prompt = attack_graph_prompt(machine(), [], 2024, body)
        assert "許可リストではありません" in prompt
        assert "公式情報による検証" in prompt
        assert "許可リストではありません" in code_prompt(machine(), scenario(), body)


@pytest.mark.asyncio
async def test_unlisted_cve_still_uses_official_verification(monkeypatch):
    m = machine().model_copy(update={"needs_user_flag": False, "user_flag_details": ""})
    step = graph("CVE-2025-9999").steps[0]
    calls = []

    async def record(cve_id):
        calls.append(("record", cve_id))
        return {"containers": {"cna": {"descriptions": [{"value": "Test application"}]}}}

    async def osv(cve_id, os):
        calls.append(("osv", cve_id))

    async def refs(cve_id):
        calls.append(("references", cve_id))
        return []

    async def verify(prompt, **kwargs):
        return json.dumps(
            {
                "software": "test-app",
                "vulnerable_version": "1.0",
                "os_compatible": False,
                "compatibility_reason": "Incompatible with target OS",
                "installation_method": "none",
                "implementation_steps": ["unsupported"],
                "references": [],
            }
        )

    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test"), client)
        monkeypatch.setattr(generator, "_cve_record", record)
        monkeypatch.setattr(generator, "_debian_evidence", osv)
        monkeypatch.setattr(generator, "_github_references", refs)
        monkeypatch.setattr(generator, "_generate", verify)
        with pytest.raises(ValueError, match="not compatible"):
            await generator._verify_attack_graph(m, graph(step.cve_id))
        with pytest.raises(ValueError):
            await generator._verify_attack_graph(m, graph("CVE-2021-9999"))
    assert sorted(kind for kind, _ in calls) == ["osv", "record", "references"]


@pytest.mark.asyncio
async def test_api_can_complete_without_skill_and_reports_unlisted_cve():
    service = SkillService(
        FakeSkillRepository([]),
        max_active=32,
        max_per_phase=8,
        max_context_chars=50000,
        planner=SemanticSkillPlanner(Generator(decision()), model="test"),
    )
    captured = []

    class RecordingGenerator(StubGenerator):
        async def generate_scenario(self, machine, skills=None):
            captured.append(skills)
            return scenario().model_copy(update={"attack_graph": graph("CVE-2025-9999")})

    app = create_app(
        Settings(ai_provider="stub"),
        repository_override=FakeSessionRepository(),
        skill_service_override=service,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        app.state.scenarios.generator = RecordingGenerator()
        sid = (await client.post("/v1/sessions")).json()["session_id"]
        base = f"/v1/sessions/{sid}"
        assert (
            await client.put(base + "/machine-information", json=machine().model_dump())
        ).status_code == 200
        assert "scenario.completed" in (await client.get(base + "/scenarios/events")).text
        assert not captured[0].attack_graph.skills
        report = (await client.get(base + "/skills")).json()
        assert report["plan"]["skills"] == []
        assert report["cve_usage"] == {
            "used": ["CVE-2025-9999"],
            "with_skill_reference": [],
            "without_skill_reference": ["CVE-2025-9999"],
        }


@pytest.mark.asyncio
async def test_unused_automatic_skill_is_skipped_after_graph_selection():
    from test_skills import stored_skill

    from ai_server.skills.models import SkillSelectors

    item = stored_skill(selectors=SkillSelectors(attack_step_kinds=["custom"]))
    plan = await SemanticSkillPlanner(Generator(decision(item.name)), model="test").plan(
        machine(), [item]
    )
    context = context_from_plan(
        plan, SkillPhase.SOURCE, machine(), scenario(), max_per_phase=8, max_context_chars=50000
    )
    assert context.skills == []
