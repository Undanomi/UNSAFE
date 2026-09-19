"""Import a local checkout of YAML + Markdown definitions without executing it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ConfigDict, Field, ValidationError

from .models import SkillCreate, SkillPhase, SkillReference, SkillSelectors, SkillVersionCreate


class FrontmatterSelectors(SkillSelectors):
    model_config = ConfigDict(extra="forbid")


class SkillFrontmatter(SkillCreate):
    model_config = ConfigDict(extra="forbid")
    phases: list[SkillPhase] = Field(default_factory=lambda: list(SkillPhase))
    selectors: FrontmatterSelectors = Field(default_factory=FrontmatterSelectors)
    priority: int = Field(default=100, ge=-10_000, le=10_000)


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError("YAML keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True)
class SkillDefinition:
    source: Path
    metadata: SkillCreate
    version: SkillVersionCreate


def _read(path: Path, root: Path) -> str:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"File is outside the Skill directory: {path}")
    with path.open(encoding="utf-8-sig") as stream:
        value = stream.read(100_001)
    if len(value) > 100_000 or not value.strip():
        raise ValueError(f"Markdown must contain 1 to 100000 characters: {path}")
    return value.strip()


def load_skill(path: Path, *, created_by: str) -> SkillDefinition:
    try:
        lines = _read(path, path.parent).splitlines()
        if lines[0] != "---":
            raise ValueError("SKILL.md must start with YAML frontmatter (---)")
        closing = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
        if closing is None:
            raise ValueError("YAML frontmatter is missing its closing ---")
        metadata = SkillFrontmatter.model_validate(
            yaml.load("\n".join(lines[1:closing]), Loader=UniqueKeyLoader)
        )
        body = "\n".join(lines[closing + 1 :]).strip()
        if not body:
            raise ValueError("SKILL.md must contain a Markdown body")
        references = []
        directory = path.parent / "references"
        if directory.exists():
            if not directory.is_dir() or not directory.resolve().is_relative_to(
                path.parent.resolve()
            ):
                raise ValueError("references must be a directory inside the Skill directory")
            for reference in sorted(directory.rglob("*.md")):
                reference_id = reference.stem
                if metadata.name == "cve" and not re.fullmatch(r"CVE-\d{4}-\d{4,7}", reference_id):
                    raise ValueError("CVE reference filenames must be CVE-YYYY-NNNN.md")
                references.append(
                    SkillReference(
                        reference_id=reference_id,
                        path=reference.relative_to(path.parent).as_posix(),
                        content=_read(reference, path.parent),
                    )
                )
                if (
                    len(references) > 200
                    or sum(len(item.content) for item in references) > 2_000_000
                ):
                    raise ValueError("Skill references exceed the import limit")
        return SkillDefinition(
            source=path,
            metadata=SkillCreate(name=metadata.name, description=metadata.description),
            version=SkillVersionCreate(
                instructions=f"適用対象: {metadata.description}\n\n{body}",
                phases=metadata.phases,
                selectors=metadata.selectors,
                priority=metadata.priority,
                created_by=created_by,
                references=references,
            ),
        )
    except (ValueError, OSError, yaml.YAMLError) as error:
        if isinstance(error, ValidationError):
            detail = "; ".join(
                f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in error.errors()
            )
        else:
            detail = str(error)
        raise ValueError(f"{path}: {detail}") from error


def load_skills(root: Path, *, created_by: str) -> list[SkillDefinition]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Skill directory does not exist: {root}")
    paths = (
        [root / "SKILL.md"] if (root / "SKILL.md").is_file() else sorted(root.glob("*/SKILL.md"))
    )
    if not paths:
        raise ValueError(f"No SKILL.md found under {root}")
    result = []
    names = set()
    for path in paths:
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Skill is outside the supplied directory: {path}")
        definition = load_skill(path, created_by=created_by)
        if definition.metadata.name in names:
            raise ValueError(f"Duplicate Skill name: {definition.metadata.name}")
        names.add(definition.metadata.name)
        result.append(definition)
    return result
