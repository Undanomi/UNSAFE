from __future__ import annotations

import httpx
import pytest
from skill_helpers import as_candidates
from test_api_flow import FakeSessionRepository
from test_skill_loader import write_skill
from test_skills import FakeSkillRepository, machine, scenario

from ai_server.config import Settings
from ai_server.main import create_app
from ai_server.models import MachineInformation
from ai_server.services.ai import GeminiGenerator
from ai_server.services.stub_ai import StubGenerator
from ai_server.skills.loader import load_skills
from ai_server.skills.models import ScenarioSkillContexts, SkillPhase
from ai_server.skills.renderer import SkillRenderer
from ai_server.skills.service import NoopSkillService, SkillService, select_context


def candidates(root):
    for name in ["sql-injection", "ssti", "csrf", "cve"]:
        path = write_skill(root, name)
        if name == "cve":
            refs = path.parent / "references"
            refs.mkdir(exist_ok=True)
            (refs / "CVE-2025-1234.md").write_text("selected reference", encoding="utf-8")
    return as_candidates(load_skills(root, created_by="test"))


def test_automatic_selection_matches_names_not_all_minimal_skills(tmp_path):
    items = candidates(tmp_path)
    context = select_context(items, SkillPhase.SOURCE, machine())
    assert [s.name for s in context.skills] == ["sql-injection"]
    m = machine().model_copy(update={"theme": "SSTI"})
    assert [s.name for s in select_context(items, SkillPhase.SOURCE, m).skills] == ["ssti"]
    m.skill_names = []
    assert select_context(items, SkillPhase.SOURCE, m).skills == []


def test_explicit_missing_skill_and_budgets_fail(tmp_path):
    items = candidates(tmp_path)
    m = machine().model_copy(update={"skill_names": ["missing"]})
    with pytest.raises(ValueError, match="missing or inactive"):
        select_context(items, SkillPhase.SOURCE, m)
    m.skill_names = ["ssti", "csrf"]
    with pytest.raises(ValueError, match="MAX_PER_PHASE"):
        select_context(items, SkillPhase.SOURCE, m, max_per_phase=1)
    with pytest.raises(ValueError, match="MAX_CHARS"):
        select_context(items, SkillPhase.SOURCE, m, max_context_chars=10)


def test_cve_uses_available_references_without_requiring_coverage(tmp_path):
    items = candidates(tmp_path)
    m = machine().model_copy(update={"skill_names": ["cve"]})
    assert select_context(items, SkillPhase.ATTACK_GRAPH, m).skills[0].selected_reference_ids == []
    m.cve_ids = ["CVE-2025-9999"]
    assert select_context(items, SkillPhase.ATTACK_GRAPH, m).skills[0].selected_reference_ids == []
    m.cve_ids = ["CVE-2025-1234"]
    context = select_context(items, SkillPhase.ATTACK_GRAPH, m)
    assert context.skills[0].selected_reference_ids == m.cve_ids
    with pytest.raises(ValueError, match="must use"):
        GeminiGenerator._validate_skill_cves(
            scenario().attack_graph, ScenarioSkillContexts(attack_graph=context), m
        )


@pytest.mark.asyncio
async def test_later_phase_keeps_published_reference_version(tmp_path):
    items = candidates(tmp_path)
    repository = FakeSkillRepository(items)
    service = SkillService(repository, max_active=32, max_per_phase=8, max_context_chars=50000)
    m = machine().model_copy(update={"skill_names": ["cve"], "cve_ids": ["CVE-2025-1234"]})
    first = await service.resolve("test", SkillPhase.ATTACK_GRAPH, m)
    # Republishing and even disabling must not change definitions already used in this session.
    repository.candidates = []
    later = await service.resolve("test", SkillPhase.SCENARIO, m)
    assert later.skills == first.skills
    assert "selected reference" in SkillRenderer.render(later)


@pytest.mark.asyncio
async def test_disabled_skills_reject_explicit_requests():
    m = machine().model_copy(update={"skill_names": ["ssti"]})
    with pytest.raises(ValueError, match="disabled"):
        await NoopSkillService().resolve("test", SkillPhase.SOURCE, m)


@pytest.mark.parametrize(
    "changes",
    [
        {"operating_system": "Ubuntu 26.04"},
        {"skill_names": ["ssti", "ssti"]},
        {"cve_ids": ["invalid"]},
    ],
)
def test_invalid_generation_choices_are_rejected(changes):
    data = machine().model_dump() | changes
    with pytest.raises(ValueError):
        MachineInformation.model_validate(data)


@pytest.mark.asyncio
async def test_api_passes_explicit_skill_to_scenario_generator(tmp_path):
    repository = FakeSkillRepository(candidates(tmp_path))
    service = SkillService(repository, max_active=32, max_per_phase=8, max_context_chars=50000)
    captured = []

    class RecordingGenerator(StubGenerator):
        async def generate_scenario(self, machine, skills=None):
            captured.append(skills)
            return await super().generate_scenario(machine, skills)

    app = create_app(
        Settings(ai_provider="stub"),
        repository_override=FakeSessionRepository(),
        skill_service_override=service,
    )
    async with app.router.lifespan_context(app):
        app.state.scenarios.generator = RecordingGenerator()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            headers = {"X-Authenticated-User-ID": "test"}
            session_id = (await client.post("/v1/sessions", headers=headers)).json()["session_id"]
            body = machine().model_dump() | {"skill_names": ["ssti"]}
            saved = await client.put(
                f"/v1/sessions/{session_id}/machine-information", json=body, headers=headers
            )
            assert saved.status_code == 200
            assert saved.json()["machine_information"]["skill_names"] == ["ssti"]
            events = await client.get(
                f"/v1/sessions/{session_id}/scenarios/events", headers=headers
            )
            assert "scenario.completed" in events.text
            assert [s.name for s in captured[0].attack_graph.skills] == ["ssti"]
            assert [s.name for s in captured[0].scenario.skills] == ["ssti"]


@pytest.mark.asyncio
async def test_gemini_gets_only_selected_cve_reference(tmp_path, monkeypatch):
    from ai_server.models import AttackGraph, AttackStep, ScenarioReview

    items = candidates(tmp_path)
    m = machine().model_copy(update={"skill_names": ["cve"], "cve_ids": ["CVE-2025-1234"]})
    contexts = ScenarioSkillContexts(
        attack_graph=select_context(items, SkillPhase.ATTACK_GRAPH, m),
        scenario=select_context(items, SkillPhase.SCENARIO, m),
    )
    graph = AttackGraph(
        steps=[
            AttackStep(
                step_id="test",
                title="test",
                kind="cve",
                phase="initial_access",
                description="test",
                implementation_steps=["test"],
                cve_id="CVE-2025-1234",
            )
        ]
    )
    prompts = []

    async def draft(machine, rejected, context):
        prompts.append(context)
        return graph

    async def verify(machine, graph):
        return graph

    async def generate(prompt, **kwargs):
        if kwargs.get("response_schema") is ScenarioReview:
            return ScenarioReview(approved=True, summary="Approved", findings=[]).model_dump_json()
        prompts.append(prompt)
        return "# Scenario"

    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test"), client)
        monkeypatch.setattr(generator, "_draft_attack_graph", draft)
        monkeypatch.setattr(generator, "_verify_attack_graph", verify)
        monkeypatch.setattr(generator, "_generate", generate)
        result = await generator.generate_scenario(m, contexts)
    assert result.target_os == "Debian 13.7.0"
    assert len(prompts) == 2
    assert all("selected reference" in prompt for prompt in prompts)
