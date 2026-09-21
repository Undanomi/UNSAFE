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
        requested = machine.skill_names
        available = {item.name for item in candidates}
        required = set(requested or [])
        missing = required - available
        if missing:
            raise ValueError(
                f"Requested Skills are missing or inactive: {', '.join(sorted(missing))}"
            )
        for candidate in candidates:
            if requested is not None and candidate.name not in requested:
                continue
            if phase not in candidate.phases:
                continue
            reason = self._match(candidate, phase, machine, scenario)
            if reason is not None:
                references = [item.reference_id for item in candidate.references]
                if candidate.name == "cve":
                    ids = self.cve_ids(machine, scenario)
                    references = [key for key in ids if key in references]
                selected.append(
                    AppliedSkill(
                        reference_mode="required"
                        if candidate.name == "cve" and self.cve_ids(machine)
                        else "candidates",
                        **candidate.model_dump(),
                        selection_reason=reason,
                        selected_reference_ids=references,
                    )
                )
            elif candidate.name in required:
                raise ValueError(
                    f"Requested Skill {candidate.name} does not match {phase.value} prerequisites"
                )
        return sorted(selected, key=lambda item: (item.priority, item.name, item.version))

    @staticmethod
    def cve_ids(machine: MachineInformation, scenario: ScenarioDraft | None = None) -> list[str]:
        if scenario is not None:
            return sorted({step.cve_id for step in scenario.attack_graph.steps if step.cve_id})
        return sorted(set(machine.cve_ids))

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

        explicit = machine.skill_names is not None and candidate.name in machine.skill_names
        if explicit:
            reasons.append("explicit")
        elif candidate.name == "cve" and SkillSelector.cve_ids(machine, scenario):
            reasons.append("cve_id")
        elif selectors.themes:
            matched = next((term for term in selectors.themes if term in theme), None)
            if matched is None:
                return None
            reasons.append(f"theme:{matched}")
        elif not any(
            (
                selectors.operating_systems,
                selectors.attack_step_kinds,
                selectors.attack_phases,
                selectors.requires_user_flag is not None,
                selectors.requires_system_flag is not None,
            )
        ):
            return None
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
