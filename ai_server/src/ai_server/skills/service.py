from __future__ import annotations

import logging
from typing import Protocol

from ..models import MachineInformation, ScenarioDraft
from .models import SkillContext, SkillPhase
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


class NoopSkillService:
    async def resolve(
        self,
        session_id: str,
        phase: SkillPhase,
        machine: MachineInformation,
        scenario: ScenarioDraft | None = None,
    ) -> SkillContext:
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
    ) -> None:
        self.repository = repository
        self.max_active = max_active
        self.max_per_phase = max_per_phase
        self.max_context_chars = max_context_chars
        self.selector = selector or SkillSelector()
        self.renderer = renderer or SkillRenderer()

    async def resolve(
        self,
        session_id: str,
        phase: SkillPhase,
        machine: MachineInformation,
        scenario: ScenarioDraft | None = None,
    ) -> SkillContext:
        existing = await self.repository.get_snapshot(session_id, phase)
        if existing is not None:
            return existing
        candidates = await self.repository.active_versions(self.max_active)
        matching = self.selector.select(candidates, phase, machine, scenario)
        selected = []
        for skill in matching:
            if len(selected) >= self.max_per_phase:
                break
            candidate = SkillContext(phase=phase, skills=[*selected, skill])
            if len(self.renderer.render(candidate)) > self.max_context_chars:
                logger.warning(
                    "skill skipped because phase context limit would be exceeded",
                    extra={"phase": phase.value, "skill": skill.name},
                )
                continue
            selected.append(skill)
        context = await self.repository.create_snapshot(session_id, phase, selected)
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
