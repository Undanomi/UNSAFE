from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_server.models import AttackGraph, AttackObjective, AttackStep


def step(step_id: str, *, requires=None, achieves=None) -> AttackStep:
    return AttackStep(
        step_id=step_id,
        title=step_id,
        kind="web_vulnerability",
        phase="initial_access",
        description="training step",
        requires=requires or [],
        achieves=achieves or [],
        implementation_steps=["provision the training condition"],
    )


def test_attack_graph_supports_chained_steps_and_multiple_objectives() -> None:
    graph = AttackGraph(
        objectives=[
            AttackObjective(
                objective_id="user-flag",
                objective_type="user_flag",
                description="user objective",
            ),
            AttackObjective(
                objective_id="system-flag",
                objective_type="system_flag",
                description="system objective",
            ),
        ],
        steps=[
            step("web-entry"),
            step("user-access", requires=["web-entry"], achieves=["user-flag"]),
            step("local-chain", requires=["user-access"]),
            step("root-access", requires=["local-chain"], achieves=["system-flag"]),
        ],
    )

    assert len(graph.steps) == 4


def test_attack_graph_rejects_cycles() -> None:
    with pytest.raises(ValidationError, match="contains a cycle"):
        AttackGraph(
            steps=[
                step("first", requires=["second"]),
                step("second", requires=["first"]),
            ]
        )


def test_attack_graph_rejects_unachieved_flag() -> None:
    with pytest.raises(ValidationError, match="not achieved"):
        AttackGraph(
            objectives=[
                AttackObjective(
                    objective_id="user-flag",
                    objective_type="user_flag",
                    description="user objective",
                )
            ],
            steps=[step("web-entry")],
        )


def test_non_cve_step_rejects_cve_id() -> None:
    with pytest.raises(ValidationError, match="only valid when kind is cve"):
        AttackStep(
            step_id="web-entry",
            title="web entry",
            kind="web_vulnerability",
            phase="initial_access",
            description="training step",
            cve_id="CVE-2026-1234",
            implementation_steps=["provision"],
        )
