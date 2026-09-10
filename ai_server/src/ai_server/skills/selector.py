from __future__ import annotations

from ..models import MachineInformation, ScenarioDraft
from .models import AppliedSkill, SkillPhase, StoredSkill


class SkillSelector:
    def select(
        self,
        candidates: list[StoredSkill],
        phase: SkillPhase,
        machine: MachineInformation,
        scenario: ScenarioDraft | None = None,
    ) -> list[AppliedSkill]:
        selected: list[AppliedSkill] = []
        for candidate in candidates:
            reason = self._match(candidate, phase, machine, scenario)
            if reason is not None:
                selected.append(AppliedSkill(**candidate.model_dump(), selection_reason=reason))
        return sorted(selected, key=lambda item: (item.priority, item.name, item.version))

    @staticmethod
    def _match(
        candidate: StoredSkill,
        phase: SkillPhase,
        machine: MachineInformation,
        scenario: ScenarioDraft | None,
    ) -> str | None:
        if phase not in candidate.phases:
            return None

        selectors = candidate.selectors
        reasons: list[str] = []
        theme = machine.theme.casefold()
        operating_system = machine.operating_system.casefold()

        if selectors.themes:
            matched = next((term for term in selectors.themes if term in theme), None)
            if matched is None:
                return None
            reasons.append(f"theme:{matched}")
        if selectors.operating_systems:
            matched = next(
                (term for term in selectors.operating_systems if term in operating_system), None
            )
            if matched is None:
                return None
            reasons.append(f"operating_system:{matched}")
        if (
            selectors.requires_user_flag is not None
            and bool(machine.needs_user_flag) != selectors.requires_user_flag
        ):
            return None
        if selectors.requires_user_flag is not None:
            reasons.append(f"requires_user_flag:{selectors.requires_user_flag}")
        if (
            selectors.requires_system_flag is not None
            and bool(machine.needs_system_flag) != selectors.requires_system_flag
        ):
            return None
        if selectors.requires_system_flag is not None:
            reasons.append(f"requires_system_flag:{selectors.requires_system_flag}")

        if selectors.attack_step_kinds or selectors.attack_phases:
            if scenario is None:
                return None
            step_kinds = {step.kind.casefold() for step in scenario.attack_graph.steps}
            step_phases = {step.phase.casefold() for step in scenario.attack_graph.steps}
            if selectors.attack_step_kinds:
                matched = next(
                    (term for term in selectors.attack_step_kinds if term in step_kinds), None
                )
                if matched is None:
                    return None
                reasons.append(f"attack_step_kind:{matched}")
            if selectors.attack_phases:
                matched = next(
                    (term for term in selectors.attack_phases if term in step_phases), None
                )
                if matched is None:
                    return None
                reasons.append(f"attack_phase:{matched}")

        return ",".join(reasons) or "phase"
