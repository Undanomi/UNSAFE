from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_server.models import (
    AttackGraph,
    AttackObjective,
    AttackStep,
    AutomaticFlagPlan,
    MachineInformation,
    PasswordCrackingSpec,
    ScenarioDraft,
)


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


def test_password_cracking_step_requires_structured_metadata() -> None:
    with pytest.raises(ValidationError, match="requires password_cracking metadata"):
        AttackStep(
            step_id="crack-password",
            title="Crack password",
            kind="password_cracking",
            phase="initial_access",
            description="Crack the stored credential.",
            implementation_steps=["Provision the hash"],
        )

    spec = PasswordCrackingSpec(
        wordlist="rockyou.txt",
        password="password01",
        line_number=123_456,
        search_space_lines=200_000,
        hash_algorithm="bcrypt",
        hash_runtime="php",
        hash_api="password_hash",
        hashcat_mode=3200,
        target_crack_seconds=150,
    )
    parsed = AttackStep(
        step_id="crack-password",
        title="Crack password",
        kind="password_cracking",
        phase="initial_access",
        description="Crack the stored credential.",
        implementation_steps=["Provision the hash"],
        password_cracking=spec,
    )
    assert parsed.password_cracking == spec

    unbound = spec.model_copy(
        update={"password": None, "line_number": None, "search_space_lines": None}
    )
    assert PasswordCrackingSpec.model_validate(unbound.model_dump()).selection_bound is False

    with pytest.raises(ValidationError, match="all unset or all populated"):
        PasswordCrackingSpec.model_validate(
            {
                **unbound.model_dump(),
                "password": "password01",
            }
        )

    with pytest.raises(ValidationError, match="only valid when kind is password_cracking"):
        AttackStep(
            step_id="web-entry",
            title="Web entry",
            kind="web_vulnerability",
            phase="initial_access",
            description="Enter through the web app.",
            implementation_steps=["Provision the app"],
            password_cracking=spec,
        )


def test_scenario_rejects_noncanonical_flag_case() -> None:
    with pytest.raises(ValidationError, match="user_flag"):
        ScenarioDraft(
            scenario_id="scenario-invalid-flag",
            title="Invalid flag",
            definition="# Invalid flag",
            attack_graph=AttackGraph(steps=[step("entry")]),
            user_flag="FLAG{USER_A1D51D7F803F51F0356F3E547C842A0B}",
        )


@pytest.mark.parametrize(
    ("selection", "needs_user", "needs_system"),
    [
        ("user", True, False),
        ("system", False, True),
        ("both", True, True),
    ],
)
def test_automatic_flag_plan_applies_all_supported_selections(
    selection: str,
    needs_user: bool,
    needs_system: bool,
) -> None:
    plan = AutomaticFlagPlan(
        selection=selection,
        user_flag_details="Obtain /home/student/user.txt" if needs_user else "",
        system_flag_details="Obtain /root/system.txt" if needs_system else "",
    )
    machine = MachineInformation(
        name="Automatic flags",
        visibility="private",
        theme="Web security",
        difficulty="Medium",
    ).with_automatic_flag_plan(plan)

    assert machine.needs_user_flag is needs_user
    assert machine.needs_system_flag is needs_system
    assert bool(machine.user_flag_details) is needs_user
    assert bool(machine.system_flag_details) is needs_system


def test_automatic_flag_plan_rejects_missing_selected_details() -> None:
    with pytest.raises(ValidationError, match="system_flag_details"):
        AutomaticFlagPlan(
            selection="both",
            user_flag_details="Obtain /home/student/user.txt",
            system_flag_details="",
        )


def test_flag_details_reject_server_managed_flag_value() -> None:
    with pytest.raises(ValidationError, match="flag values are generated by the server"):
        MachineInformation(
            name="Invalid details",
            visibility="private",
            theme="Web",
            difficulty="Easy",
            needs_user_flag=True,
            user_flag_details="flag{user_a1d51d7f803f51f0356f3e547c842a0b}",
        )


def test_flag_details_promote_cves_to_dedicated_field() -> None:
    promoted = MachineInformation(
        name="Promoted CVE details",
        visibility="private",
        theme="Web",
        difficulty="Easy",
        needs_user_flag=True,
        user_flag_details="CVE-2026-42533を用いたRCE。",
    )
    assert promoted.cve_ids == ["CVE-2026-42533"]

    deduplicated = MachineInformation(
        name="Explicit CVE details",
        visibility="private",
        theme="Web",
        difficulty="Easy",
        needs_user_flag=True,
        user_flag_details="Exploit cve-2026-42533 to obtain the user flag",
        cve_ids=["CVE-2026-42533"],
    )
    assert deduplicated.cve_ids == ["CVE-2026-42533"]
