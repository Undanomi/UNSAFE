from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import asyncpg

from .models import (
    Artifact,
    CVEInstallationPlan,
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
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self.pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.database_url, min_size=self.min_size, max_size=self.max_size
            )
        migration = Path(__file__).with_name("migrations").joinpath("001_init.sql").read_text()
        async with self.pool.acquire() as connection:
            await connection.execute(migration)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def ping(self) -> None:
        assert self.pool is not None
        await self.pool.fetchval("SELECT 1")

    async def create(self, owner_user_id: str) -> SessionState:
        assert self.pool is not None
        state = SessionState(session_id=str(uuid4()), owner_user_id=owner_user_id)
        await self.pool.execute(
            """INSERT INTO ai_sessions
               (session_id, owner_user_id, status, created_at, updated_at)
               VALUES ($1::uuid, $2, $3, $4, $4)""",
            state.session_id,
            state.owner_user_id,
            state.status.value,
            state.created_at,
        )
        return state

    async def get(self, session_id: str) -> SessionState:
        assert self.pool is not None
        row = await self.pool.fetchrow(
            """SELECT s.*, sc.title, sv.scenario_definition, sv.target_os,
                      sv.initial_cve, sv.privilege_escalation_cve, sv.cve_installation
               FROM ai_sessions s
               LEFT JOIN scenarios sc ON sc.scenario_id = s.scenario_id
               LEFT JOIN scenario_versions sv
                 ON sv.scenario_id = s.scenario_id
                AND sv.scenario_version_id = s.scenario_version_id
               WHERE s.session_id = $1::uuid""",
            session_id,
        )
        if row is None:
            raise SessionNotFoundError(session_id)
        scenario = None
        if row["scenario_id"]:
            scenario = ScenarioDraft(
                scenario_id=row["scenario_id"],
                scenario_version_id=row["scenario_version_id"],
                title=row["title"],
                definition=row["scenario_definition"],
                target_os=row["target_os"],
                initial_cve=row["initial_cve"],
                privilege_escalation_cve=row["privilege_escalation_cve"],
                cve_installation=self._cve_plans(row["cve_installation"]),
            )
        return SessionState(
            session_id=str(row["session_id"]),
            owner_user_id=row["owner_user_id"],
            status=SessionStatus(row["status"]),
            machine_information=self._json_model(row["machine_information"], MachineInformation),
            scenario=scenario,
            source_path=row["generated_code_path"],
            source_checksum=row["generated_code_checksum"],
            build_id=str(row["build_id"]) if row["build_id"] else None,
            build_status=row["build_status"],
            build_progress=row["build_progress"],
            artifact=self._json_model(row["artifact"], Artifact),
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def save(self, state: SessionState) -> SessionState:
        assert self.pool is not None
        state.updated_at = utcnow()
        async with self.pool.acquire() as connection, connection.transaction():
            if state.scenario:
                await self._save_scenario(connection, state)
            result = await connection.execute(
                """UPDATE ai_sessions SET
                     status=$2, machine_information=$3::jsonb,
                     scenario_id=$4, scenario_version_id=$5,
                     generated_code_path=$6, generated_code_checksum=$7,
                     build_id=$8::uuid, build_status=$9, build_progress=$10,
                     artifact=$11::jsonb, error_message=$12, updated_at=$13
                   WHERE session_id=$1::uuid""",
                state.session_id,
                state.status.value,
                state.machine_information.model_dump_json() if state.machine_information else None,
                state.scenario.scenario_id if state.scenario else None,
                state.scenario.scenario_version_id if state.scenario else None,
                state.source_path,
                state.source_checksum,
                state.build_id,
                state.build_status,
                state.build_progress,
                state.artifact.model_dump_json() if state.artifact else None,
                state.error_message,
                state.updated_at,
            )
        if result == "UPDATE 0":
            raise SessionNotFoundError(state.session_id)
        return state

    async def _save_scenario(self, connection: asyncpg.Connection, state: SessionState) -> None:
        assert state.scenario and state.machine_information
        await connection.execute(
            """INSERT INTO scenarios
                 (scenario_id, owner_user_id, title, description, difficulty, status,
                  current_version, created_at, updated_at)
               VALUES ($1,$2,$3,$4,$5,'draft',1,$6,$6)
               ON CONFLICT (scenario_id) DO UPDATE SET title=EXCLUDED.title,
                 description=EXCLUDED.description, difficulty=EXCLUDED.difficulty,
                 updated_at=EXCLUDED.updated_at""",
            state.scenario.scenario_id,
            state.owner_user_id,
            state.scenario.title,
            state.machine_information.theme,
            state.machine_information.difficulty,
            state.updated_at,
        )
        await connection.execute(
            """INSERT INTO scenario_versions
                 (scenario_version_id, scenario_id, version, scenario_definition,
                  target_os, initial_cve, privilege_escalation_cve, cve_installation,
                  generated_code_path, generated_code_checksum, created_by, created_at)
               VALUES ($1,$2,1,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11)
               ON CONFLICT (scenario_id, scenario_version_id) DO UPDATE SET
                 scenario_definition=EXCLUDED.scenario_definition,
                 target_os=EXCLUDED.target_os,
                 initial_cve=EXCLUDED.initial_cve,
                 privilege_escalation_cve=EXCLUDED.privilege_escalation_cve,
                 cve_installation=EXCLUDED.cve_installation,
                 generated_code_path=EXCLUDED.generated_code_path,
                 generated_code_checksum=EXCLUDED.generated_code_checksum""",
            state.scenario.scenario_version_id,
            state.scenario.scenario_id,
            state.scenario.definition,
            state.scenario.target_os,
            state.scenario.initial_cve,
            state.scenario.privilege_escalation_cve,
            json.dumps([item.model_dump(mode="json") for item in state.scenario.cve_installation]),
            state.source_path,
            state.source_checksum,
            state.owner_user_id,
            state.updated_at,
        )

    @staticmethod
    def _json_model(value, model_type):
        if value is None:
            return None
        if isinstance(value, str):
            return model_type.model_validate_json(value)
        return model_type.model_validate(value)

    @staticmethod
    def _cve_plans(value) -> list[CVEInstallationPlan]:
        if not value:
            return []
        items = json.loads(value) if isinstance(value, str) else value
        return [CVEInstallationPlan.model_validate(item) for item in items]
