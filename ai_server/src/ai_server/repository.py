from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import and_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .database import (
    AISessionRecord,
    ScenarioRecord,
    ScenarioVersionRecord,
    create_database_engine,
    create_session_factory,
)
from .models import (
    Artifact,
    AttackGraph,
    MachineAccess,
    MachineInformation,
    ScenarioDraft,
    SessionState,
    SessionStatus,
    utcnow,
)


class SessionNotFoundError(Exception):
    pass


class SessionRepository:
    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 10) -> None:
        self.engine: AsyncEngine = create_database_engine(database_url, min_size, max_size)
        self.session_factory: async_sessionmaker = create_session_factory(self.engine)

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(text("SELECT pg_advisory_xact_lock(739247151)"))
            await connection.exec_driver_sql(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version varchar(128) PRIMARY KEY,
                    applied_at timestamptz NOT NULL
                )"""
            )
            applied = set(
                (await connection.execute(text("SELECT version FROM schema_migrations"))).scalars()
            )
            migration_root = Path(__file__).with_name("migrations")
            for migration_path in sorted(migration_root.glob("[0-9][0-9][0-9]_*.sql")):
                version = migration_path.stem
                if version in applied:
                    continue
                for statement in (
                    item.strip() for item in migration_path.read_text(encoding="utf-8").split(";")
                ):
                    if statement:
                        await connection.exec_driver_sql(statement)
                await connection.execute(
                    text(
                        "INSERT INTO schema_migrations (version, applied_at) "
                        "VALUES (:version, now())"
                    ),
                    {"version": version},
                )

    async def close(self) -> None:
        await self.engine.dispose()

    async def ping(self) -> None:
        async with self.session_factory() as session:
            await session.execute(text("SELECT 1"))

    async def create(self, owner_user_id: str) -> SessionState:
        state = SessionState(session_id=str(uuid4()), owner_user_id=owner_user_id)
        record = AISessionRecord(
            session_id=UUID(state.session_id),
            owner_user_id=state.owner_user_id,
            status=state.status.value,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )
        async with self.session_factory.begin() as session:
            session.add(record)
        return state

    async def get(self, session_id: str) -> SessionState:
        try:
            parsed_session_id = UUID(session_id)
        except ValueError as error:
            raise SessionNotFoundError(session_id) from error
        statement = (
            select(
                AISessionRecord,
                ScenarioRecord.title,
                ScenarioRecord.description,
                ScenarioVersionRecord.scenario_definition,
                ScenarioVersionRecord.target_os,
                ScenarioVersionRecord.attack_graph,
                ScenarioVersionRecord.user_flag,
                ScenarioVersionRecord.system_flag,
            )
            .outerjoin(ScenarioRecord, ScenarioRecord.scenario_id == AISessionRecord.scenario_id)
            .outerjoin(
                ScenarioVersionRecord,
                and_(
                    ScenarioVersionRecord.scenario_id == AISessionRecord.scenario_id,
                    ScenarioVersionRecord.scenario_version_id
                    == AISessionRecord.scenario_version_id,
                ),
            )
            .where(AISessionRecord.session_id == parsed_session_id)
        )
        async with self.session_factory() as session:
            row = (await session.execute(statement)).one_or_none()
        if row is None:
            raise SessionNotFoundError(session_id)
        record = row[0]
        scenario = None
        if record.scenario_id:
            scenario = ScenarioDraft(
                scenario_id=record.scenario_id,
                scenario_version_id=record.scenario_version_id or "v1",
                title=row[1],
                scenario_description=row[2],
                definition=row[3],
                target_os=row[4],
                attack_graph=AttackGraph.model_validate(row[5]),
                user_flag=row[6],
                system_flag=row[7],
            )
        return SessionState(
            session_id=str(record.session_id),
            owner_user_id=record.owner_user_id,
            status=SessionStatus(record.status),
            machine_information=self._json_model(record.machine_information, MachineInformation),
            scenario=scenario,
            source_path=record.generated_code_path,
            source_checksum=record.generated_code_checksum,
            build_id=str(record.build_id) if record.build_id else None,
            build_status=record.build_status,
            build_progress=record.build_progress,
            build_repair_attempts=record.build_repair_attempts,
            build_repair_attempt_limit=record.build_repair_attempt_limit,
            machine_access=self._json_model(record.machine_access, MachineAccess),
            artifact=self._json_model(record.artifact, Artifact),
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def save(self, state: SessionState) -> SessionState:
        try:
            session_id = UUID(state.session_id)
            build_id = UUID(state.build_id) if state.build_id else None
        except ValueError as error:
            raise SessionNotFoundError(state.session_id) from error
        state.updated_at = utcnow()
        async with self.session_factory.begin() as session:
            if state.scenario:
                await self._save_scenario(session, state)
            result = await session.execute(
                update(AISessionRecord)
                .where(AISessionRecord.session_id == session_id)
                .values(
                    status=state.status.value,
                    machine_information=(
                        state.machine_information.model_dump(mode="json")
                        if state.machine_information
                        else None
                    ),
                    scenario_id=state.scenario.scenario_id if state.scenario else None,
                    scenario_version_id=(
                        state.scenario.scenario_version_id if state.scenario else None
                    ),
                    generated_code_path=state.source_path,
                    generated_code_checksum=state.source_checksum,
                    build_id=build_id,
                    build_status=state.build_status,
                    build_progress=state.build_progress,
                    build_repair_attempts=state.build_repair_attempts,
                    build_repair_attempt_limit=state.build_repair_attempt_limit,
                    machine_access=(
                        state.machine_access.model_dump(mode="json")
                        if state.machine_access
                        else None
                    ),
                    artifact=state.artifact.model_dump(mode="json") if state.artifact else None,
                    error_message=state.error_message,
                    updated_at=state.updated_at,
                )
            )
            if result.rowcount == 0:
                raise SessionNotFoundError(state.session_id)
        return state

    @staticmethod
    async def _save_scenario(session: AsyncSession, state: SessionState) -> None:
        assert state.scenario and state.machine_information
        scenario_insert = insert(ScenarioRecord).values(
            scenario_id=state.scenario.scenario_id,
            owner_user_id=state.owner_user_id,
            title=state.scenario.title,
            description=state.scenario.scenario_description,
            difficulty=state.machine_information.difficulty,
            status="draft",
            current_version=1,
            created_at=state.updated_at,
            updated_at=state.updated_at,
        )
        await session.execute(
            scenario_insert.on_conflict_do_update(
                index_elements=[ScenarioRecord.scenario_id],
                set_={
                    "title": scenario_insert.excluded.title,
                    "description": scenario_insert.excluded.description,
                    "difficulty": scenario_insert.excluded.difficulty,
                    "updated_at": scenario_insert.excluded.updated_at,
                },
            )
        )
        version_insert = insert(ScenarioVersionRecord).values(
            scenario_version_id=state.scenario.scenario_version_id,
            scenario_id=state.scenario.scenario_id,
            version=1,
            scenario_definition=state.scenario.definition,
            target_os=state.scenario.target_os,
            attack_graph=state.scenario.attack_graph.model_dump(mode="json"),
            user_flag=state.scenario.user_flag,
            system_flag=state.scenario.system_flag,
            generated_code_path=state.source_path,
            generated_code_checksum=state.source_checksum,
            created_by=state.owner_user_id,
            created_at=state.updated_at,
        )
        await session.execute(
            version_insert.on_conflict_do_update(
                index_elements=[
                    ScenarioVersionRecord.scenario_id,
                    ScenarioVersionRecord.scenario_version_id,
                ],
                set_={
                    "scenario_definition": version_insert.excluded.scenario_definition,
                    "target_os": version_insert.excluded.target_os,
                    "attack_graph": version_insert.excluded.attack_graph,
                    "user_flag": version_insert.excluded.user_flag,
                    "system_flag": version_insert.excluded.system_flag,
                    "generated_code_path": version_insert.excluded.generated_code_path,
                    "generated_code_checksum": version_insert.excluded.generated_code_checksum,
                },
            )
        )

    @staticmethod
    def _json_model(value, model_type):
        if value is None:
            return None
        return model_type.model_validate(value)
