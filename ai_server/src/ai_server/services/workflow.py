from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..models import GeneratedSource, MachineAccess, SessionState, SessionStatus
from ..repository import SessionRepository
from .ai import AIGenerator
from .build_client import BuildClient
from .errors import exception_detail
from .source_archive import InvalidSourceError, SourceArchive
from .source_repair import apply_source_patch
from .source_validation import known_failed_resources

logger = logging.getLogger(__name__)
BUILD_POLL_INTERVAL_SECONDS = 5


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
        build_repair_max_attempts: int,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.source_archive = source_archive
        self.build_client = build_client
        self.source_generation_attempts = source_generation_attempts
        self.build_repair_max_attempts = build_repair_max_attempts
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
        if state.build_id:
            if state.build_status not in {"failed", "cancelled"}:
                return state
            if state.build_repair_attempts >= self.build_repair_max_attempts:
                state.build_repair_attempts = 0
            return await self._start_build_repair(state)
        state.status = SessionStatus.GENERATING_CODE
        await self.repository.save(state)
        self._create_task(session_id)
        return state

    async def _start_build_repair(self, state: SessionState) -> SessionState:
        prepared = await self._prepare_build_repair(state)
        if prepared is not None:
            repair_source, repair_report, repair_history = prepared
            self._create_task(state.session_id, repair_source, repair_report, repair_history)
        return state

    async def _prepare_build_repair(
        self, state: SessionState
    ) -> tuple[GeneratedSource, dict, list[dict]] | None:
        if state.build_repair_attempts >= self.build_repair_max_attempts:
            state.status = SessionStatus.FAILED
            await self.repository.save(state)
            return None
        archive_path = self._existing_archive(state)
        repair_source = (
            self.source_archive.load_archive(archive_path)
            if archive_path is not None
            else self.source_archive.load(state.source_path or "")
        )
        if repair_source is None:
            state.status = SessionStatus.FAILED
            state.error_message = (
                f"{state.error_message or 'build failed without details'}; "
                "generated source is unavailable for automatic repair"
            )
            await self.repository.save(state)
            return None
        repair_report = {
            "kind": "packer_build",
            "status": state.build_status,
            "error_message": state.error_message or "build failed without details",
        }
        if state.build_id:
            try:
                build_log = await self.build_client.packer_log(state.build_id)
            except Exception:
                logger.warning(
                    "packer log retrieval failed",
                    exc_info=True,
                    extra={"session_id": state.session_id, "build_id": state.build_id},
                )
            else:
                if build_log.strip():
                    repair_report["packer_log_tail"] = build_log
        repair_history = (
            self.source_archive.load_repair_history_from_archive(archive_path)
            if archive_path is not None
            else self.source_archive.load_repair_history(state.source_path or "")
        )
        state.build_repair_attempts += 1
        state.build_progress = 0
        state.machine_access = None
        state.artifact = None
        state.status = SessionStatus.GENERATING_CODE
        await self.repository.save(state)
        return repair_source, repair_report, repair_history

    def _create_task(
        self,
        session_id: str,
        generated: GeneratedSource | None = None,
        failure_report: dict | None = None,
        repair_history: list[dict] | None = None,
    ) -> None:
        task = asyncio.create_task(
            self._generate_and_submit(session_id, generated, failure_report, repair_history)
        )
        self.tasks[session_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(session_id, None))

    async def _generate_and_submit(
        self,
        session_id: str,
        generated: GeneratedSource | None = None,
        failure_report: dict | None = None,
        existing_repair_history: list[dict] | None = None,
    ) -> None:
        try:
            state = await self.repository.get(session_id)
            assert state.machine_information is not None and state.scenario is not None
            archive_path = self._existing_archive(state) if failure_report is None else None
            checksum = state.source_checksum
            last_validation_error: Exception | None = None
            repair_history = list(existing_repair_history or [])
            best_validation_failures = 0 if failure_report is not None else None
            if archive_path is None and generated is None:
                generated = await self.generator.generate_source(
                    state.machine_information, state.scenario
                )
            for attempt in range(
                1, self.source_generation_attempts + 1 if archive_path is None else 1
            ):
                assert generated is not None
                retry_base = generated
                patch_applied = False
                if failure_report is not None:
                    repair_context = {
                        **failure_report,
                        "known_failed_resources": known_failed_resources(repair_history),
                        "repair_history": _compact_repair_history(repair_history),
                    }
                    patch = await self.generator.repair_source(
                        state.machine_information,
                        state.scenario,
                        generated,
                        repair_context,
                    )
                    generated = apply_source_patch(generated, patch)
                    patch_applied = True
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
                    failed_count = int(error.report.get("summary", {}).get("failed", 0))
                    if (
                        patch_applied
                        and best_validation_failures is not None
                        and failed_count >= best_validation_failures
                    ):
                        generated = retry_base
                    else:
                        best_validation_failures = failed_count
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
            state.machine_access = None
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
            await self._monitor_build(session_id)
        except Exception as error:
            detail = exception_detail(error)
            logger.exception("machine workflow failed", extra={"session_id": session_id})
            state = await self.repository.get(session_id)
            state.status = SessionStatus.FAILED
            state.error_message = detail
            await self.repository.save(state)

    async def _monitor_build(self, session_id: str) -> None:
        while True:
            state = await self.repository.get(session_id)
            if not state.build_id:
                return
            build_id = state.build_id
            try:
                build = await self.build_client.get(build_id)
            except Exception:
                logger.warning(
                    "build status polling failed",
                    exc_info=True,
                    extra={"session_id": session_id, "build_id": build_id},
                )
                await asyncio.sleep(BUILD_POLL_INTERVAL_SECONDS)
                continue

            state = await self.repository.get(session_id)
            if state.build_id != build_id:
                return
            state.build_status = build["status"]
            state.build_progress = build.get("progress", state.build_progress)
            if build["status"] == "completed":
                self._capture_machine_access(state, build)
                artifacts = await self.build_client.artifacts(build_id)
                if not artifacts:
                    raise RuntimeError("build completed without an artifact")
                state.artifact = next(
                    (item for item in artifacts if item.artifact_type == "qcow2"), artifacts[0]
                )
                state.status = SessionStatus.COMPLETED
                await self.repository.save(state)
                return
            if build["status"] in {"failed", "cancelled"}:
                state.error_message = build.get("error_message") or f"build {build['status']}"
                prepared = await self._prepare_build_repair(state)
                if prepared is None:
                    return
                repair_source, repair_report, repair_history = prepared
                await self._generate_and_submit(
                    session_id, repair_source, repair_report, repair_history
                )
                return
            state.status = (
                SessionStatus.BUILDING
                if build["status"] in {"building", "uploading"}
                else SessionStatus.BUILD_QUEUED
            )
            await self.repository.save(state)
            await asyncio.sleep(BUILD_POLL_INTERVAL_SECONDS)

    @staticmethod
    def _existing_archive(state: SessionState) -> Path | None:
        if not state.source_path or not state.source_checksum:
            return None
        archive_path = Path(state.source_path).parent / "source.zip"
        return archive_path if archive_path.is_file() else None

    async def synchronize(self, state: SessionState) -> SessionState:
        if (
            not state.build_id
            or state.session_id in self.tasks
            or (
                state.status == SessionStatus.FAILED
                and (
                    state.build_status not in {"failed", "cancelled"}
                    or state.build_repair_attempts >= self.build_repair_max_attempts
                )
            )
        ):
            return state
        build = await self.build_client.get(state.build_id)
        state.build_status = build["status"]
        state.build_progress = build.get("progress", state.build_progress)
        if build["status"] == "completed":
            self._capture_machine_access(state, build)
            artifacts = await self.build_client.artifacts(state.build_id)
            if not artifacts:
                raise RuntimeError("build completed without an artifact")
            state.artifact = next(
                (item for item in artifacts if item.artifact_type == "qcow2"), artifacts[0]
            )
            state.status = SessionStatus.COMPLETED
        elif build["status"] in {"failed", "cancelled"}:
            state.error_message = build.get("error_message") or f"build {build['status']}"
            if state.build_repair_attempts < self.build_repair_max_attempts:
                return await self._start_build_repair(state)
            state.status = SessionStatus.FAILED
        elif build["status"] in {"building", "uploading"}:
            state.status = SessionStatus.BUILDING
        else:
            state.status = SessionStatus.BUILD_QUEUED
        return await self.repository.save(state)

    @staticmethod
    def _capture_machine_access(state: SessionState, build: dict) -> None:
        password = build.get("machine_password")
        if isinstance(password, str) and password:
            state.machine_access = MachineAccess(username="ubuntu", password=password)


def _compact_repair_history(history: list[dict], limit: int = 10) -> list[dict]:
    compact: list[dict] = []
    for attempt in history[-limit:]:
        trigger = attempt.get("trigger")
        compact_trigger: dict = {}
        if isinstance(trigger, dict):
            for key in ("kind", "status", "summary"):
                if key in trigger:
                    compact_trigger[key] = trigger[key]
            error_message = trigger.get("error_message")
            if isinstance(error_message, str):
                compact_trigger["error_message"] = _bounded_context(error_message, 2_000)
            packer_log = trigger.get("packer_log_tail")
            if isinstance(packer_log, str):
                compact_trigger["packer_log_tail"] = _bounded_context(packer_log, 4_000)
            checks = trigger.get("checks")
            if isinstance(checks, list):
                compact_trigger["failed_checks"] = [
                    check
                    for check in checks
                    if isinstance(check, dict) and check.get("status") == "fail"
                ]
        compact.append(
            {
                "attempt": attempt.get("attempt"),
                "trigger": compact_trigger,
                "changed_files": attempt.get("changed_files", []),
                "deleted_files": attempt.get("deleted_files", []),
                "validation_status_after": attempt.get("validation_status_after"),
                "validation_summary_after": attempt.get("validation_summary_after"),
            }
        )
    return compact


def _bounded_context(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    prefix = min(500, limit // 4)
    return value[:prefix] + "\n...[truncated]...\n" + value[-(limit - prefix) :]
