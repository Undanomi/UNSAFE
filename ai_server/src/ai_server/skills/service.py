from __future__ import annotations

import logging
from typing import Protocol

from ..models import MachineInformation, ScenarioDraft
from .models import SkillContext, SkillPhase, StoredSkill
from .planning import SemanticSkillPlanner, context_for_graph, context_from_plan, input_checksum
from .renderer import SkillRenderer
from .repository import SkillRepository
from .selector import SkillSelector

logger = logging.getLogger(__name__)


class SkillResolver(Protocol):
    async def resolve(
        self,
        session_id: str,
        phase: SkillPhase,
        machine: MachineInformation,
        scenario: ScenarioDraft | None = None,
    ) -> SkillContext: ...

    async def snapshot_manifest(self, session_id: str) -> dict[str, list[dict]]: ...

    async def reset(self, session_id: str) -> None: ...

    async def finalize_scenario(self, session_id: str, scenario: ScenarioDraft) -> None: ...

    async def selection_report(self, session_id: str) -> dict: ...


class NoopSkillService:
    async def finalize_scenario(self, session_id: str, scenario: ScenarioDraft) -> None:
        return None

    async def selection_report(self, session_id: str) -> dict:
        return {"enabled": False, "plan": None, "phases": {}}

    async def resolve(
        self,
        session_id: str,
        phase: SkillPhase,
        machine: MachineInformation,
        scenario: ScenarioDraft | None = None,
    ) -> SkillContext:
        if machine.skill_names:
            raise ValueError("Skills are disabled; explicitly requested Skills cannot be applied")
        return SkillContext(phase=phase)

    async def snapshot_manifest(self, session_id: str) -> dict[str, list[dict]]:
        return {}

    async def reset(self, session_id: str) -> None:
        return None


class SkillService:
    def __init__(
        self,
        repository: SkillRepository,
        *,
        max_active: int,
        max_per_phase: int,
        max_context_chars: int,
        selector: SkillSelector | None = None,
        renderer: SkillRenderer | None = None,
        planner: SemanticSkillPlanner | None = None,
    ) -> None:
        self.repository = repository
        self.max_active = max_active
        self.max_per_phase = max_per_phase
        self.max_context_chars = max_context_chars
        self.selector = selector or SkillSelector()
        self.renderer = renderer or SkillRenderer()
        self.planner = planner

    async def resolve(
        self,
        session_id: str,
        phase: SkillPhase,
        machine: MachineInformation,
        scenario: ScenarioDraft | None = None,
    ) -> SkillContext:
        existing = await self.repository.get_snapshot(session_id, phase)
        if existing is not None:
            if self.planner is not None:
                plan = await self.repository.get_plan(session_id)
                if plan is not None and plan.input_checksum != input_checksum(machine):
                    raise ValueError(
                        "Machine input changed; reset the selection plan before generating"
                    )
                return existing
            return existing
        if self.planner is not None:
            plan = await self.repository.get_plan(session_id)
            if plan is None:
                candidates = (
                    []
                    if machine.skill_names == []
                    else await self.repository.active_versions(self.max_active)
                )
                plan = await self.planner.plan(machine, candidates)
                # Validate all currently evaluable phases before persisting a plan.
                for initial_phase in (SkillPhase.ATTACK_GRAPH, SkillPhase.SCENARIO):
                    context_from_plan(
                        plan,
                        initial_phase,
                        machine,
                        max_per_phase=self.max_per_phase,
                        max_context_chars=self.max_context_chars,
                    )
                plan = await self.repository.create_plan(session_id, plan)
            preview = context_from_plan(
                plan,
                phase,
                machine,
                scenario,
                max_per_phase=self.max_per_phase,
                max_context_chars=self.max_context_chars,
            )
            snapshot = await self.repository.create_snapshot(session_id, phase, preview.skills)
            return snapshot
        candidates = await self.repository.active_versions(self.max_active)
        # Keep the same definitions for later phases, even if a new version was published.
        pinned = {}
        for previous_phase in (SkillPhase.ATTACK_GRAPH, SkillPhase.SCENARIO):
            if previous_phase == phase:
                break
            previous = await self.repository.get_snapshot(session_id, previous_phase)
            if previous is not None:
                for skill in previous.skills:
                    pinned.setdefault(skill.name, StoredSkill.model_validate(skill.model_dump()))
        candidates = [item for item in candidates if item.name not in pinned] + list(
            pinned.values()
        )
        preview = select_context(
            candidates,
            phase,
            machine,
            scenario,
            max_per_phase=self.max_per_phase,
            max_context_chars=self.max_context_chars,
            selector=self.selector,
            renderer=self.renderer,
        )
        context = await self.repository.create_snapshot(session_id, phase, preview.skills)
        logger.info(
            "skills resolved",
            extra={
                "session_id": session_id,
                "phase": phase.value,
                "skills": [f"{skill.name}@{skill.version}" for skill in context.skills],
            },
        )
        return context

    async def snapshot_manifest(self, session_id: str) -> dict[str, list[dict]]:
        return await self.repository.snapshot_manifest(session_id)

    async def reset(self, session_id: str) -> None:
        await self.repository.clear_snapshots(session_id)

    async def finalize_scenario(self, session_id: str, scenario: ScenarioDraft) -> None:
        snapshot = await self.repository.get_snapshot(session_id, SkillPhase.SCENARIO)
        if snapshot is not None:
            await self.repository.finalize_references(
                session_id, context_for_graph(snapshot, scenario.attack_graph)
            )

    async def selection_report(self, session_id: str) -> dict:
        plan = await self.repository.get_plan(session_id)
        return {
            "enabled": True,
            "selection_policy": "advisory",
            "plan": None
            if plan is None
            else {
                "mode": plan.mode,
                "model": plan.model,
                "reason": plan.reason,
                "skills": [
                    {
                        "name": item.name,
                        "version": item.version,
                        "checksum": item.content_checksum,
                        "reason": item.selection_reason,
                        "reference_mode": item.reference_mode,
                        "reference_ids": item.selected_reference_ids,
                        "reference_reasons": item.reference_reasons,
                    }
                    for item in plan.skills
                ],
            },
            "phases": await self.repository.snapshot_manifest(session_id),
        }


def select_context(
    candidates: list[StoredSkill],
    phase: SkillPhase,
    machine: MachineInformation,
    scenario: ScenarioDraft | None = None,
    *,
    max_per_phase: int = 8,
    max_context_chars: int = 50_000,
    selector: SkillSelector | None = None,
    renderer: SkillRenderer | None = None,
) -> SkillContext:
    """Resolve rule-based selection without silently omitting matching Skills."""
    selected = (selector or SkillSelector()).select(candidates, phase, machine, scenario)
    if len(selected) > max_per_phase:
        raise ValueError(
            f"Selected Skills exceed SKILLS_MAX_PER_PHASE={max_per_phase}; narrow the selection"
        )
    context = SkillContext(phase=phase, skills=selected)
    size = len((renderer or SkillRenderer()).render(context))
    if size > max_context_chars:
        raise ValueError(
            f"Selected Skill context ({size} characters) exceeds SKILL_CONTEXT_MAX_CHARS={max_context_chars}"
        )
    return context
