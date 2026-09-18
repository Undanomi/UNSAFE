from __future__ import annotations

from uuid import UUID

from ai_server.models import utcnow
from ai_server.skills.loader import SkillDefinition
from ai_server.skills.models import StoredSkill, skill_checksum


def as_candidates(definitions: list[SkillDefinition]) -> list[StoredSkill]:
    return [
        StoredSkill(
            **item.metadata.model_dump(),
            **item.version.model_dump(),
            skill_id=UUID(int=i + 1),
            version=1,
            created_at=utcnow(),
            published_at=utcnow(),
            content_checksum=skill_checksum(
                item.version.instructions,
                item.version.phases,
                item.version.selectors,
                item.version.priority,
                item.version.references,
            ),
        )
        for i, item in enumerate(definitions)
    ]
