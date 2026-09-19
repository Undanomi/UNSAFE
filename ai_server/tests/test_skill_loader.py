from __future__ import annotations

import json
from pathlib import Path

import pytest
from skill_helpers import as_candidates

from ai_server.models import MachineInformation
from ai_server.skills.cli import main
from ai_server.skills.loader import load_skill, load_skills
from ai_server.skills.models import SkillPhase, skill_checksum
from ai_server.skills.renderer import SkillRenderer
from ai_server.skills.service import select_context


def write_skill(root: Path, name: str, extra: str = "") -> Path:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: >\n  演習用の指示。\n{extra}---\n\n# Overview\n本文。",
        encoding="utf-8",
    )
    return path


def test_references_are_separate_versioned_and_selectively_rendered(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "cve")
    refs = path.parent / "references"
    refs.mkdir()
    (refs / "CVE-2025-1234.md").write_text("Selected test guidance", encoding="utf-8")
    other = refs / "CVE-2025-5678.md"
    other.write_text("Unselected test guidance" * 3000, encoding="utf-8")
    definitions = load_skills(tmp_path, created_by="tester")
    assert "Selected test guidance" not in definitions[0].version.instructions
    assert len(definitions[0].version.references) == 2
    machine = MachineInformation(
        name="test",
        visibility="private",
        theme="test",
        difficulty="Easy",
        skill_names=["cve"],
        cve_ids=["CVE-2025-1234"],
    )
    candidates = as_candidates(definitions)
    context = select_context(candidates, SkillPhase.ATTACK_GRAPH, machine)
    prompt = SkillRenderer.render(context)
    assert "Selected test guidance" in prompt
    assert "Unselected test guidance" not in prompt
    assert len(prompt) < 5000
    other.write_text("Changed test guidance", encoding="utf-8")
    changed = as_candidates(load_skills(tmp_path, created_by="tester"))
    assert candidates[0].content_checksum != changed[0].content_checksum
    assert SkillRenderer.render(context) == prompt


@pytest.mark.parametrize(
    "content",
    [
        "# no frontmatter",
        "---\nname: test",
        "---\nname: test\n---\nbody",
        "---\nname: test\ndescription: demo\n---\n",
        "---\nname: test\nname: other\ndescription: demo\n---\nbody",
        "---\nname: test\ndescription: demo\nphases: []\n---\nbody",
        "---\nname: test\ndescription: demo\nselectors: {typo: value}\n---\nbody",
        "---\n!!python/object/apply:os.system ['echo unsafe']\n---\nbody",
    ],
)
def test_invalid_skill_fails_before_publish(tmp_path: Path, content: str, monkeypatch) -> None:
    from ai_server.repository import SessionRepository

    monkeypatch.setattr(SessionRepository, "__init__", lambda *a, **kw: pytest.fail("DB touched"))
    path = write_skill(tmp_path, "test")
    path.write_text(content, encoding="utf-8")
    assert main(["publish", str(tmp_path), "--created-by", "tester"]) == 1


def test_reference_symlink_and_duplicate_id_are_rejected(tmp_path: Path) -> None:
    path = write_skill(tmp_path, "cve")
    refs = path.parent / "references"
    refs.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    link = refs / "CVE-2025-1234.md"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="outside"):
        load_skill(path, created_by="tester")
    link.unlink()
    link.write_text("first", encoding="utf-8")
    (refs / "nested").mkdir()
    (refs / "nested" / link.name).write_text("second", encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_skill(path, created_by="tester")


def test_validate_does_not_use_database(tmp_path: Path, monkeypatch, capsys) -> None:
    from ai_server.repository import SessionRepository

    monkeypatch.setattr(SessionRepository, "__init__", lambda *a, **kw: pytest.fail("DB touched"))
    write_skill(tmp_path, "test-skill")
    assert main(["validate", str(tmp_path)]) == 0
    assert "valid: test-skill" in capsys.readouterr().out


def test_legacy_checksum_is_unchanged() -> None:
    import hashlib

    from ai_server.skills.models import SkillSelectors

    selectors = SkillSelectors()
    payload = {
        "instructions": "test",
        "phases": ["source"],
        "selectors": selectors.model_dump(mode="json"),
        "priority": 100,
    }
    previous = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert skill_checksum("test", [SkillPhase.SOURCE], selectors, 100, []) == previous
