from __future__ import annotations

from pathlib import Path

import pytest

from ai_server.models import (
    ROCKYOU_PASSWORD_PLACEHOLDER,
    AttackGraph,
    AttackStep,
    PasswordCrackingSpec,
    ScenarioDraft,
)
from ai_server.services.rockyou import (
    RockYouPasswordSelector,
    bind_rockyou_passwords,
    materialize_rockyou_placeholders,
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

    template = f"php -r 'password_hash(\"{ROCKYOU_PASSWORD_PLACEHOLDER}\", 1);'"
    assert ROCKYOU_PASSWORD_PLACEHOLDER not in materialize_rockyou_placeholders(
        template, bound
    )
    assert "password123" in materialize_rockyou_placeholders(template, bound)
