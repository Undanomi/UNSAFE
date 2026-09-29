from __future__ import annotations

import asyncio
import os
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, select, text

from ai_server.config import Settings
from ai_server.database import (
    AISessionRecord,
    ScenarioRecord,
    ScenarioVersionRecord,
    SkillRecord,
    SkillVersionRecord,
)
from ai_server.main import create_app
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
from ai_server.repository import ActiveSessionLimitError, SessionRepository
from ai_server.skills.models import (
    AppliedSkill,
    SkillCreate,
    SkillPhase,
    SkillSelectors,
    SkillVersionCreate,
)
from ai_server.skills.repository import SkillRepository


@pytest.mark.asyncio
async def test_postgres_migration_and_session_round_trip() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")
    repository = SessionRepository(database_url)
    await repository.initialize()
    state = await repository.create("integration-user")
    skill_id = None
    try:
        loaded = await repository.get(state.session_id)
        assert loaded.session_id == state.session_id
        assert loaded.owner_user_id == "integration-user"
        assert loaded.status == state.status
        await repository.increment_ai_token_usage(state.session_id, 100, 25, 130)
        await repository.increment_ai_token_usage(state.session_id, 50, 10, 62)
        async with repository.session_factory() as session:
            usage = (
                await session.execute(
                    select(
                        AISessionRecord.ai_input_tokens,
                        AISessionRecord.ai_output_tokens,
                        AISessionRecord.ai_total_tokens,
                    ).where(AISessionRecord.session_id == UUID(state.session_id))
                )
            ).one()
        assert usage == (150, 35, 192)
        loaded.machine_information = MachineInformation(
            name="Postgres Test",
            visibility="private",
            theme="database persistence",
            difficulty="Easy",
        )
        loaded.scenario = ScenarioDraft(
            scenario_id="scenario-postgres-test",
            title="Postgres Test",
            scenario_description="Investigate the database training machine.",
            definition="# persisted scenario",
            target_os="Debian 13.7.0",
            tags=["PostgreSQL", "永続化"],
            user_flag="flag{user_postgres_test}",
            system_flag="flag{system_postgres_test}",
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
        assert (
            persisted.scenario.scenario_description == "Investigate the database training machine."
        )
        assert persisted.scenario.definition == "# persisted scenario"
        assert persisted.scenario.target_os == "Debian 13.7.0"
        assert persisted.scenario.tags == ["PostgreSQL", "永続化"]
        assert persisted.scenario.user_flag == "flag{user_postgres_test}"
        assert persisted.scenario.system_flag == "flag{system_postgres_test}"
        assert persisted.scenario.attack_graph.steps[0].vulnerable_version == "1.0"

        persisted.source_path = "/tmp/generated/source"
        persisted.source_checksum = "a" * 64
        persisted.scenario_generation_attempts = 2
        persisted.scenario_generation_attempt_limit = 5
        persisted.source_generation_attempts = 4
        persisted.source_generation_attempt_limit = 12
        persisted.build_id = "a49f148e-1f8c-4703-97bb-d0aa180682ae"
        persisted.build_status = "completed"
        persisted.build_progress = 100
        persisted.build_repair_attempts = 2
        persisted.build_repair_attempt_limit = 5
        persisted.repair_failure_report = {
            "kind": "scenario_sync_review",
            "status": "fail",
            "error_message": "scenario and source differ",
        }
        persisted.machine_access = MachineAccess(
            username="provisioner", password="generated-password"
        )
        persisted.artifact = Artifact(
            artifact_id="3a3c16bd-6d41-49e1-98c3-927138f8a271",
            artifact_type="zip",
            file_name="3a3c16bd-6d41-49e1-98c3-927138f8a271.zip",
            file_size=4,
            checksum="checksum",
        )
        await repository.save(persisted)
        completed = await repository.get(state.session_id)
        assert completed.source_checksum == "a" * 64
        assert completed.scenario_generation_attempts == 2
        assert completed.scenario_generation_attempt_limit == 5
        assert completed.source_generation_attempts == 4
        assert completed.source_generation_attempt_limit == 12
        assert completed.build_repair_attempts == 2
        assert completed.build_repair_attempt_limit == 5
        assert completed.repair_failure_report == {
            "kind": "scenario_sync_review",
            "status": "fail",
            "error_message": "scenario and source differ",
        }
        assert completed.machine_access == MachineAccess(
            username="provisioner", password="generated-password"
        )
        assert completed.artifact is not None
        assert completed.artifact.file_name == "3a3c16bd-6d41-49e1-98c3-927138f8a271.zip"
        async with repository.session_factory() as session:
            generation_jobs = await session.scalar(
                text("SELECT to_regclass('public.generation_jobs')")
            )
        assert generation_jobs is None

        skill_repository = SkillRepository(repository.session_factory)
        skill_id = await skill_repository.create_skill(
            SkillCreate(
                name="postgres-integration-skill",
                description="Skill repository integration test",
            )
        )
        published = await skill_repository.publish_version(
            skill_id,
            SkillVersionCreate(
                instructions="Apply PostgreSQL-specific test guidance.",
                phases=[SkillPhase.SOURCE],
                selectors=SkillSelectors(themes=["database"]),
                created_by="integration-user",
            ),
        )
        active = await skill_repository.active_versions(limit=10)
        assert [skill.name for skill in active if skill.skill_id == skill_id] == [
            "postgres-integration-skill"
        ]
        snapshot = await skill_repository.create_snapshot(
            state.session_id,
            SkillPhase.SOURCE,
            [AppliedSkill(**published.model_dump(), selection_reason="theme:database")],
        )
        assert snapshot.skills[0].version == 1
        assert await skill_repository.get_snapshot(state.session_id, SkillPhase.SOURCE) == snapshot
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
            if skill_id is not None:
                await session.execute(
                    delete(SkillVersionRecord).where(SkillVersionRecord.skill_id == skill_id)
                )
                await session.execute(delete(SkillRecord).where(SkillRecord.skill_id == skill_id))
        await repository.close()


@pytest.mark.asyncio
async def test_user_active_session_limit_is_atomic_across_repositories() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")
    first_repository = SessionRepository(database_url, max_active_sessions_per_user=1)
    second_repository = SessionRepository(database_url, max_active_sessions_per_user=1)
    await first_repository.initialize()
    owner = f"limit-test-{uuid4()}"
    created_ids: list[UUID] = []
    try:
        first, second = await asyncio.gather(
            first_repository.create(owner),
            second_repository.create(owner),
        )
        created_ids.extend((UUID(first.session_id), UUID(second.session_id)))
        assert first.status == second.status == SessionStatus.CREATED

        first.status = second.status = SessionStatus.READY
        results = await asyncio.gather(
            first_repository.save(first),
            second_repository.save(second),
            return_exceptions=True,
        )
        successes = [item for item in results if not isinstance(item, BaseException)]
        failures = [item for item in results if isinstance(item, BaseException)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], ActiveSessionLimitError)
        winner = successes[0]
        loser = second if winner.session_id == first.session_id else first
        winner_repository = (
            first_repository if winner.session_id == first.session_id else second_repository
        )
        loser_repository = (
            second_repository if winner.session_id == first.session_id else first_repository
        )
        assert failures[0].active_session_ids == [winner.session_id]
        assert (await loser_repository.get(loser.session_id)).status == SessionStatus.CREATED

        winner.status = SessionStatus.SCENARIO_READY
        await winner_repository.save(winner)
        with pytest.raises(ActiveSessionLimitError):
            await loser_repository.save(loser)

        winner.status = SessionStatus.FAILED
        await winner_repository.save(winner)
        await loser_repository.save(loser)
        winner.status = SessionStatus.READY
        with pytest.raises(ActiveSessionLimitError):
            await winner_repository.save(winner)
        assert (await winner_repository.get(winner.session_id)).status == SessionStatus.FAILED

        loser.status = SessionStatus.CANCELLED
        await loser_repository.save(loser)
        await winner_repository.save(winner)
        assert (await winner_repository.get(winner.session_id)).status == SessionStatus.READY
    finally:
        async with first_repository.session_factory.begin() as session:
            if created_ids:
                await session.execute(
                    delete(AISessionRecord).where(AISessionRecord.session_id.in_(created_ids))
                )
        await first_repository.close()
        await second_repository.close()


@pytest.mark.asyncio
async def test_machine_information_api_reports_limit_and_releases_on_cancel(tmp_path) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")
    repository = SessionRepository(database_url)
    app = create_app(
        Settings(
            ai_provider="stub",
            database_url=database_url,
            source_root=tmp_path,
            max_active_sessions_per_user=2,
        ),
        repository_override=repository,
    )
    headers = {"X-Authenticated-User-ID": f"api-limit-test-{uuid4()}"}
    created_ids: list[UUID] = []
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            first = await client.post("/v1/sessions", headers=headers)
            second = await client.post("/v1/sessions", headers=headers)
            third = await client.post("/v1/sessions", headers=headers)
            assert [response.status_code for response in (first, second, third)] == [201] * 3
            session_ids = [response.json()["session_id"] for response in (first, second, third)]
            created_ids.extend(UUID(session_id) for session_id in session_ids)
            machine_information = {
                "name": "Limit test",
                "visibility": "private",
                "theme": "concurrency",
                "difficulty": "Easy",
            }
            for session_id in session_ids[:2]:
                admitted = await client.put(
                    f"/v1/sessions/{session_id}/machine-information",
                    headers=headers,
                    json=machine_information,
                )
                assert admitted.status_code == 200
                assert admitted.json()["status"] == "ready"
            blocked = await client.put(
                f"/v1/sessions/{session_ids[2]}/machine-information",
                headers=headers,
                json=machine_information,
            )
            assert blocked.status_code == 409
            assert "at most 2 active sessions" in blocked.json()["detail"]
            assert blocked.json()["code"] == "active_session_limit"
            assert blocked.json()["limit"] == 2
            assert set(blocked.json()["active_session_ids"]) == set(session_ids[:2])
            assert (await repository.get(session_ids[2])).status == SessionStatus.CREATED
            cancelled = await client.post(f"/v1/sessions/{session_ids[0]}/cancel", headers=headers)
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "cancelled"
            admitted = await client.put(
                f"/v1/sessions/{session_ids[2]}/machine-information",
                headers=headers,
                json=machine_information,
            )
            assert admitted.status_code == 200
            assert admitted.json()["status"] == "ready"

    finally:
        async with repository.session_factory.begin() as session:
            if created_ids:
                await session.execute(
                    delete(AISessionRecord).where(AISessionRecord.session_id.in_(created_ids))
                )
        await repository.close()
