from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SkillPhase(StrEnum):
    ATTACK_GRAPH = "attack_graph"
    SCENARIO = "scenario"
    SOURCE = "source"
    REPAIR = "repair"
    REVIEW = "review"


class SkillStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class SkillSelectors(BaseModel):
    themes: list[str] = Field(default_factory=list, max_length=50)
    operating_systems: list[str] = Field(default_factory=list, max_length=20)
    attack_step_kinds: list[str] = Field(default_factory=list, max_length=50)
    attack_phases: list[str] = Field(default_factory=list, max_length=50)
    requires_user_flag: bool | None = None
    requires_system_flag: bool | None = None

    @field_validator("themes", "operating_systems", "attack_step_kinds", "attack_phases")
    @classmethod
    def normalize_terms(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            term = value.strip().casefold()
            if not term:
                raise ValueError("skill selector terms must not be blank")
            if len(term) > 100:
                raise ValueError("skill selector terms must not exceed 100 characters")
            if term not in normalized:
                normalized.append(term)
        return normalized


class SkillCreate(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
    description: str = Field(min_length=1, max_length=2000)


class SkillVersionCreate(BaseModel):
    instructions: str = Field(min_length=1, max_length=100_000)
    phases: list[SkillPhase] = Field(min_length=1, max_length=5)
    selectors: SkillSelectors = Field(default_factory=SkillSelectors)
    priority: int = Field(default=100, ge=-10_000, le=10_000)
    created_by: str = Field(min_length=1, max_length=500)

    @field_validator("instructions")
    @classmethod
    def instructions_must_have_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("skill instructions must not be blank")
        return value

    @field_validator("phases")
    @classmethod
    def phases_must_be_unique(cls, values: list[SkillPhase]) -> list[SkillPhase]:
        if len(values) != len(set(values)):
            raise ValueError("skill phases must be unique")
        return values


class StoredSkill(BaseModel):
    skill_id: UUID
    name: str
    description: str
    version: int
    instructions: str
    phases: list[SkillPhase]
    selectors: SkillSelectors
    priority: int
    content_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime
    published_at: datetime | None = None

    def verify_checksum(self) -> None:
        expected = skill_checksum(
            self.instructions,
            self.phases,
            self.selectors,
            self.priority,
        )
        if self.content_checksum != expected:
            raise ValueError(
                f"published skill {self.name} version {self.version} checksum does not match"
            )


class AppliedSkill(StoredSkill):
    selection_reason: str


class SkillContext(BaseModel):
    phase: SkillPhase
    skills: list[AppliedSkill] = Field(default_factory=list)


class ScenarioSkillContexts(BaseModel):
    attack_graph: SkillContext = Field(
        default_factory=lambda: SkillContext(phase=SkillPhase.ATTACK_GRAPH)
    )
    scenario: SkillContext = Field(default_factory=lambda: SkillContext(phase=SkillPhase.SCENARIO))


def skill_checksum(
    instructions: str,
    phases: list[SkillPhase],
    selectors: SkillSelectors,
    priority: int,
) -> str:
    canonical = json.dumps(
        {
            "instructions": instructions,
            "phases": [phase.value for phase in phases],
            "selectors": selectors.model_dump(mode="json"),
            "priority": priority,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
