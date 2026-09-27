from __future__ import annotations

from pathlib import Path

import pytest

from ai_server.models import (
    ROCKYOU_PASSWORD_PLACEHOLDER,
    AttackGraph,
    AttackStep,
    PasswordCrackingSpec,
    ScenarioDraft,
    rockyou_password_placeholder,
)
from ai_server.services.rockyou import (
    RockYouPasswordSelector,
    bind_rockyou_passwords,
    materialize_rockyou_placeholders,
    strip_rockyou_selections,
)


def test_selects_and_reuses_password_from_configured_window(tmp_path: Path) -> None:
    wordlist = tmp_path / "rockyou.txt"
    wordlist.write_bytes(
        b"outside01\ninside001\ninside002\ninside003\noutside02\n"
    )
    selector = RockYouPasswordSelector(wordlist, min_line=2, max_line=4)

    first = selector.select()
    second = selector.select()

    assert first == second
    assert first.password in {"inside001", "inside002", "inside003"}
    assert 2 <= first.line_number <= 4
    assert first.search_space_lines == 4


def test_rejects_missing_or_unusable_wordlist(tmp_path: Path) -> None:
    missing = RockYouPasswordSelector(tmp_path / "missing.txt", min_line=1, max_line=2)
    with pytest.raises(RuntimeError, match="rockyou.txt is unavailable"):
        missing.select()

    unusable_path = tmp_path / "rockyou.txt"
    unusable_path.write_bytes(b"short\n\xffinvalid-password\nquoted'password\n")
    unusable = RockYouPasswordSelector(unusable_path, min_line=1, max_line=3)
    with pytest.raises(RuntimeError, match="no prompt-safe entries"):
        unusable.select()


def test_binds_only_after_source_generation_and_materializes_placeholder(
    tmp_path: Path,
) -> None:
    wordlist = tmp_path / "rockyou.txt"
    wordlist.write_text("password123\n")
    spec = PasswordCrackingSpec(
        wordlist="rockyou.txt",
        hash_algorithm="bcrypt",
        hash_runtime="php",
        hash_api="password_hash",
        hashcat_mode=3200,
        target_crack_seconds=150,
    )
    scenario = ScenarioDraft(
        scenario_id="late-binding",
        title="Late binding",
        definition="Use the server-managed placeholder.",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="crack-password",
                    title="Crack password",
                    kind="password_cracking",
                    phase="initial_access",
                    description="Crack a credential.",
                    implementation_steps=["Hash the late-bound password"],
                    password_cracking=spec,
                )
            ]
        ),
    )

    assert spec.selection_bound is False
    bound = bind_rockyou_passwords(
        scenario, RockYouPasswordSelector(wordlist, min_line=1, max_line=1)
    )
    bound_spec = bound.attack_graph.steps[0].password_cracking
    assert bound_spec is not None
    assert bound_spec.password == "password123"
    assert bound_spec.line_number == 1
    assert bound_spec.search_space_lines == 1

    placeholder = rockyou_password_placeholder("crack-password")
    template = f"php -r 'password_hash(\"{placeholder}\", 1);'"
    assert placeholder not in materialize_rockyou_placeholders(
        template, bound
    )
    assert "password123" in materialize_rockyou_placeholders(template, bound)

    persisted = strip_rockyou_selections(
        bound.model_copy(update={"definition": "Selected password: password123"})
    )
    persisted_spec = persisted.attack_graph.steps[0].password_cracking
    assert persisted_spec is not None
    assert persisted_spec.password is None
    assert persisted_spec.line_number is None
    assert persisted_spec.search_space_lines is None
    assert "password123" not in persisted.definition


def test_binds_and_materializes_distinct_passwords_per_step(tmp_path: Path) -> None:
    wordlist = tmp_path / "rockyou.txt"
    wordlist.write_text("password123\npassword456\npassword789\n")
    spec = PasswordCrackingSpec(
        wordlist="rockyou.txt",
        hash_algorithm="bcrypt",
        hash_runtime="php",
        hash_api="password_hash",
        hashcat_mode=3200,
        target_crack_seconds=150,
    )
    scenario = ScenarioDraft(
        scenario_id="multiple-passwords",
        title="Multiple passwords",
        definition="Two independently selected credentials.",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="crack-web-password",
                    title="Crack web password",
                    kind="password_cracking",
                    phase="initial_access",
                    description="Crack the web credential.",
                    implementation_steps=["Hash the web credential"],
                    password_cracking=spec,
                ),
                AttackStep(
                    step_id="crack-ssh-password",
                    title="Crack SSH password",
                    kind="password_cracking",
                    phase="lateral_movement",
                    description="Crack the SSH credential.",
                    requires=["crack-web-password"],
                    implementation_steps=["Hash the SSH credential"],
                    password_cracking=spec.model_copy(deep=True),
                ),
            ]
        ),
    )

    bound = bind_rockyou_passwords(
        scenario,
        RockYouPasswordSelector(
            wordlist,
            min_line=1,
            max_line=3,
            selection_key="session-multiple",
        ),
    )
    selections = {
        step.step_id: step.password_cracking.password
        for step in bound.attack_graph.steps
        if step.password_cracking is not None
    }

    assert len(set(selections.values())) == 2
    rebound = bind_rockyou_passwords(
        scenario,
        RockYouPasswordSelector(
            wordlist,
            min_line=1,
            max_line=3,
            selection_key="session-multiple",
        ),
    )
    assert [
        step.password_cracking.password
        for step in rebound.attack_graph.steps
        if step.password_cracking is not None
    ] == list(selections.values())
    template = "|".join(
        rockyou_password_placeholder(step_id) for step_id in selections
    )
    assert materialize_rockyou_placeholders(template, bound) == "|".join(
        selections.values()
    )
    with pytest.raises(ValueError, match="legacy rockyou placeholder is ambiguous"):
        materialize_rockyou_placeholders(ROCKYOU_PASSWORD_PLACEHOLDER, bound)

    persisted = strip_rockyou_selections(
        bound.model_copy(
            update={"definition": "|".join(selections.values())}
        )
    )
    assert persisted.definition == template


def test_multiple_password_steps_require_enough_distinct_candidates(tmp_path: Path) -> None:
    wordlist = tmp_path / "rockyou.txt"
    wordlist.write_text("password123\n")
    spec = PasswordCrackingSpec(
        wordlist="rockyou.txt",
        hash_algorithm="bcrypt",
        hash_runtime="php",
        hash_api="password_hash",
        hashcat_mode=3200,
        target_crack_seconds=150,
    )
    scenario = ScenarioDraft(
        scenario_id="insufficient-passwords",
        title="Insufficient passwords",
        definition="Two credentials are required.",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id=step_id,
                    title=step_id,
                    kind="password_cracking",
                    phase="initial_access",
                    description="Crack a distinct credential.",
                    implementation_steps=["Hash the credential"],
                    password_cracking=spec.model_copy(deep=True),
                )
                for step_id in ("crack-first", "crack-second")
            ]
        ),
    )

    with pytest.raises(RuntimeError, match="no unused prompt-safe entries"):
        bind_rockyou_passwords(
            scenario,
            RockYouPasswordSelector(
                wordlist,
                min_line=1,
                max_line=1,
                selection_key="session-insufficient",
            ),
        )


def test_keyed_selection_is_repeatable_across_selector_instances(tmp_path: Path) -> None:
    wordlist = tmp_path / "rockyou.txt"
    wordlist.write_text("password123\npassword456\npassword789\n")

    first = RockYouPasswordSelector(
        wordlist, min_line=1, max_line=3, selection_key="session-1"
    ).select()
    second = RockYouPasswordSelector(
        wordlist, min_line=1, max_line=3, selection_key="session-1"
    ).select()

    assert first == second
