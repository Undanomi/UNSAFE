from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from ..models import ROCKYOU_PASSWORD_PLACEHOLDER, ScenarioDraft


@dataclass(frozen=True)
class RockYouPasswordSelection:
    password: str
    line_number: int
    search_space_lines: int


class RockYouPasswordSelector:
    """Select one prompt-safe password after AI source generation."""

    def __init__(self, path: Path, min_line: int, max_line: int) -> None:
        if min_line < 1:
            raise ValueError("rockyou minimum line must be positive")
        if max_line < min_line:
            raise ValueError("rockyou maximum line must not be less than minimum line")
        self.path = path
        self.min_line = min_line
        self.max_line = max_line
        self.selection: RockYouPasswordSelection | None = None

    def select(self) -> RockYouPasswordSelection:
        if self.selection is None:
            self.selection = self._select()
        return self.selection

    def _select(self) -> RockYouPasswordSelection:
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
                if password is not None:
                    candidates.append((line_number, password))

        if not candidates:
            raise RuntimeError(
                "rockyou.txt contains no prompt-safe entries in lines "
                f"{self.min_line}-{self.max_line}"
            )
        line_number, password = secrets.choice(candidates)
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

    selection = selector.select()
    steps = []
    for step in scenario.attack_graph.steps:
        spec = step.password_cracking
        if spec is None:
            steps.append(step)
            continue
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


def materialize_rockyou_placeholders(text: str, scenario: ScenarioDraft) -> str:
    """Replace the framework-owned placeholder only after AI generation has finished."""
    passwords = {
        spec.password
        for step in scenario.attack_graph.steps
        if (spec := step.password_cracking) is not None and spec.password is not None
    }
    if not passwords:
        return text
    if len(passwords) != 1:
        raise ValueError("all password cracking steps must share one rockyou selection")
    return text.replace(ROCKYOU_PASSWORD_PLACEHOLDER, next(iter(passwords)))
