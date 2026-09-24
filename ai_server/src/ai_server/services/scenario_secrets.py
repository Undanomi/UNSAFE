from __future__ import annotations

from ..models import ScenarioDraft

USER_FLAG_PLACEHOLDER = "__SLSG_USER_FLAG__"
SYSTEM_FLAG_PLACEHOLDER = "__SLSG_SYSTEM_FLAG__"


def scenario_flag_placeholders(scenario: ScenarioDraft) -> tuple[tuple[str, str], ...]:
    """Return only the flag placeholders that are meaningful for this scenario."""

    values: list[tuple[str, str]] = []
    if scenario.user_flag:
        values.append((scenario.user_flag, USER_FLAG_PLACEHOLDER))
    if scenario.system_flag:
        values.append((scenario.system_flag, SYSTEM_FLAG_PLACEHOLDER))
    return tuple(values)


def materialize_scenario_flag_placeholders(text: str, scenario: ScenarioDraft) -> str:
    """Replace typed flag placeholders immediately before archiving the source."""

    result = text
    required = scenario_flag_placeholders(scenario)
    known_placeholders = {placeholder for _, placeholder in required}
    for value, placeholder in required:
        result = result.replace(placeholder, value)

    unsupported = {
        USER_FLAG_PLACEHOLDER,
        SYSTEM_FLAG_PLACEHOLDER,
    } - known_placeholders
    remaining = sorted(placeholder for placeholder in unsupported if placeholder in result)
    if remaining:
        raise ValueError(
            "flag placeholder has no configured value: " + ", ".join(remaining)
        )
    return result


def redact_scenario_flags(text: str, scenario: ScenarioDraft) -> str:
    """Restore typed placeholders before generated content is sent to an AI model."""

    result = text
    for value, placeholder in sorted(
        scenario_flag_placeholders(scenario), key=lambda item: len(item[0]), reverse=True
    ):
        result = result.replace(value, placeholder)
    return result
