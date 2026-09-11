from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..models import (
    Artifact,
    GeneratedSource,
    MachineAccess,
    SessionState,
    SessionStatus,
    SourceReview,
)
from ..repository import SessionRepository
from .ai import AIGenerator
from .build_client import BuildClient
from .errors import exception_detail
from .source_archive import InvalidSourceError, SourceArchive
from .source_repair import apply_source_patch
from .source_validation import known_failed_resources

logger = logging.getLogger(__name__)
BUILD_POLL_INTERVAL_SECONDS = 5
DISTRIBUTION_ARTIFACT_TYPE = "tar.zst"


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
        active_task = self.tasks.get(session_id)
        if active_task is not None:
            if not active_task.done():
                return state
            self.tasks.pop(session_id, None)
        if state.build_id and state.build_status not in {"completed", "failed", "cancelled"}:
            state = await self.synchronize(state, auto_repair=False, force=True)
        if state.build_id:
            if state.build_status not in {"failed", "cancelled"}:
                return state
            state.build_repair_attempt_limit = (
                state.build_repair_attempts + self.build_repair_max_attempts
            )
            await self.repository.save(state)
            return await self._start_build_repair(state)
        state.build_repair_attempt_limit = (
            state.build_repair_attempts + self.build_repair_max_attempts
        )
        state.status = SessionStatus.GENERATING_CODE
        await self.repository.save(state)
        self._create_task(
            session_id,
            build_slots_remaining=self.build_repair_max_attempts + 1,
        )
        return state

    async def _start_build_repair(
        self,
        state: SessionState,
        build_slots_remaining: int | None = None,
    ) -> SessionState:
        prepared = await self._prepare_build_repair(state)
        if prepared is not None:
            repair_source, repair_report, repair_history = prepared
            remaining = (
                state.build_repair_attempt_limit - state.build_repair_attempts
                if build_slots_remaining is None
                else build_slots_remaining
            )
            self._create_task(
                state.session_id,
                repair_source,
                repair_report,
                repair_history,
                remaining,
            )
        return state

    async def _prepare_build_repair(
        self, state: SessionState
    ) -> tuple[GeneratedSource, dict, list[dict]] | None:
        if state.build_repair_attempts >= state.build_repair_attempt_limit:
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
        build_slots_remaining: int = 1,
    ) -> None:
        task = asyncio.create_task(
            self._generate_and_submit(
                session_id,
                generated,
                failure_report,
                repair_history,
                build_slots_remaining,
            )
        )
        self.tasks[session_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(session_id, None))

    async def _generate_and_submit(
        self,
        session_id: str,
        generated: GeneratedSource | None = None,
        failure_report: dict | None = None,
        existing_repair_history: list[dict] | None = None,
        build_slots_remaining: int = 1,
    ) -> None:
        try:
            is_build_repair = failure_report is not None
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
            if archive_path is not None:
                build_slots_remaining -= 1
            while archive_path is None and build_slots_remaining > 0:
                for _ in range(self.source_generation_attempts):
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
                        try:
                            generated = apply_source_patch(generated, patch)
                        except InvalidSourceError as error:
                            last_validation_error = error
                            failure_report = _invalid_source_report(
                                error, "source_patch_validation"
                            )
                            continue
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
                    except InvalidSourceError as error:
                        last_validation_error = error
                        failed_count = _validation_failed_count(error.report)
                        if (
                            patch_applied
                            and best_validation_failures is not None
                            and failed_count is not None
                            and failed_count >= best_validation_failures
                        ):
                            generated = retry_base
                        elif failed_count is not None:
                            best_validation_failures = failed_count
                        failure_report = _invalid_source_report(error, "source_validation")
                        continue
                    review = await self.generator.review_source(
                        state.machine_information,
                        state.scenario,
                        generated,
                    )
                    if review.approved:
                        logger.info(
                            "source semantic review approved",
                            extra={"session_id": session_id, "summary": review.summary},
                        )
                        break
                    review_report = _source_review_report(review)
                    last_validation_error = InvalidSourceError(
                        f"source semantic review failed: {review.summary}", review_report
                    )
                    failure_report = review_report
                    archive_path = None
                    checksum = None
                build_slots_remaining -= 1
                if archive_path is None and build_slots_remaining > 0:
                    logger.info(
                        "source validation batch exhausted; continuing with next build slot",
                        extra={
                            "session_id": session_id,
                            "build_slots_remaining": build_slots_remaining,
                        },
                    )
            if archive_path is None or checksum is None:
                state.build_repair_attempt_limit = state.build_repair_attempts
                await self.repository.save(state)
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
            if is_build_repair:
                state.build_repair_attempts += 1
            state.build_id = build["build_id"]
            state.build_status = build["status"]
            state.build_progress = build.get("progress", 0)
            state.status = SessionStatus.BUILD_QUEUED
            await self.repository.save(state)
            await self._monitor_build(session_id, build_slots_remaining)
        except Exception as error:
            detail = exception_detail(error)
            logger.exception("machine workflow failed", extra={"session_id": session_id})
            state = await self.repository.get(session_id)
            state.status = SessionStatus.FAILED
            state.error_message = detail
            await self.repository.save(state)

    async def _monitor_build(self, session_id: str, build_slots_remaining: int) -> None:
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
                state.artifact = self._distribution_artifact(artifacts)
                state.status = SessionStatus.COMPLETED
                await self.repository.save(state)
                return
            if build["status"] in {"failed", "cancelled"}:
                state.error_message = build.get("error_message") or f"build {build['status']}"
                if build_slots_remaining <= 0:
                    state.build_repair_attempt_limit = state.build_repair_attempts
                    state.status = SessionStatus.FAILED
                    await self.repository.save(state)
                    return
                prepared = await self._prepare_build_repair(state)
                if prepared is None:
                    return
                repair_source, repair_report, repair_history = prepared
                await self._generate_and_submit(
                    session_id,
                    repair_source,
                    repair_report,
                    repair_history,
                    build_slots_remaining,
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

    async def synchronize(
        self,
        state: SessionState,
        *,
        auto_repair: bool = True,
        force: bool = False,
    ) -> SessionState:
        if (
            not state.build_id
            or state.session_id in self.tasks
            or (
                not force
                and state.status == SessionStatus.FAILED
                and (
                    state.build_status not in {"failed", "cancelled"}
                    or state.build_repair_attempts >= state.build_repair_attempt_limit
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
            state.artifact = self._distribution_artifact(artifacts)
            state.status = SessionStatus.COMPLETED
        elif build["status"] in {"failed", "cancelled"}:
            state.error_message = build.get("error_message") or f"build {build['status']}"
            if auto_repair and (state.build_repair_attempts < state.build_repair_attempt_limit):
                return await self._start_build_repair(state)
            state.status = SessionStatus.FAILED
        elif build["status"] in {"building", "uploading"}:
            state.status = SessionStatus.BUILDING
        else:
            state.status = SessionStatus.BUILD_QUEUED
        return await self.repository.save(state)

    @staticmethod
    def _distribution_artifact(artifacts: list[Artifact]) -> Artifact:
        artifact = next(
            (item for item in artifacts if item.artifact_type == DISTRIBUTION_ARTIFACT_TYPE),
            None,
        )
        if artifact is None:
            raise RuntimeError("build completed without a tar.zst distribution artifact")
        return artifact

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


def _invalid_source_report(error: InvalidSourceError, kind: str) -> dict:
    report = error.report
    checks = report.get("checks") if isinstance(report, dict) else None
    if isinstance(checks, list) and checks:
        return report
    return {
        "kind": kind,
        "status": "fail",
        "error_message": str(error),
        "summary": {"passed": 0, "failed": 1, "warnings": 0},
        "checks": [
            {
                "status": "fail",
                "name": f"{kind}:invalid_path_or_patch",
                "message": str(error),
            }
        ],
    }


def _validation_failed_count(report: dict) -> int | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    failed = summary.get("failed")
    return failed if isinstance(failed, int) and not isinstance(failed, bool) else None


def _source_review_report(review: SourceReview) -> dict:
    checks = [
        {
            "status": "fail" if finding.severity == "error" else "warn",
            "name": (f"semantic:{finding.category}:{finding.step_id or 'scenario'}"),
            "message": f"{finding.evidence} Remediation: {finding.remediation}",
        }
        for finding in review.findings
    ]
    failed = sum(check["status"] == "fail" for check in checks)
    warnings = sum(check["status"] == "warn" for check in checks)
    return {
        "kind": "source_semantic_review",
        "status": "fail",
        "error_message": review.summary,
        "summary": {"passed": 0, "failed": failed, "warnings": warnings},
        "checks": checks,
    }


def _bounded_context(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    prefix = min(500, limit // 4)
    return value[:prefix] + "\n...[truncated]...\n" + value[-(limit - prefix) :]
