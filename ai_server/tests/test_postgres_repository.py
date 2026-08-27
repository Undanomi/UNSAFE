from __future__ import annotations

import os

import pytest

from ai_server.models import (
    Artifact,
    CVEInstallationPlan,
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
            cve_installation=[
                CVEInstallationPlan(
                    cve_id="CVE-2024-0001",
                    role="initial_access",
                    software="test-service",
                    vulnerable_version="1.0",
                    os_compatible=True,
                    compatibility_reason="test evidence",
                    installation_method="apt snapshot",
                    installation_steps=["install test-service=1.0"],
                )
            ],
        )
        loaded.status = SessionStatus.SCENARIO_READY
        await repository.save(loaded)
        persisted = await repository.get(state.session_id)
        assert persisted.scenario is not None
        assert persisted.scenario.definition == "# persisted scenario"
        assert persisted.scenario.target_os == "Ubuntu 24.04"
        assert persisted.scenario.cve_installation[0].vulnerable_version == "1.0"

        persisted.source_path = "/tmp/generated/source"
        persisted.source_checksum = "a" * 64
        persisted.build_id = "a49f148e-1f8c-4703-97bb-d0aa180682ae"
        persisted.build_status = "completed"
        persisted.build_progress = 100
        persisted.artifact = Artifact(
            artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
            artifact_type="qcow2",
            file_name="image.qcow2",
            file_size=4,
            checksum="checksum",
        )
        await repository.save(persisted)
        completed = await repository.get(state.session_id)
        assert completed.source_checksum == "a" * 64
        assert completed.artifact is not None
        assert completed.artifact.file_name == "image.qcow2"
    finally:
        assert repository.pool is not None
        await repository.pool.execute(
            "DELETE FROM ai_sessions WHERE session_id=$1::uuid", state.session_id
        )
        await repository.pool.execute(
            "DELETE FROM scenario_versions WHERE scenario_id='scenario-postgres-test'"
        )
        await repository.pool.execute(
            "DELETE FROM scenarios WHERE scenario_id='scenario-postgres-test'"
        )
        await repository.close()
