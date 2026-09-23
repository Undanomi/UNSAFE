from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from ..models import (
    ROCKYOU_PASSWORD_PLACEHOLDER,
    AttackGraph,
    ScenarioDraft,
    rockyou_password_placeholder,
)

ROCKYOU_STEP_PLACEHOLDER_PATTERN = re.compile(
    r"__SLSG_ROCKYOU_PASSWORD_[a-z][a-z0-9_-]{0,63}__"
)


@dataclass(frozen=True)
class RockYouPasswordSelection:
    password: str
    line_number: int
    search_space_lines: int


class RockYouPasswordSelector:
    """Select repeatable, prompt-safe passwords after AI source generation."""

    def __init__(
        self,
        path: Path,
        min_line: int,
        max_line: int,
        selection_key: str | None = None,
    ) -> None:
        if min_line < 1:
            raise ValueError("rockyou minimum line must be positive")
        if max_line < min_line:
            raise ValueError("rockyou maximum line must not be less than minimum line")
        self.path = path
        self.min_line = min_line
        self.max_line = max_line
        self.selection_key = selection_key
        self.selections: dict[str, RockYouPasswordSelection] = {}

    def select(self) -> RockYouPasswordSelection:
        return self._select_cached("default", self.selection_key, set())

    def select_for(
        self,
        step_id: str,
        excluded_passwords: set[str] | None = None,
    ) -> RockYouPasswordSelection:
        scoped_key = (
            None if self.selection_key is None else f"{self.selection_key}\0{step_id}"
        )
        return self._select_cached(
            f"step:{step_id}",
            scoped_key,
            excluded_passwords or set(),
        )

    def _select_cached(
        self,
        cache_key: str,
        selection_key: str | None,
        excluded_passwords: set[str],
    ) -> RockYouPasswordSelection:
        if cache_key not in self.selections:
            self.selections[cache_key] = self._select(selection_key, excluded_passwords)
        selection = self.selections[cache_key]
        if selection.password in excluded_passwords:
            raise RuntimeError(
                f"rockyou selection for {cache_key} conflicts with another password step"
            )
        return selection

    def _select(
        self,
        selection_key: str | None,
        excluded_passwords: set[str],
    ) -> RockYouPasswordSelection:
        candidates: list[tuple[int, str]] = []
        try:
            wordlist = self.path.open("rb")
        except OSError as error:
            raise RuntimeError(f"rockyou.txt is unavailable at {self.path}: {error}") from error

        with wordlist:
            for line_number, raw_line in enumerate(wordlist, start=1):
                if line_number > self.max_line:
                    break
                if line_number < self.min_line:
                    continue
                password = self._safe_password(raw_line)
                if password is not None and password not in excluded_passwords:
                    candidates.append((line_number, password))

        if not candidates:
            qualifier = "unused " if excluded_passwords else ""
            raise RuntimeError(
                f"rockyou.txt contains no {qualifier}prompt-safe entries in lines "
                f"{self.min_line}-{self.max_line}"
            )
        if selection_key is None:
            line_number, password = secrets.choice(candidates)
        else:
            digest = hashlib.sha256(selection_key.encode("utf-8")).digest()
            line_number, password = candidates[int.from_bytes(digest, "big") % len(candidates)]
        return RockYouPasswordSelection(
            password=password,
            line_number=line_number,
            search_space_lines=self.max_line,
        )

    @staticmethod
    def _safe_password(raw_line: bytes) -> str | None:
        password_bytes = raw_line.rstrip(b"\r\n")
        if not 8 <= len(password_bytes) <= 32:
            return None
        try:
            password = password_bytes.decode("ascii")
        except UnicodeDecodeError:
            return None
        if not password.isascii() or not password.isalnum():
            return None
        return password


def bind_rockyou_passwords(
    scenario: ScenarioDraft,
    selector: RockYouPasswordSelector,
) -> ScenarioDraft:
    """Late-bind one server-selected password after source generation."""
    cracking_steps = [
        step for step in scenario.attack_graph.steps if step.password_cracking is not None
    ]
    if not cracking_steps:
        return scenario
    bound = [
        spec.selection_bound
        for step in cracking_steps
        if (spec := step.password_cracking) is not None
    ]
    if all(bound):
        return scenario
    if any(bound):
        raise ValueError("password cracking selections must be consistently bound")

    use_legacy_single_selection = len(cracking_steps) == 1
    selected_passwords: set[str] = set()
    steps = []
    for step in scenario.attack_graph.steps:
        spec = step.password_cracking
        if spec is None:
            steps.append(step)
            continue
        selection = (
            selector.select()
            if use_legacy_single_selection
            else selector.select_for(step.step_id, selected_passwords)
        )
        selected_passwords.add(selection.password)
        steps.append(
            step.model_copy(
                update={
                    "password_cracking": spec.model_copy(
                        update={
                            "password": selection.password,
                            "line_number": selection.line_number,
                            "search_space_lines": selection.search_space_lines,
                        }
                    )
                }
            )
        )
    graph = scenario.attack_graph.model_copy(update={"steps": steps})
    return scenario.model_copy(update={"attack_graph": graph})


def strip_rockyou_graph(graph: AttackGraph) -> AttackGraph:
    """Clear construction-only selections from an attack graph."""
    steps = []
    for step in graph.steps:
        spec = step.password_cracking
        if spec is None:
            steps.append(step)
            continue
        steps.append(
            step.model_copy(
                update={
                    "password_cracking": spec.model_copy(
                        update={
                            "password": None,
                            "line_number": None,
                            "search_space_lines": None,
                        }
                    )
                }
            )
        )
    return graph.model_copy(update={"steps": steps})


def strip_rockyou_selections(scenario: ScenarioDraft) -> ScenarioDraft:
    """Remove construction-only rockyou values from a persisted design artifact."""
    selected_passwords = [
        (spec.password, rockyou_password_placeholder(step.step_id))
        for step in scenario.attack_graph.steps
        if (spec := step.password_cracking) is not None and spec.password is not None
    ]
    definition = scenario.definition
    for password, placeholder in sorted(
        selected_passwords, key=lambda item: len(item[0]), reverse=True
    ):
        definition = definition.replace(password, placeholder)
    graph = strip_rockyou_graph(scenario.attack_graph)
    return scenario.model_copy(update={"attack_graph": graph, "definition": definition})


def materialize_rockyou_placeholders(text: str, scenario: ScenarioDraft) -> str:
    """Replace the framework-owned placeholder only after AI generation has finished."""
    selections = {
        step.step_id: spec.password
        for step in scenario.attack_graph.steps
        if (spec := step.password_cracking) is not None and spec.password is not None
    }
    if not selections:
        return text
    for step_id, password in selections.items():
        text = text.replace(rockyou_password_placeholder(step_id), password)
    if ROCKYOU_PASSWORD_PLACEHOLDER in text:
        if len(selections) != 1:
            raise ValueError(
                "the legacy rockyou placeholder is ambiguous with multiple password steps"
            )
        text = text.replace(ROCKYOU_PASSWORD_PLACEHOLDER, next(iter(selections.values())))
    unresolved = ROCKYOU_STEP_PLACEHOLDER_PATTERN.findall(text)
    if unresolved:
        raise ValueError(
            "rockyou placeholders reference unknown password steps: "
            + ", ".join(sorted(set(unresolved)))
        )
    return text
