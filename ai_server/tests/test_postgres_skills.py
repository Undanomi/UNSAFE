from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from ai_server.database import AISessionRecord, SkillRecord, SkillVersionRecord
from ai_server.models import MachineInformation
from ai_server.repository import SessionRepository
from ai_server.skills.models import (
    SkillCreate,
    SkillPhase,
    SkillReference,
    SkillStatus,
    SkillVersionCreate,
)
from ai_server.skills.planning import SemanticSkillPlanner
from ai_server.skills.repository import SkillRepository
from ai_server.skills.service import SkillService


@pytest.mark.asyncio
async def test_import_references_round_trip_and_pinning():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    repository = SessionRepository(url)
    await repository.initialize()
    skills = SkillRepository(repository.session_factory)
    state = await repository.create("skill-import-test")
    skill_id = None
    name = f"test-{uuid4().hex}"
    metadata = SkillCreate(name=name, description="integration")
    version = SkillVersionCreate(
        instructions="Common instructions",
        phases=list(SkillPhase),
        created_by="test",
        references=[
            SkillReference(
                reference_id="example", path="references/example.md", content="Old reference"
            )
        ],
    )
    try:
        published = await skills.publish_definitions([(metadata, version)])
        first, changed = published[0]
        skill_id = first.skill_id
        assert changed and first.version == 1
        first.verify_checksum()
        unchanged = await skills.publish_definitions([(metadata, version)])
        assert unchanged[0][1] is False
        state.machine_information = MachineInformation(
            name="test", visibility="private", theme="test", difficulty="Easy", skill_names=[name]
        )
        await repository.save(state)
        loaded = await repository.get(state.session_id)
        assert loaded.machine_information.skill_names == [name]
        service = SkillService(skills, max_active=100, max_per_phase=8, max_context_chars=50000)
        snapshot = await service.resolve(
            state.session_id, SkillPhase.ATTACK_GRAPH, loaded.machine_information
        )
        assert snapshot.skills[0].selected_reference_ids == ["example"]
        assert await skills.get_snapshot(state.session_id, SkillPhase.ATTACK_GRAPH) == snapshot

        version.references[0].content = "New reference"
        second, changed = (await skills.publish_definitions([(metadata, version)]))[0]
        assert changed and second.version == 2
        assert second.content_checksum != first.content_checksum
        assert second.references[0].content == "New reference"
        later = await service.resolve(
            state.session_id, SkillPhase.SCENARIO, loaded.machine_information
        )
        assert later.skills[0].version == 1
        assert later.skills[0].references[0].content == "Old reference"
        manifest = await skills.snapshot_manifest(state.session_id)
        assert manifest["scenario"][0]["references"][0]["checksum"] == first.references[0].checksum

        # Persist and reload the new selection plan, including the reference mode/reasons.
        await service.reset(state.session_id)

        async def never_generate(*args, **kwargs):
            pytest.fail("Explicit selection must not call Gemini")

        plan = await SemanticSkillPlanner(never_generate, model="test").plan(
            loaded.machine_information, [first]
        )
        plan.skills[0].reference_mode = "candidates"
        plan.skills[0].reference_reasons = {"example": "matches the learning goal"}
        assert await skills.create_plan(state.session_id, plan) == plan
        assert await skills.get_plan(state.session_id) == plan
        planned_service = SkillService(
            skills,
            max_active=100,
            max_per_phase=8,
            max_context_chars=50000,
            planner=SemanticSkillPlanner(never_generate, model="test"),
        )
        snapshot = await planned_service.resolve(
            state.session_id, SkillPhase.SCENARIO, loaded.machine_information
        )
        assert snapshot.skills[0].version == 1  # The DB already has version 2.
        assert (
            await skills.get_snapshot(state.session_id, SkillPhase.SCENARIO)
        ).skills == snapshot.skills
        assert (
            await planned_service.resolve(
                state.session_id, SkillPhase.SCENARIO, loaded.machine_information
            )
            == snapshot
        )
        snapshot.skills[0].reference_mode = "used"
        await skills.finalize_references(state.session_id, snapshot)
        assert (
            await skills.get_snapshot(state.session_id, SkillPhase.SCENARIO)
        ).skills == snapshot.skills
        report = await planned_service.selection_report(state.session_id)
        assert (
            report["plan"]["skills"][0]["reference_reasons"]["example"]
            == "matches the learning goal"
        )
        assert report["phases"]["scenario"][0]["reference_mode"] == "used"
        await planned_service.reset(state.session_id)
        assert await skills.get_plan(state.session_id) is None
        assert await skills.snapshot_manifest(state.session_id) == {}

        await skills.set_status(skill_id, SkillStatus.DISABLED)
        assert (await skills.publish_definitions([(metadata, version)]))[0][1] is False
        async with repository.session_factory() as session:
            record = await session.get(SkillRecord, skill_id)
            assert record.status == "disabled"

        # A later error must roll back earlier inserts from the same batch.
        other = SkillCreate(name=f"a-{uuid4().hex}", description="rollback test")
        async with repository.session_factory.begin() as session:
            record = await session.get(SkillRecord, skill_id)
            record.current_version = 999
        with pytest.raises(ValueError, match="Missing current version"):
            await skills.publish_definitions([(other, version), (metadata, version)])
        async with repository.session_factory() as session:
            assert (
                await session.scalar(select(SkillRecord).where(SkillRecord.name == other.name))
                is None
            )
    finally:
        async with repository.session_factory.begin() as session:
            await session.execute(
                delete(AISessionRecord).where(AISessionRecord.session_id == UUID(state.session_id))
            )
            if skill_id is not None:
                await session.execute(
                    delete(SkillVersionRecord).where(SkillVersionRecord.skill_id == skill_id)
                )
                await session.execute(delete(SkillRecord).where(SkillRecord.skill_id == skill_id))
        await repository.close()
