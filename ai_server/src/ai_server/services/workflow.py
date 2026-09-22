from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path

from ..models import (
    Artifact,
    GeneratedSource,
    MachineAccess,
    ScenarioReview,
    SessionState,
    SessionStatus,
    SourcePatch,
    SourceReview,
    scenario_is_valid_for_machine,
)
from ..repository import SessionRepository
from ..skills.models import SkillPhase
from ..skills.service import NoopSkillService, SkillResolver
from .ai import AIGenerator
from .build_client import BuildClient
from .errors import exception_detail
from .source_archive import InvalidSourceError, SourceArchive
from .source_repair import apply_source_patch
from .source_validation import known_failed_resources

logger = logging.getLogger(__name__)
BUILD_POLL_INTERVAL_SECONDS = 5
DISTRIBUTION_ARTIFACT_TYPE = "tar.zst"
MAX_SOURCE_REVIEW_RECONSIDERATIONS = 2


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
        scenario_sync_attempts: int,
        skill_service: SkillResolver | None = None,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.source_archive = source_archive
        self.build_client = build_client
        self.source_generation_attempts = source_generation_attempts
        self.build_repair_max_attempts = build_repair_max_attempts
        self.scenario_sync_attempts = scenario_sync_attempts
        self.skill_service = skill_service or NoopSkillService()
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.starting_sessions: set[str] = set()
        self.cancel_requests: set[str] = set()

    def is_running(self, session_id: str) -> bool:
        task = self.tasks.get(session_id)
        return session_id in self.starting_sessions or (task is not None and not task.done())

    async def cancel(self, session_id: str) -> None:
        self.cancel_requests.add(session_id)
        self.starting_sessions.discard(session_id)
        task = self.tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        state = await self.repository.get(session_id)
        if state.build_id and state.build_status not in {"completed", "failed", "cancelled"}:
            await self.build_client.cancel(state.build_id)

    async def start(self, session_id: str, scenario_id: str | None = None) -> SessionState:
        self.cancel_requests.discard(session_id)
        state = await self.repository.get(session_id)
        if not state.machine_information or not state.scenario:
            raise InvalidSessionStateError(
                "a generated scenario is required before machine creation"
            )
        if not scenario_is_valid_for_machine(state.machine_information, state.scenario):
            state.scenario = None
            state.status = SessionStatus.READY
            state.error_message = None
            await self.repository.save(state)
            raise InvalidSessionStateError(
                "scenario flag values are invalid; regenerate the scenario before machine creation"
            )
        if scenario_id and scenario_id != state.scenario.scenario_id:
            raise InvalidSessionStateError("scenario_id does not belong to this session")
        active_task = self.tasks.get(session_id)
        if active_task is not None:
            if not active_task.done():
                return state
            self.tasks.pop(session_id, None)
        if state.build_id:
            if state.build_status not in {"failed", "cancelled"}:
                return state
            state.build_repair_attempt_limit = (
                state.build_repair_attempts + self.build_repair_max_attempts
            )
            state.source_generation_attempt_limit = (
                state.source_generation_attempts
                + self.build_repair_max_attempts * self.source_generation_attempts
            )
            await self.repository.save(state)
            return await self._start_build_repair(state)
        state.build_repair_attempt_limit = (
            state.build_repair_attempts + self.build_repair_max_attempts
        )
        state.source_generation_attempt_limit = (
            state.source_generation_attempts
            + (self.build_repair_max_attempts + 1) * self.source_generation_attempts
        )
        state.status = SessionStatus.GENERATING_CODE
        self.starting_sessions.add(session_id)
        try:
            await self.repository.save(state)
            if session_id in self.cancel_requests:
                state.status = SessionStatus.CANCELLED
                state.error_message = None
                await self.repository.save(state)
                return state
            self._create_task(
                session_id,
                build_slots_remaining=self.build_repair_max_attempts + 1,
            )
        finally:
            self.starting_sessions.discard(session_id)
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
        persisted_failure_report = state.repair_failure_report
        repair_report = (
            dict(persisted_failure_report)
            if isinstance(persisted_failure_report, dict)
            else {
                "kind": "packer_build",
                "status": state.build_status,
                "error_message": state.error_message or "build failed without details",
            }
        )
        if persisted_failure_report is None and state.build_id:
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
                    failed_commands, failure_context = _extract_build_failures(build_log)
                    if failed_commands:
                        repair_report["failed_commands"] = failed_commands
                    if failure_context:
                        repair_report["failure_log_context"] = failure_context
        if _source_review_report_has_unsupported_target(repair_report):
            repair_report = {
                "kind": "source_review_revalidation",
                "status": "retry",
                "error_message": (
                    "the previous source review selected a repair target that is not mutable "
                    "during source generation"
                ),
                "previous_review": repair_report,
            }
        repair_history = (
            self.source_archive.load_repair_history_from_archive(archive_path)
            if archive_path is not None
            else self.source_archive.load_repair_history(state.source_path or "")
        )
        # A build repair can change the source and therefore require another scenario
        # synchronization cycle. Reserve that cycle as soon as the repair starts so
        # progress never remains at (for example) 4/4 during an active rebuild.
        state.scenario_sync_attempt_limit = (
            state.scenario_sync_attempts + self.scenario_sync_attempts
        )
        state.build_progress = 0
        state.machine_access = None
        state.artifact = None
        state.repair_failure_report = None
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
            persisted_failure_context = failure_report
            review_revalidation = (
                failure_report
                if isinstance(failure_report, dict)
                and failure_report.get("kind") == "source_review_revalidation"
                else None
            )
            if review_revalidation is not None:
                failure_report = None
            state = await self.repository.get(session_id)
            assert state.machine_information is not None and state.scenario is not None
            working_scenario = state.scenario
            authoritative_attack_graph = state.scenario.attack_graph
            source_skills = await self.skill_service.resolve(
                session_id,
                SkillPhase.SOURCE,
                state.machine_information,
                state.scenario,
            )
            repair_skills = await self.skill_service.resolve(
                session_id,
                SkillPhase.REPAIR,
                state.machine_information,
                state.scenario,
            )
            review_skills = await self.skill_service.resolve(
                session_id,
                SkillPhase.REVIEW,
                state.machine_information,
                state.scenario,
            )
            skill_snapshot = await self.skill_service.snapshot_manifest(session_id)
            archive_path = None
            if review_revalidation is None and failure_report is None:
                archive_path = self._existing_archive(state)
            checksum = state.source_checksum
            last_validation_error: Exception | None = None
            repair_history = list(existing_repair_history or [])
            best_validation_failures = 0 if failure_report is not None else None
            pending_source_review: SourceReview | None = None
            pending_source_review_source: GeneratedSource | None = None
            source_changed_since_scenario = False
            repair_failure_signatures: set[str] = set()
            reconsideration_signatures: set[str] = set()

            async def reconsider_source_review(
                source: GeneratedSource,
                review: SourceReview,
                context: dict,
            ) -> SourceReview:
                reconsideration_signature = json.dumps(
                    {
                        "source": _generated_source_checksum(source),
                        "review": _source_review_report(review),
                        "context": context,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                if (
                    reconsideration_signature in reconsideration_signatures
                    or len(reconsideration_signatures) >= MAX_SOURCE_REVIEW_RECONSIDERATIONS
                ):
                    state.build_repair_attempt_limit = state.build_repair_attempts
                    state.source_generation_attempt_limit = state.source_generation_attempts
                    await self.repository.save(state)
                    raise RuntimeError(
                        "source review reconsideration did not converge on a repairable finding"
                    )
                reconsideration_signatures.add(reconsideration_signature)
                return await self.generator.review_source(
                    state.machine_information,
                    working_scenario,
                    source,
                    review_skills,
                    reconsideration={
                        **context,
                        "previous_review": _source_review_report(review),
                    },
                )

            async def reconsider_repeated_repair_failure(
                base_source: GeneratedSource,
                trigger: dict,
                patch: SourcePatch,
                validation_report: dict,
            ) -> tuple[dict, SourceReview | None]:
                feedback = _source_repair_failure_report(
                    trigger,
                    patch,
                    validation_report,
                )
                signature = _source_repair_failure_signature(
                    base_source,
                    trigger,
                    patch,
                    validation_report,
                )
                if signature not in repair_failure_signatures:
                    repair_failure_signatures.add(signature)
                    return feedback, None
                if pending_source_review is None or pending_source_review_source is None:
                    state.build_repair_attempt_limit = state.build_repair_attempts
                    state.source_generation_attempt_limit = state.source_generation_attempts
                    await self.repository.save(state)
                    raise RuntimeError(
                        "source repair repeated the same patch and validation failure"
                    )
                reconsidered = await reconsider_source_review(
                    pending_source_review_source,
                    pending_source_review,
                    {
                        "kind": "source_repair_validation_failure",
                        "validation_failure": validation_report,
                        "attempted_patch": _serialized_source_patch(patch),
                    },
                )
                reconsidered_report = _source_review_report(reconsidered)
                return (
                    _source_repair_failure_report(
                        reconsidered_report,
                        patch,
                        validation_report,
                    ),
                    reconsidered,
                )

            if archive_path is not None:
                build_slots_remaining -= 1
            while archive_path is None and build_slots_remaining > 0:
                for _ in range(self.source_generation_attempts):
                    state.source_generation_attempts += 1
                    await self.repository.save(state)
                    if generated is None:
                        generated = await self.generator.generate_source(
                            state.machine_information, working_scenario, source_skills
                        )
                    assert generated is not None
                    retry_base = generated
                    retry_scenario = working_scenario
                    patch_applied = False
                    prevalidated_review: SourceReview | None = None
                    if failure_report is not None:
                        repair_trigger = failure_report
                        repair_context = {
                            **failure_report,
                            "known_failed_resources": known_failed_resources(repair_history),
                            "repair_history": _compact_repair_history(repair_history),
                        }
                        patch = await self.generator.repair_source(
                            state.machine_information,
                            working_scenario,
                            generated,
                            repair_context,
                            repair_skills,
                        )
                        try:
                            generated = apply_source_patch(generated, patch)
                        except InvalidSourceError as error:
                            last_validation_error = error
                            validation_report = _invalid_source_report(
                                error, "source_patch_validation"
                            )
                            repair_history.append(
                                _failed_source_repair_attempt(
                                    repair_history,
                                    repair_trigger,
                                    patch,
                                    validation_report,
                                )
                            )
                            failure_report, reconsidered = await reconsider_repeated_repair_failure(
                                retry_base,
                                repair_trigger,
                                patch,
                                validation_report,
                            )
                            if reconsidered is None or not reconsidered.approved:
                                if reconsidered is not None:
                                    pending_source_review = reconsidered
                                generated = pending_source_review_source or retry_base
                                continue
                            generated = pending_source_review_source or retry_base
                            pending_source_review = None
                            pending_source_review_source = None
                            prevalidated_review = reconsidered
                            repair_history.append(
                                _source_review_reconsideration_attempt(
                                    repair_history,
                                    reconsidered,
                                    validation_report,
                                )
                            )
                        else:
                            patch_applied = True
                            repair_history.append(
                                {
                                    "attempt": len(repair_history) + 1,
                                    "trigger": _persistable_repair_trigger(repair_trigger),
                                    "changed_files": sorted(file.path for file in patch.files),
                                    "deleted_files": sorted(patch.delete_paths),
                                }
                            )
                    try:
                        archive_path, checksum = self.source_archive.create(
                            session_id,
                            working_scenario,
                            generated,
                            repair_history,
                            skill_snapshot,
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
                            working_scenario = retry_scenario
                        elif failed_count is not None:
                            best_validation_failures = failed_count
                        validation_report = _invalid_source_report(error, "source_validation")
                        if not patch_applied:
                            failure_report = validation_report
                            continue
                        repair_history[-1]["validation_report_after"] = validation_report
                        failure_report, reconsidered = await reconsider_repeated_repair_failure(
                            retry_base,
                            repair_trigger,
                            patch,
                            validation_report,
                        )
                        if reconsidered is None or not reconsidered.approved:
                            if reconsidered is not None:
                                pending_source_review = reconsidered
                            if pending_source_review_source is not None:
                                generated = pending_source_review_source
                            continue
                        generated = pending_source_review_source or retry_base
                        pending_source_review = None
                        pending_source_review_source = None
                        repair_history.append(
                            _source_review_reconsideration_attempt(
                                repair_history,
                                reconsidered,
                                validation_report,
                            )
                        )
                        archive_path, checksum = self.source_archive.create(
                            session_id,
                            working_scenario,
                            generated,
                            repair_history,
                            skill_snapshot,
                        )
                        prevalidated_review = reconsidered
                    if patch_applied and prevalidated_review is None:
                        source_changed_since_scenario = True
                    if prevalidated_review is not None:
                        review = prevalidated_review
                    elif review_revalidation is not None:
                        review = await self.generator.review_source(
                            state.machine_information,
                            working_scenario,
                            generated,
                            review_skills,
                            reconsideration=review_revalidation,
                        )
                        review_revalidation = None
                    else:
                        review = await self.generator.review_source(
                            state.machine_information,
                            working_scenario,
                            generated,
                            review_skills,
                        )
                    if (
                        pending_source_review is not None
                        and not review.approved
                        and _source_review_did_not_improve(pending_source_review, review)
                    ):
                        review = await reconsider_source_review(
                            generated,
                            review,
                            {
                                "kind": "source_semantic_review_nonprogress",
                                "review_before_repair": _source_review_report(
                                    pending_source_review
                                ),
                                "source_before_repair": _generated_source_checksum(
                                    pending_source_review_source or retry_base
                                ),
                                "source_after_repair": _generated_source_checksum(generated),
                                "attempted_change": (
                                    {
                                        "kind": "source_patch",
                                        "patch": _serialized_source_patch(patch),
                                    }
                                    if patch_applied
                                    else {"kind": "scenario_sync"}
                                ),
                                "reason": (
                                    "an error finding remained after repair or the number of "
                                    "error findings increased"
                                ),
                            },
                        )

                    error_targets = _source_review_error_targets(review)
                    review_report = _source_review_report(review)
                    checksum = self.source_archive.record_semantic_review(
                        archive_path,
                        review_report,
                        approved=review.approved,
                    )
                    scenario_text_only = bool(error_targets) and error_targets <= {"scenario_text"}
                    if review.approved or scenario_text_only:
                        pending_source_review = None
                        pending_source_review_source = None
                        if source_changed_since_scenario or scenario_text_only:
                            scenario_before_sync = working_scenario
                            scenario_feedback: dict | None = (
                                review_report if scenario_text_only else None
                            )
                            scenario_reviews: list[dict] = []
                            state.scenario_sync_attempt_limit = (
                                state.scenario_sync_attempts + self.scenario_sync_attempts
                            )
                            await self.repository.save(state)
                            for _ in range(self.scenario_sync_attempts):
                                state.scenario_sync_attempts += 1
                                await self.repository.save(state)
                                if scenario_feedback is None:
                                    revision = await self.generator.synchronize_scenario(
                                        state.machine_information,
                                        working_scenario,
                                        generated,
                                    )
                                else:
                                    revision = await self.generator.synchronize_scenario(
                                        state.machine_information,
                                        working_scenario,
                                        generated,
                                        scenario_feedback,
                                    )
                                working_scenario = working_scenario.model_copy(
                                    update={
                                        "scenario_description": revision.scenario_description,
                                        "definition": revision.definition,
                                        "attack_graph": authoritative_attack_graph,
                                    }
                                )
                                scenario_review = await self.generator.review_scenario(
                                    state.machine_information,
                                    working_scenario,
                                    review_context="source_sync",
                                )
                                scenario_feedback = _scenario_review_report(scenario_review)
                                scenario_reviews.append(scenario_feedback)
                                if scenario_review.approved:
                                    break
                            if repair_history:
                                sync_record = repair_history[-1]
                            else:
                                sync_record = {
                                    "attempt": 1,
                                    "trigger": _persistable_repair_trigger(review_report),
                                    "changed_files": [],
                                    "deleted_files": [],
                                }
                                repair_history.append(sync_record)
                            sync_record["scenario_sync_summary"] = revision.summary
                            sync_record["scenario_sync_reviews"] = scenario_reviews
                            if not scenario_review.approved:
                                sync_record["scenario_sync_status"] = "rejected"
                                last_validation_error = InvalidSourceError(
                                    "synchronized scenario semantic review failed: "
                                    + scenario_review.summary,
                                    scenario_feedback,
                                )
                                if any(
                                    finding.severity == "error"
                                    and finding.repair_target == "source_code"
                                    for finding in scenario_review.findings
                                ):
                                    sync_record["scenario_sync_routed_to"] = "source_repair"
                                    failure_report = scenario_feedback
                                    archive_path = None
                                    checksum = None
                                    working_scenario = scenario_before_sync
                                    continue
                                failure_report = scenario_feedback
                                raise RuntimeError(
                                    "could not synchronize an approved scenario after source "
                                    "repair: " + scenario_review.summary
                                )
                            sync_record["scenario_sync_status"] = "approved"
                            archive_path, checksum = self.source_archive.create(
                                session_id,
                                working_scenario,
                                generated,
                                repair_history,
                                skill_snapshot,
                            )
                            checksum = self.source_archive.record_semantic_review(
                                archive_path,
                                review_report,
                                approved=review.approved,
                            )
                            source_changed_since_scenario = False
                            if scenario_text_only:
                                # The source reviewer must judge the synchronized artifacts again;
                                # an earlier rejection must never be reused as an approval.
                                failure_report = None
                                pending_source_review = review
                                pending_source_review_source = generated
                                archive_path = None
                                checksum = None
                                continue
                        logger.info(
                            "source semantic review approved",
                            extra={"session_id": session_id, "summary": review.summary},
                        )
                        break
                    last_validation_error = InvalidSourceError(
                        f"source semantic review failed: {review.summary}", review_report
                    )
                    failure_report = _source_review_report(
                        review,
                        repair_targets={"source_code"},
                    )
                    pending_source_review = review
                    pending_source_review_source = generated
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
            state.scenario = working_scenario
            state.source_path = str(archive_path.parent / "source")
            state.source_checksum = checksum
            state.build_id = None
            state.build_status = None
            state.build_progress = 0
            state.machine_access = None
            state.error_message = None
            state.repair_failure_report = None
            failure_report = None
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
            if isinstance(failure_report, dict):
                failure_to_persist = _persistable_repair_trigger(failure_report)
            elif isinstance(persisted_failure_context, dict):
                failure_to_persist = _persistable_repair_trigger(persisted_failure_context)
            else:
                failure_to_persist = {
                    "kind": "machine_workflow",
                    "status": "failed",
                    "error_message": detail,
                }
            state.repair_failure_report = failure_to_persist
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
                state.repair_failure_report = None
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
            state.machine_access = MachineAccess(username="provisioner", password=password)


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
            for key in ("failed_commands", "failure_log_context"):
                value = trigger.get(key)
                if isinstance(value, list):
                    compact_trigger[key] = value[:10]
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
                "scenario_sync_status": attempt.get("scenario_sync_status"),
                "scenario_sync_summary": attempt.get("scenario_sync_summary"),
            }
        )
    return compact


def _invalid_source_report(error: InvalidSourceError, kind: str) -> dict:
    report = error.report
    checks = report.get("checks") if isinstance(report, dict) else None
    if isinstance(checks, list) and checks:
        return {
            **report,
            "kind": report.get("kind", kind),
            "error_message": report.get("error_message", str(error)),
        }
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


def _source_repair_failure_report(
    trigger: dict,
    patch: SourcePatch,
    validation_report: dict,
) -> dict:
    return {
        **validation_report,
        "original_trigger": _root_repair_trigger(trigger),
        "rejected_patch": _serialized_source_patch(patch),
    }


def _failed_source_repair_attempt(
    repair_history: list[dict],
    trigger: dict,
    patch: SourcePatch,
    validation_report: dict,
) -> dict:
    return {
        "attempt": len(repair_history) + 1,
        "trigger": _persistable_repair_trigger(trigger),
        "changed_files": sorted(file.path for file in patch.files),
        "deleted_files": sorted(patch.delete_paths),
        "validation_status_after": "fail",
        "validation_summary_after": validation_report.get("summary"),
        "validation_report_after": validation_report,
    }


def _source_review_reconsideration_attempt(
    repair_history: list[dict],
    review: SourceReview,
    validation_report: dict,
) -> dict:
    return {
        "attempt": len(repair_history) + 1,
        "trigger": {
            "kind": "source_review_reconsideration",
            "status": "pass" if review.approved else "fail",
            "review": _source_review_report(review),
            "repair_validation_failure": validation_report,
        },
        "changed_files": [],
        "deleted_files": [],
    }


def _source_repair_failure_signature(
    base_source: GeneratedSource,
    trigger: dict,
    patch: SourcePatch,
    validation_report: dict,
) -> str:
    value = json.dumps(
        {
            "source": _generated_source_checksum(base_source),
            "trigger": _root_repair_trigger(trigger),
            "patch": patch.model_dump(mode="json"),
            "validation": validation_report,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generated_source_checksum(source: GeneratedSource) -> str:
    value = source.model_dump_json()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialized_source_patch(patch: SourcePatch) -> str:
    return patch.model_dump_json(indent=2)[:12_000]


def _root_repair_trigger(trigger: dict) -> dict:
    current = trigger
    visited: set[int] = set()
    while isinstance(current.get("original_trigger"), dict) and id(current) not in visited:
        visited.add(id(current))
        current = current["original_trigger"]
    return _persistable_repair_trigger(current)


def _persistable_repair_trigger(trigger: dict) -> dict:
    persisted = {
        key: value
        for key, value in trigger.items()
        if key not in {"rejected_patch", "rejected_model_output"}
    }
    original = persisted.get("original_trigger")
    if isinstance(original, dict):
        persisted["original_trigger"] = _persistable_repair_trigger(original)
    return persisted


def _validation_failed_count(report: dict) -> int | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    failed = summary.get("failed")
    return failed if isinstance(failed, int) and not isinstance(failed, bool) else None


def _source_review_error_targets(review: SourceReview) -> set[str]:
    return {finding.repair_target for finding in review.findings if finding.severity == "error"}


def _source_review_report_has_unsupported_target(report: dict) -> bool:
    if report.get("kind") != "source_semantic_review":
        return False
    checks = report.get("checks")
    if not isinstance(checks, list):
        return False
    return any(
        isinstance(check, dict)
        and check.get("status") == "fail"
        and check.get("repair_target") not in {"source_code", "scenario_text"}
        for check in checks
    )


def _source_review_did_not_improve(
    previous: SourceReview,
    current: SourceReview,
) -> bool:
    def error_keys(review: SourceReview) -> set[tuple[str | None, str, str]]:
        return {
            (finding.step_id, finding.category, finding.repair_target)
            for finding in review.findings
            if finding.severity == "error"
        }

    previous_errors = error_keys(previous)
    current_errors = error_keys(current)
    return bool(previous_errors & current_errors) or len(current_errors) > len(previous_errors)


def _source_review_report(
    review: SourceReview,
    repair_targets: set[str] | None = None,
) -> dict:
    checks = [
        {
            "status": "fail" if finding.severity == "error" else "warn",
            "name": (f"semantic:{finding.category}:{finding.step_id or 'scenario'}"),
            "message": f"{finding.evidence} Remediation: {finding.remediation}",
            "step_id": finding.step_id,
            "severity": finding.severity,
            "category": finding.category,
            "repair_target": finding.repair_target,
            "evidence": finding.evidence,
            "remediation": finding.remediation,
        }
        for finding in review.findings
        if repair_targets is None
        or finding.severity != "error"
        or finding.repair_target in repair_targets
    ]
    failed = sum(check["status"] == "fail" for check in checks)
    warnings = sum(check["status"] == "warn" for check in checks)
    return {
        "kind": "source_semantic_review",
        "status": "pass" if review.approved else "fail",
        "error_message": review.summary,
        "summary": {
            "passed": 1 if review.approved else 0,
            "failed": failed,
            "warnings": warnings,
        },
        "checks": checks,
    }


def _scenario_review_report(review: ScenarioReview) -> dict:
    checks = [
        {
            "status": "fail" if finding.severity == "error" else "warn",
            "name": (f"scenario_sync:{finding.category}:{finding.step_id or 'scenario'}"),
            "message": f"{finding.evidence} Remediation: {finding.remediation}",
        }
        for finding in review.findings
    ]
    failed = sum(check["status"] == "fail" for check in checks)
    warnings = sum(check["status"] == "warn" for check in checks)
    return {
        "kind": "scenario_sync_review",
        "status": "pass" if review.approved else "fail",
        "error_message": review.summary,
        "summary": {
            "passed": 1 if review.approved else 0,
            "failed": failed,
            "warnings": warnings,
        },
        "checks": checks,
    }


def _bounded_context(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    prefix = min(500, limit // 4)
    return value[:prefix] + "\n...[truncated]...\n" + value[-(limit - prefix) :]


def _extract_build_failures(log: str) -> tuple[list[str], list[str]]:
    """Extract traced shell commands and bounded context near concrete build errors."""

    lines = [line.rstrip() for line in log.splitlines() if line.strip()]
    error_pattern = re.compile(
        r"(?i)(?:\berror\b|\bfailed\b|failure|command not found|permission denied|"
        r"no such file|non[- ]zero|exit status|returned?\s+\d+)"
    )
    trace_pattern = re.compile(r"^\s*\+\s+(.+\S)\s*$")
    commands: list[str] = []
    contexts: list[str] = []
    for index, line in enumerate(lines):
        if not error_pattern.search(line):
            continue
        start = max(0, index - 3)
        end = min(len(lines), index + 2)
        context = "\n".join(lines[start:end])
        if context not in contexts:
            contexts.append(context)
        for candidate in reversed(lines[max(0, index - 12) : index + 1]):
            match = trace_pattern.match(candidate)
            if match:
                command = match.group(1)
                if command not in commands:
                    commands.append(command)
                break
        if len(contexts) >= 10:
            break
    return commands[:10], contexts[:10]
