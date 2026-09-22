from __future__ import annotations

import json

import pytest
from skill_helpers import as_candidates
from test_skill_loader import write_skill
from test_skills import FakeSkillRepository, machine

from ai_server.models import AttackGraph, AttackStep
from ai_server.skills.loader import load_skills
from ai_server.skills.models import SkillPhase
from ai_server.skills.planning import (
    NoMatchingSkillError,
    SemanticSkillPlanner,
    SkillSelectionError,
    context_for_graph,
    context_from_plan,
    reference_is_eligible,
)
from ai_server.skills.renderer import SkillRenderer
from ai_server.skills.service import SkillService


def catalog(tmp_path):
    write_skill(tmp_path, "sql-injection")
    write_skill(tmp_path, "ssti")
    path = write_skill(tmp_path, "cve")
    refs = path.parent / "references"
    refs.mkdir()
    for year, number, os in [
        (2025, 1111, "Debian"),
        (2025, 2222, "Debian"),
        (2021, 3333, "Debian 11"),
    ]:
        (refs / f"CVE-{year}-{number}.md").write_text(
            f"# Test CVE\n## Metadata\nProduct: test\n## Preconditions\nLocal shell\n## Environment\n- Target OS: {os}\n## Construction\nBODY-{number}",
            encoding="utf-8",
        )
    return as_candidates(load_skills(tmp_path, created_by="test"))


def decision(*names, supported=True):
    return json.dumps(
        {
            "input_supported": supported,
            "selected": [
                {"name": name, "reason": "Matches the requested learning objective"}
                for name in names
            ],
            "reason": "Evaluation selection",
        }
    )


class Generator:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    async def __call__(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.responses.pop(0)


def graph(*ids):
    return AttackGraph(
        steps=[
            AttackStep(
                step_id=f"step-{i}",
                title="test",
                kind="cve",
                phase="initial_access",
                description="test",
                implementation_steps=["test"],
                cve_id=id,
            )
            for i, id in enumerate(ids)
        ]
    )


@pytest.mark.asyncio
async def test_semantic_selection_uses_metadata_then_selected_reference_summaries(tmp_path):
    items = catalog(tmp_path)
    generate = Generator(decision("cve"), decision("CVE-2025-1111", "CVE-2025-2222"))
    planner = SemanticSkillPlanner(generate, model="test")
    m = machine().model_copy(update={"theme": "サービス侵入から設定を取得したい"})
    plan = await planner.plan(m, items)
    assert len(generate.prompts) == 2
    assert "BODY-" not in "\n".join(generate.prompts)
    assert "CVE-2021-3333" not in generate.prompts[1]
    assert plan.skills[0].reference_mode == "candidates"
    context = context_from_plan(
        plan, SkillPhase.ATTACK_GRAPH, m, max_per_phase=8, max_context_chars=50000
    )
    assert "BODY-1111" in SkillRenderer.render(context)
    assert "BODY-2222" in SkillRenderer.render(context)
    used = context_for_graph(context, graph("CVE-2025-1111"))
    assert "BODY-1111" in SkillRenderer.render(used)
    assert "BODY-2222" not in SkillRenderer.render(used)
    assert used.skills[0].reference_mode == "used"
    unlisted = context_for_graph(context, graph("CVE-2025-9999"))
    assert unlisted.skills[0].selected_reference_ids == []


@pytest.mark.asyncio
async def test_explicit_ids_remain_required_and_skip_model(tmp_path):
    items = catalog(tmp_path)
    generate = Generator()
    planner = SemanticSkillPlanner(generate, model="test")
    m = machine().model_copy(
        update={"skill_names": ["cve"], "cve_ids": ["CVE-2025-1111", "CVE-2025-2222"]}
    )
    plan = await planner.plan(m, items)
    assert generate.prompts == []
    assert plan.mode == "explicit"
    context = context_from_plan(
        plan, SkillPhase.ATTACK_GRAPH, m, max_per_phase=8, max_context_chars=50000
    )
    with pytest.raises(SkillSelectionError):
        context_for_graph(context, graph("CVE-2025-1111"))
    assert (
        context_for_graph(context, graph(*m.cve_ids)).skills[0].selected_reference_ids == m.cve_ids
    )
    empty = await planner.plan(machine().model_copy(update={"skill_names": []}), [])
    assert empty.skills == []


@pytest.mark.asyncio
async def test_explicit_cve_without_ids_selects_reference_automatically(tmp_path):
    generate = Generator(decision("CVE-2025-1111"))
    plan = await SemanticSkillPlanner(generate, model="test").plan(
        machine().model_copy(update={"skill_names": ["cve"]}), catalog(tmp_path)
    )
    assert len(generate.prompts) == 1
    assert plan.skills[0].reference_mode == "candidates"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["not json", decision("nonexistent"), decision("ssti", "ssti")])
async def test_invalid_choices_retry_with_catalog_validation(tmp_path, bad):
    generate = Generator(bad, decision("ssti"))
    plan = await SemanticSkillPlanner(generate, model="test").plan(machine(), catalog(tmp_path))
    assert [s.name for s in plan.skills] == ["ssti"]
    assert "前回の選択エラー" in generate.prompts[1]


@pytest.mark.asyncio
async def test_no_match_and_exhausted_retries_are_explicit_errors(tmp_path):
    items = catalog(tmp_path)
    with pytest.raises(NoMatchingSkillError, match="Evaluation selection"):
        await SemanticSkillPlanner(Generator(decision(supported=False)), model="test").plan(
            machine(), items
        )
    with pytest.raises(SkillSelectionError, match="Could not validate"):
        await SemanticSkillPlanner(Generator(decision("x"), decision("x")), model="test").plan(
            machine(), items
        )
    with pytest.raises(NoMatchingSkillError):
        await SemanticSkillPlanner(Generator(decision(supported=False)), model="test").plan(
            machine(), []
        )


@pytest.mark.asyncio
async def test_limits_do_not_silently_drop_choices(tmp_path):
    items = catalog(tmp_path)
    with pytest.raises(SkillSelectionError, match="catalog exceeds"):
        await SemanticSkillPlanner(Generator(), model="test", max_catalog_chars=10).plan(
            machine(), items
        )
    plan = await SemanticSkillPlanner(
        Generator(decision("ssti", "sql-injection")), model="test"
    ).plan(machine(), items)
    with pytest.raises(SkillSelectionError, match="MAX_PER_PHASE"):
        context_from_plan(
            plan, SkillPhase.SOURCE, machine(), max_per_phase=1, max_context_chars=50000
        )
    with pytest.raises(SkillSelectionError, match="MAX_CHARS"):
        context_from_plan(plan, SkillPhase.SOURCE, machine(), max_per_phase=8, max_context_chars=1)


def test_reference_eligibility_uses_structured_id_and_year_only(tmp_path):
    refs = next(s for s in catalog(tmp_path) if s.name == "cve").references
    old = next(r for r in refs if "2021" in r.reference_id)
    assert reference_is_eligible(old, machine(), 2020)
    assert not reference_is_eligible(
        old, machine().model_copy(update={"operating_system": "Debian 11"}), 2024
    )


@pytest.mark.asyncio
async def test_plan_is_reused_for_all_phases_and_reset(tmp_path):
    items = catalog(tmp_path)
    generate = Generator(decision("ssti"), decision("sql-injection"))
    repository = FakeSkillRepository(items)
    service = SkillService(
        repository,
        max_active=32,
        max_per_phase=8,
        max_context_chars=50000,
        planner=SemanticSkillPlanner(generate, model="test"),
    )
    first = await service.resolve("session", SkillPhase.ATTACK_GRAPH, machine())
    repository.candidates = []
    for phase in (SkillPhase.SCENARIO, SkillPhase.SOURCE, SkillPhase.REPAIR, SkillPhase.REVIEW):
        assert (await service.resolve("session", phase, machine())).skills == first.skills
    assert len(generate.prompts) == 1
    await service.reset("session")
    repository.candidates = items
    assert (await service.resolve("session", SkillPhase.ATTACK_GRAPH, machine())).skills[
        0
    ].name == "sql-injection"
    assert len(generate.prompts) == 2


@pytest.mark.asyncio
async def test_changed_input_and_cve_phase_mismatch_fail(tmp_path):
    from ai_server.skills.models import skill_checksum

    items = catalog(tmp_path)
    m = machine().model_copy(update={"skill_names": ["ssti"]})
    plan = await SemanticSkillPlanner(Generator(), model="test").plan(m, items)
    with pytest.raises(SkillSelectionError, match="input changed"):
        context_from_plan(
            plan, SkillPhase.SOURCE, machine(), max_per_phase=8, max_context_chars=50000
        )
    cve = next(item for item in items if item.name == "cve")
    cve.phases = [SkillPhase.SOURCE]
    cve.content_checksum = skill_checksum(
        cve.instructions, cve.phases, cve.selectors, cve.priority, cve.references
    )
    with pytest.raises(SkillSelectionError, match="incompatible"):
        await SemanticSkillPlanner(Generator(), model="test").plan(
            machine().model_copy(update={"skill_names": ["cve"]}), items
        )


@pytest.mark.asyncio
async def test_source_only_semantic_skill_allows_unselected_cves(tmp_path):
    from ai_server.services.ai import GeminiGenerator
    from ai_server.skills.models import ScenarioSkillContexts, skill_checksum

    items = catalog(tmp_path)
    skill = next(item for item in items if item.name == "ssti")
    skill.phases = [SkillPhase.SOURCE]
    skill.content_checksum = skill_checksum(
        skill.instructions, skill.phases, skill.selectors, skill.priority, skill.references
    )
    service = SkillService(
        FakeSkillRepository(items),
        max_active=32,
        max_per_phase=8,
        max_context_chars=50000,
        planner=SemanticSkillPlanner(Generator(decision("ssti")), model="test"),
    )
    for _ in range(2):  # Both fresh and persisted phase resolution.
        context = await service.resolve("test", SkillPhase.ATTACK_GRAPH, machine())
        assert not context.skills
        GeminiGenerator._validate_skill_cves(
            graph("CVE-2025-1111"), ScenarioSkillContexts(attack_graph=context), machine()
        )


@pytest.mark.asyncio
async def test_api_automatic_selection_report_reset_and_failure(tmp_path):
    import httpx
    from test_api_flow import FakeSessionRepository

    from ai_server.config import Settings
    from ai_server.main import create_app
    from ai_server.models import SessionStatus

    generate = Generator(decision("ssti"), decision(supported=False))
    repository = FakeSkillRepository(catalog(tmp_path))
    service = SkillService(
        repository,
        max_active=32,
        max_per_phase=8,
        max_context_chars=50000,
        planner=SemanticSkillPlanner(generate, model="test"),
    )
    app = create_app(
        Settings(ai_provider="stub"),
        repository_override=FakeSessionRepository(),
        skill_service_override=service,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        headers = {"X-Authenticated-User-ID": "owner"}
        sid = (await client.post("/v1/sessions", headers=headers)).json()["session_id"]
        base = f"/v1/sessions/{sid}"
        assert (
            await client.put(
                base + "/machine-information", headers=headers, json=machine().model_dump()
            )
        ).status_code == 200
        events = await client.get(base + "/scenarios/events", headers=headers)
        assert "scenario.completed" in events.text
        report = (await client.get(base + "/skills", headers=headers)).json()
        assert report["plan"]["mode"] == "semantic"
        assert report["plan"]["skills"][0]["name"] == "ssti"
        assert "instructions" not in json.dumps(report)
        assert (
            await client.get(base + "/skills", headers={"X-Authenticated-User-ID": "other"})
        ).status_code == 404
        assert (await client.get(base + "/skills")).status_code == 404
        # Generating stages must not discard a selection plan halfway through.
        state = await app.state.repository.get(sid)
        state.status = SessionStatus.GENERATING_CODE
        await app.state.repository.save(state)
        assert (
            await client.put(
                base + "/machine-information", headers=headers, json=machine().model_dump()
            )
        ).status_code == 409
        state.status = SessionStatus.SCENARIO_READY
        await app.state.repository.save(state)
        assert (
            await client.put(
                base + "/machine-information", headers=headers, json=machine().model_dump()
            )
        ).status_code == 200
        assert (await client.get(base + "/skills", headers=headers)).json()["plan"] is None
        failed = await client.get(base + "/scenarios/events", headers=headers)
        assert "scenario.error" in failed.text
        assert "Unsupported learning input" in failed.text
        assert (await app.state.repository.get(sid)).status == SessionStatus.FAILED


@pytest.mark.asyncio
async def test_generated_graph_narrows_references_for_all_later_stages(tmp_path, monkeypatch):
    import httpx

    from ai_server.config import Settings
    from ai_server.models import ScenarioCorrection, ScenarioReview, ScenarioReviewFinding
    from ai_server.services.ai import GeminiGenerator
    from ai_server.skills.models import ScenarioSkillContexts

    generate = Generator(decision("cve"), decision("CVE-2025-1111", "CVE-2025-2222"))
    repository = FakeSkillRepository(catalog(tmp_path))
    service = SkillService(
        repository,
        max_active=32,
        max_per_phase=8,
        max_context_chars=50000,
        planner=SemanticSkillPlanner(generate, model="test"),
    )
    m = machine()
    contexts = ScenarioSkillContexts(
        attack_graph=await service.resolve("test", SkillPhase.ATTACK_GRAPH, m),
        scenario=await service.resolve("test", SkillPhase.SCENARIO, m),
    )
    used_graph = graph("CVE-2025-1111", "CVE-2025-9999")
    prompts = []

    async def draft(machine, rejected, context):
        assert "BODY-1111" in context and "BODY-2222" in context
        return used_graph

    async def verify(machine, graph):
        return graph

    review_calls = 0

    async def definition(prompt, **kwargs):
        nonlocal review_calls
        if kwargs.get("response_schema") is ScenarioReview:
            review_calls += 1
            if review_calls == 1:
                return ScenarioReview(
                    approved=False,
                    summary="Specify the file owner",
                    findings=[
                        ScenarioReviewFinding(
                            severity="error",
                            category="implementation_gap",
                            evidence="Missing owner",
                            remediation="Specify owner",
                        )
                    ],
                ).model_dump_json()
            return ScenarioReview(approved=True, summary="Approved", findings=[]).model_dump_json()
        prompts.append(prompt)
        if kwargs.get("response_schema") is ScenarioCorrection:
            return ScenarioCorrection(
                scenario_description=None,
                definition_replacements=[
                    {
                        "old": "Owner is unspecified.",
                        "new": "The file owner is www-data.",
                    }
                ],
            ).model_dump_json()
        return json.dumps(
            {
                "scenario_description": "Investigate the generated training machine.",
                "definition": "# Scenario\n\nOwner is unspecified.",
            }
        )

    async with httpx.AsyncClient() as client:
        generator = GeminiGenerator(Settings(gemini_api_key="test"), client)
        monkeypatch.setattr(generator, "_draft_attack_graph", draft)
        monkeypatch.setattr(generator, "_verify_attack_graph", verify)
        monkeypatch.setattr(generator, "_generate", definition)
        result = await generator.generate_scenario(m, contexts)
    assert review_calls == 2 and len(prompts) == 2
    assert all("BODY-1111" in prompt and "BODY-2222" not in prompt for prompt in prompts)
    assert "Specify the file owner" in prompts[1]
    await service.finalize_scenario("test", result)
    assert (await repository.get_snapshot("test", SkillPhase.SCENARIO)).skills[
        0
    ].selected_reference_ids == ["CVE-2025-1111"]
    for phase in (SkillPhase.SOURCE, SkillPhase.REPAIR, SkillPhase.REVIEW):
        context = await service.resolve("test", phase, m, result)
        assert context.skills[0].selected_reference_ids == ["CVE-2025-1111"]
        assert "BODY-2222" not in SkillRenderer.render(context)
    # General Skills are advisory and do not prohibit additional CVEs.
    general = context_from_plan(
        await SemanticSkillPlanner(Generator(decision("ssti")), model="test").plan(
            m, repository.candidates
        ),
        SkillPhase.ATTACK_GRAPH,
        m,
        max_per_phase=8,
        max_context_chars=50000,
    )
    GeminiGenerator._validate_skill_cves(used_graph, ScenarioSkillContexts(attack_graph=general), m)
