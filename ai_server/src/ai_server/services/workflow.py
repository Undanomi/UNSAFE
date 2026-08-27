from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..models import GeneratedSource, SessionState, SessionStatus
from ..repository import SessionRepository
from .ai import AIGenerator
from .build_client import BuildClient
from .errors import exception_detail
from .source_archive import InvalidSourceError, SourceArchive
from .source_repair import apply_source_patch

logger = logging.getLogger(__name__)


class InvalidSessionStateError(ValueError):
    pass


class MachineWorkflow:
    def __init__(
        self,
        repository: SessionRepository,
        generator: AIGenerator,
        source_archive: SourceArchive,
        build_client: BuildClient,
        source_generation_attempts: int,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.source_archive = source_archive
        self.build_client = build_client
        self.source_generation_attempts = source_generation_attempts
        self.tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self, session_id: str, scenario_id: str | None = None) -> SessionState:
        state = await self.repository.get(session_id)
        if not state.machine_information or not state.scenario:
            raise InvalidSessionStateError(
                "a generated scenario is required before machine creation"
            )
        if scenario_id and scenario_id != state.scenario.scenario_id:
            raise InvalidSessionStateError("scenario_id does not belong to this session")
        if session_id in self.tasks:
            return state
        if state.build_id and state.build_status not in {"failed", "cancelled"}:
            return state
        repair_source = None
        repair_report = None
        if state.build_id:
            repair_source = self.source_archive.load(state.source_path or "")
            repair_report = {
                "kind": "packer_build",
                "status": state.build_status,
                "error_message": state.error_message or "build failed without details",
            }
            state.build_progress = 0
            state.artifact = None
        state.status = SessionStatus.GENERATING_CODE
        await self.repository.save(state)
        task = asyncio.create_task(
            self._generate_and_submit(session_id, repair_source, repair_report)
        )
        self.tasks[session_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(session_id, None))
        return state

    async def _generate_and_submit(
        self,
        session_id: str,
        generated: GeneratedSource | None = None,
        failure_report: dict | None = None,
    ) -> None:
        try:
            state = await self.repository.get(session_id)
            assert state.machine_information is not None and state.scenario is not None
            archive_path = self._existing_archive(state) if failure_report is None else None
            checksum = state.source_checksum
            last_validation_error: Exception | None = None
            repair_history: list[dict] = []
            if archive_path is None and generated is None:
                generated = await self.generator.generate_source(
                    state.machine_information, state.scenario
                )
            for attempt in range(
                1, self.source_generation_attempts + 1 if archive_path is None else 1
            ):
                assert generated is not None
                if failure_report is not None:
                    patch = await self.generator.repair_source(
                        state.machine_information,
                        state.scenario,
                        generated,
                        failure_report,
                    )
                    generated = apply_source_patch(generated, patch)
                    repair_history.append(
                        {
                            "attempt": len(repair_history) + 1,
                            "trigger": failure_report,
                            "changed_files": sorted(file.path for file in patch.files),
                            "deleted_files": sorted(patch.delete_paths),
                        }
                    )
                try:
                    archive_path, checksum = self.source_archive.create(
                        session_id, state.scenario, generated, repair_history
                    )
                    break
                except InvalidSourceError as error:
                    last_validation_error = error
                    failure_report = error.report
            if archive_path is None or checksum is None:
                raise RuntimeError(
                    f"source validation failed after retries: {last_validation_error}"
                )
            state.source_path = str(archive_path.parent / "source")
            state.source_checksum = checksum
            state.build_id = None
            state.build_status = None
            state.build_progress = 0
            state.error_message = None
            await self.repository.save(state)
            build = await self.build_client.submit(
                scenario_id=state.scenario.scenario_id,
                scenario_version_id=state.scenario.scenario_version_id,
                requested_by=state.owner_user_id,
                idempotency_key=f"ai-session-{session_id}-{checksum[:16]}",
                archive_path=archive_path,
            )
            state.build_id = build["build_id"]
            state.build_status = build["status"]
            state.build_progress = build.get("progress", 0)
            state.status = SessionStatus.BUILD_QUEUED
            await self.repository.save(state)
        except Exception as error:
            detail = exception_detail(error)
            logger.exception("machine workflow failed", extra={"session_id": session_id})
            state = await self.repository.get(session_id)
            state.status = SessionStatus.FAILED
            state.error_message = detail
            await self.repository.save(state)

    @staticmethod
    def _existing_archive(state: SessionState) -> Path | None:
        if not state.source_path or not state.source_checksum:
            return None
        archive_path = Path(state.source_path).parent / "source.zip"
        return archive_path if archive_path.is_file() else None

    async def synchronize(self, state: SessionState) -> SessionState:
        if (
            not state.build_id
            or state.status == SessionStatus.FAILED
            or state.session_id in self.tasks
        ):
            return state
        build = await self.build_client.get(state.build_id)
        state.build_status = build["status"]
        state.build_progress = build.get("progress", state.build_progress)
        if build["status"] == "completed":
            artifacts = await self.build_client.artifacts(state.build_id)
            if not artifacts:
                raise RuntimeError("build completed without an artifact")
            state.artifact = next(
                (item for item in artifacts if item.artifact_type == "qcow2"), artifacts[0]
            )
            state.status = SessionStatus.COMPLETED
        elif build["status"] in {"failed", "cancelled"}:
            state.status = SessionStatus.FAILED
            state.error_message = build.get("error_message") or f"build {build['status']}"
        elif build["status"] in {"building", "uploading"}:
            state.status = SessionStatus.BUILDING
        else:
            state.status = SessionStatus.BUILD_QUEUED
        return await self.repository.save(state)
