from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import delete, text

from ai_server.database import AISessionRecord, ScenarioRecord, ScenarioVersionRecord
from ai_server.models import (
    Artifact,
    AttackGraph,
    AttackObjective,
    AttackStep,
    MachineAccess,
    MachineInformation,
    ScenarioDraft,
    SessionStatus,
)
from ai_server.repository import SessionRepository


@pytest.mark.asyncio
async def test_postgres_migration_and_session_round_trip() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")
    repository = SessionRepository(database_url)
    await repository.initialize()
    state = await repository.create("integration-user")
    try:
        loaded = await repository.get(state.session_id)
        assert loaded.session_id == state.session_id
        assert loaded.owner_user_id == "integration-user"
        assert loaded.status == state.status
        loaded.machine_information = MachineInformation(
            name="Postgres Test",
            visibility="private",
            theme="database persistence",
            difficulty="Easy",
        )
        loaded.scenario = ScenarioDraft(
            scenario_id="scenario-postgres-test",
            title="Postgres Test",
            definition="# persisted scenario",
            target_os="Ubuntu 24.04",
            attack_graph=AttackGraph(
                objectives=[
                    AttackObjective(
                        objective_id="user-flag",
                        objective_type="user_flag",
                        description="read the user flag",
                    )
                ],
                steps=[
                    AttackStep(
                        step_id="web-entry",
                        title="Web entry",
                        kind="cve",
                        phase="initial_access",
                        description="exploit the training service",
                        achieves=["user-flag"],
                        implementation_steps=["install test-service=1.0"],
                        installation_method="apt snapshot",
                        references=[],
                        os_compatible=True,
                        compatibility_reason="test evidence",
                        cve_id="CVE-2024-0001",
                        software="test-service",
                        vulnerable_version="1.0",
                    )
                ],
            ),
        )
        loaded.status = SessionStatus.SCENARIO_READY
        await repository.save(loaded)
        persisted = await repository.get(state.session_id)
        assert persisted.scenario is not None
        assert persisted.scenario.definition == "# persisted scenario"
        assert persisted.scenario.target_os == "Ubuntu 24.04"
        assert persisted.scenario.attack_graph.steps[0].vulnerable_version == "1.0"

        persisted.source_path = "/tmp/generated/source"
        persisted.source_checksum = "a" * 64
        persisted.build_id = "a49f148e-1f8c-4703-97bb-d0aa180682ae"
        persisted.build_status = "completed"
        persisted.build_progress = 100
        persisted.build_repair_attempts = 2
        persisted.build_repair_attempt_limit = 5
        persisted.machine_access = MachineAccess(username="ubuntu", password="generated-password")
        persisted.artifact = Artifact(
            artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
            artifact_type="tar.zst",
            file_name="slsg-machine.tar.zst",
            file_size=4,
            checksum="checksum",
        )
        await repository.save(persisted)
        completed = await repository.get(state.session_id)
        assert completed.source_checksum == "a" * 64
        assert completed.build_repair_attempts == 2
        assert completed.build_repair_attempt_limit == 5
        assert completed.machine_access == MachineAccess(
            username="ubuntu", password="generated-password"
        )
        assert completed.artifact is not None
        assert completed.artifact.file_name == "slsg-machine.tar.zst"
        async with repository.session_factory() as session:
            generation_jobs = await session.scalar(
                text("SELECT to_regclass('public.generation_jobs')")
            )
        assert generation_jobs is None
    finally:
        async with repository.session_factory.begin() as session:
            await session.execute(
                delete(AISessionRecord).where(AISessionRecord.session_id == UUID(state.session_id))
            )
            await session.execute(
                delete(ScenarioVersionRecord).where(
                    ScenarioVersionRecord.scenario_id == "scenario-postgres-test"
                )
            )
            await session.execute(
                delete(ScenarioRecord).where(ScenarioRecord.scenario_id == "scenario-postgres-test")
            )
        await repository.close()
