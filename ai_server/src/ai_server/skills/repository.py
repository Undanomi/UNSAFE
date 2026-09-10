from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..database import (
    SessionSkillSnapshotItemRecord,
    SessionSkillSnapshotRecord,
    SkillRecord,
    SkillVersionRecord,
)
from ..models import utcnow
from .models import (
    AppliedSkill,
    SkillContext,
    SkillCreate,
    SkillPhase,
    SkillStatus,
    SkillVersionCreate,
    StoredSkill,
    skill_checksum,
)


class SkillNotFoundError(Exception):
    pass


class SkillRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_skill(self, value: SkillCreate) -> UUID:
        skill_id = uuid4()
        now = utcnow()
        async with self.session_factory.begin() as session:
            session.add(
                SkillRecord(
                    skill_id=skill_id,
                    name=value.name,
                    description=value.description,
                    status=SkillStatus.DRAFT.value,
                    current_version=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        return skill_id

    async def publish_version(self, skill_id: UUID, value: SkillVersionCreate) -> StoredSkill:
        now = utcnow()
        async with self.session_factory.begin() as session:
            record = await session.get(SkillRecord, skill_id, with_for_update=True)
            if record is None:
                raise SkillNotFoundError(str(skill_id))
            version = (record.current_version or 0) + 1
            checksum = skill_checksum(
                value.instructions,
                value.phases,
                value.selectors,
                value.priority,
            )
            session.add(
                SkillVersionRecord(
                    skill_id=skill_id,
                    version=version,
                    instructions=value.instructions,
                    phases=[phase.value for phase in value.phases],
                    selectors=value.selectors.model_dump(mode="json"),
                    priority=value.priority,
                    content_checksum=checksum,
                    created_by=value.created_by,
                    created_at=now,
                    published_at=now,
                )
            )
            record.current_version = version
            record.status = SkillStatus.ACTIVE.value
            record.updated_at = now
            result = self._stored_skill(record, record_version=None, value=value, now=now)
        return result

    async def set_status(self, skill_id: UUID, status: SkillStatus) -> None:
        async with self.session_factory.begin() as session:
            result = await session.execute(
                update(SkillRecord)
                .where(SkillRecord.skill_id == skill_id)
                .values(status=status.value, updated_at=utcnow())
            )
            if result.rowcount == 0:
                raise SkillNotFoundError(str(skill_id))

    async def active_versions(self, limit: int) -> list[StoredSkill]:
        statement = (
            select(SkillRecord, SkillVersionRecord)
            .join(
                SkillVersionRecord,
                and_(
                    SkillVersionRecord.skill_id == SkillRecord.skill_id,
                    SkillVersionRecord.version == SkillRecord.current_version,
                ),
            )
            .where(SkillRecord.status == SkillStatus.ACTIVE.value)
            .order_by(SkillVersionRecord.priority, SkillRecord.name)
            .limit(limit + 1)
        )
        async with self.session_factory() as session:
            rows = (await session.execute(statement)).all()
        if len(rows) > limit:
            raise ValueError(f"active skill count exceeds configured limit {limit}")
        skills = [self._stored_skill(row[0], row[1]) for row in rows]
        for skill in skills:
            skill.verify_checksum()
        return skills

    async def get_snapshot(self, session_id: str, phase: SkillPhase) -> SkillContext | None:
        parsed_session_id = UUID(session_id)
        async with self.session_factory() as session:
            snapshot = await session.get(
                SessionSkillSnapshotRecord,
                (parsed_session_id, phase.value),
            )
            if snapshot is None:
                return None
            statement = (
                select(
                    SessionSkillSnapshotItemRecord,
                    SkillRecord,
                    SkillVersionRecord,
                )
                .join(
                    SkillVersionRecord,
                    and_(
                        SkillVersionRecord.skill_id == SessionSkillSnapshotItemRecord.skill_id,
                        SkillVersionRecord.version == SessionSkillSnapshotItemRecord.skill_version,
                    ),
                )
                .join(SkillRecord, SkillRecord.skill_id == SkillVersionRecord.skill_id)
                .where(
                    SessionSkillSnapshotItemRecord.session_id == parsed_session_id,
                    SessionSkillSnapshotItemRecord.phase == phase.value,
                )
                .order_by(SessionSkillSnapshotItemRecord.position)
            )
            rows = (await session.execute(statement)).all()
        applied: list[AppliedSkill] = []
        for item, skill_record, version_record in rows:
            skill = self._stored_skill(skill_record, version_record)
            skill.verify_checksum()
            if item.content_checksum != skill.content_checksum:
                raise ValueError(
                    f"skill snapshot checksum does not match {skill.name} version {skill.version}"
                )
            applied.append(
                AppliedSkill(**skill.model_dump(), selection_reason=item.selection_reason)
            )
        return SkillContext(phase=phase, skills=applied)

    async def create_snapshot(
        self,
        session_id: str,
        phase: SkillPhase,
        selected: list[AppliedSkill],
    ) -> SkillContext:
        parsed_session_id = UUID(session_id)
        now = utcnow()
        created = False
        async with self.session_factory.begin() as session:
            result = await session.execute(
                insert(SessionSkillSnapshotRecord)
                .values(session_id=parsed_session_id, phase=phase.value, resolved_at=now)
                .on_conflict_do_nothing(index_elements=["session_id", "phase"])
            )
            created = result.rowcount == 1
            if created:
                for position, skill in enumerate(selected):
                    session.add(
                        SessionSkillSnapshotItemRecord(
                            session_id=parsed_session_id,
                            phase=phase.value,
                            skill_id=skill.skill_id,
                            skill_version=skill.version,
                            position=position,
                            selection_reason=skill.selection_reason,
                            content_checksum=skill.content_checksum,
                        )
                    )
        if created:
            return SkillContext(phase=phase, skills=selected)
        existing = await self.get_snapshot(session_id, phase)
        assert existing is not None
        return existing

    async def snapshot_manifest(self, session_id: str) -> dict[str, list[dict]]:
        manifest: dict[str, list[dict]] = {}
        for phase in SkillPhase:
            snapshot = await self.get_snapshot(session_id, phase)
            if snapshot is None:
                continue
            manifest[phase.value] = [
                {
                    "skill_id": str(skill.skill_id),
                    "name": skill.name,
                    "version": skill.version,
                    "checksum": skill.content_checksum,
                    "selection_reason": skill.selection_reason,
                }
                for skill in snapshot.skills
            ]
        return manifest

    async def clear_snapshots(self, session_id: str) -> None:
        async with self.session_factory.begin() as session:
            await session.execute(
                delete(SessionSkillSnapshotRecord).where(
                    SessionSkillSnapshotRecord.session_id == UUID(session_id)
                )
            )

    @staticmethod
    def _stored_skill(
        skill: SkillRecord,
        record_version: SkillVersionRecord | None,
        value: SkillVersionCreate | None = None,
        now=None,
    ) -> StoredSkill:
        if record_version is not None:
            return StoredSkill(
                skill_id=skill.skill_id,
                name=skill.name,
                description=skill.description,
                version=record_version.version,
                instructions=record_version.instructions,
                phases=record_version.phases,
                selectors=record_version.selectors,
                priority=record_version.priority,
                content_checksum=record_version.content_checksum,
                created_by=record_version.created_by,
                created_at=record_version.created_at,
                published_at=record_version.published_at,
            )
        assert value is not None and now is not None and skill.current_version is not None
        return StoredSkill(
            skill_id=skill.skill_id,
            name=skill.name,
            description=skill.description,
            version=skill.current_version,
            instructions=value.instructions,
            phases=value.phases,
            selectors=value.selectors,
            priority=value.priority,
            content_checksum=skill_checksum(
                value.instructions, value.phases, value.selectors, value.priority
            ),
            created_by=value.created_by,
            created_at=now,
            published_at=now,
        )
