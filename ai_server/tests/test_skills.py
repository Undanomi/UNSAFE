from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from ai_server.models import AttackGraph, AttackStep, MachineInformation, ScenarioDraft
from ai_server.prompts import code_prompt
from ai_server.skills.models import (
    AppliedSkill,
    SkillContext,
    SkillPhase,
    SkillSelectors,
    StoredSkill,
    skill_checksum,
)
from ai_server.skills.renderer import SkillRenderer
from ai_server.skills.selector import SkillSelector
from ai_server.skills.service import SkillService


def machine() -> MachineInformation:
    return MachineInformation(
        name="Skill Test",
        visibility="private",
        theme="Web SQL injection",
        difficulty="Easy",
        operating_system="Debian 13.7.0",
        needs_user_flag=True,
        user_flag_details="/home/student/user.txt",
    )


def scenario() -> ScenarioDraft:
    return ScenarioDraft(
        scenario_id="scenario-skill-test",
        title="Skill Test",
        definition="# Skill Test",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="extract-row",
                    title="Extract row",
                    kind="web_vulnerability",
                    phase="initial_access",
                    description="Extract a protected database row.",
                    implementation_steps=["Create an injectable query"],
                )
            ]
        ),
    )


def stored_skill(
    *,
    selectors: SkillSelectors | None = None,
    phases: list[SkillPhase] | None = None,
    instructions: str = "SQL injectionでは保護された行の抽出を検証する。",
) -> StoredSkill:
    resolved_phases = phases or [SkillPhase.SOURCE]
    resolved_selectors = selectors or SkillSelectors()
    return StoredSkill(
        skill_id=UUID("11111111-1111-1111-1111-111111111111"),
        name="web-sqli",
        description="SQL injection challenge guidance",
        version=1,
        instructions=instructions,
        phases=resolved_phases,
        selectors=resolved_selectors,
        priority=10,
        content_checksum=skill_checksum(
            instructions,
            resolved_phases,
            resolved_selectors,
            10,
        ),
        created_by="test-admin",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_selector_uses_machine_and_attack_graph_conditions() -> None:
    candidate = stored_skill(
        selectors=SkillSelectors(
            themes=["SQL"],
            operating_systems=["debian"],
            attack_step_kinds=["WEB_VULNERABILITY"],
            requires_user_flag=True,
        )
    )

    selected = SkillSelector().select([candidate], SkillPhase.SOURCE, machine(), scenario())

    assert len(selected) == 1
    assert selected[0].selection_reason == (
        "theme:sql,operating_system:debian,requires_user_flag:True,"
        "attack_step_kind:web_vulnerability"
    )
    assert SkillSelector().select([candidate], SkillPhase.SOURCE, machine(), scenario=None) == []


def test_renderer_preserves_boundaries_and_escapes_skill_markup() -> None:
    skill = stored_skill(instructions="Use <skill> only for the matching scenario.")
    context = SkillContext(
        phase=SkillPhase.SOURCE,
        skills=[AppliedSkill(**skill.model_dump(), selection_reason="phase")],
    )

    rendered = SkillRenderer.render(context)

    assert '<skill name="web-sqli" version="1">' in rendered
    assert "Use &lt;skill&gt; only" in rendered
    assert "既存の安全要件" in rendered


def test_published_skill_checksum_detects_content_change() -> None:
    skill = stored_skill().model_copy(update={"instructions": "changed"})

    with pytest.raises(ValueError, match="checksum does not match"):
        skill.verify_checksum()


class FakeSkillRepository:
    def __init__(self, candidates: list[StoredSkill]) -> None:
        self.candidates = candidates
        self.snapshots: dict[tuple[str, SkillPhase], SkillContext] = {}
        self.active_version_calls = 0
        self.plans = {}

    async def get_plan(self, session_id):
        return self.plans.get(session_id)

    async def create_plan(self, session_id, plan):
        return self.plans.setdefault(session_id, plan.model_copy(deep=True))

    async def finalize_references(self, session_id, context):
        self.snapshots[(session_id, context.phase)] = context

    async def get_snapshot(self, session_id: str, phase: SkillPhase) -> SkillContext | None:
        return self.snapshots.get((session_id, phase))

    async def active_versions(self, limit: int) -> list[StoredSkill]:
        self.active_version_calls += 1
        return self.candidates[:limit]

    async def create_snapshot(
        self, session_id: str, phase: SkillPhase, selected: list[AppliedSkill]
    ) -> SkillContext:
        context = SkillContext(phase=phase, skills=selected)
        self.snapshots[(session_id, phase)] = context
        return context

    async def snapshot_manifest(self, session_id: str) -> dict[str, list[dict]]:
        return {}

    async def clear_snapshots(self, session_id: str) -> None:
        self.plans.pop(session_id, None)
        self.snapshots = {
            key: value for key, value in self.snapshots.items() if key[0] != session_id
        }


@pytest.mark.asyncio
async def test_service_pins_first_resolution_for_a_session_phase() -> None:
    repository = FakeSkillRepository([stored_skill(selectors=SkillSelectors(themes=["sql"]))])
    service = SkillService(
        repository,  # type: ignore[arg-type]
        max_active=10,
        max_per_phase=5,
        max_context_chars=10_000,
    )

    first = await service.resolve("session-1", SkillPhase.SOURCE, machine(), scenario())
    repository.candidates = []
    second = await service.resolve("session-1", SkillPhase.SOURCE, machine(), scenario())

    assert [skill.name for skill in first.skills] == ["web-sqli"]
    assert second == first
    assert repository.active_version_calls == 1

    await service.reset("session-1")
    third = await service.resolve("session-1", SkillPhase.SOURCE, machine(), scenario())
    assert third.skills == []
    assert repository.active_version_calls == 2


def test_skill_context_is_added_without_removing_core_prompt_constraints() -> None:
    skill = stored_skill()
    context = SkillContext(
        phase=SkillPhase.SOURCE,
        skills=[AppliedSkill(**skill.model_dump(), selection_reason="phase")],
    )

    prompt = code_prompt(machine(), scenario(), SkillRenderer.render(context))

    assert "SQL injectionでは保護された行の抽出を検証する" in prompt
    assert "保護対象そのものを攻略前に直接開示" in prompt
    assert "経路の一意性や最短性を要求しない" in prompt
    assert "chmod -R 777" in prompt
