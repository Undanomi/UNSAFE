from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from ..models import (
    Artifact,
    GeneratedSource,
    MachineAccess,
    MachineInformation,
    ScenarioDraft,
    ScenarioReview,
    SessionState,
    SessionStatus,
    SourcePatch,
    SourceReview,
    SourceWorkbenchCommand,
    scenario_is_valid_for_machine,
)
from ..repository import SessionRepository
from ..skills.models import SkillPhase
from ..skills.service import NoopSkillService, SkillResolver
from ..source_workbench_policy import is_target_vm_executable
from .ai import (
    AIGenerator,
    AIProviderSafetyRefusalError,
    begin_token_usage_session,
    end_token_usage_session,
)
from .build_client import BuildClient
from .errors import exception_detail
from .rockyou import (
    RockYouPasswordSelector,
    bind_rockyou_passwords,
    strip_rockyou_selections,
)
from .scenario_secrets import redact_scenario_secrets
from .source_archive import InvalidSourceError, SourceArchive
from .source_repair import apply_source_patch
from .source_sandbox import SourceSandboxClient, SourceSandboxError
from .source_validation import known_failed_resources

logger = logging.getLogger(__name__)
BUILD_POLL_INTERVAL_SECONDS = 5
DISTRIBUTION_ARTIFACT_TYPE = "zip"
MAX_SOURCE_REVIEW_RECONSIDERATIONS = 2
MAX_WORKBENCH_POLICY_REJECTIONS = 4
SOURCE_SANDBOX_KEEPALIVE_SECONDS = 60


class MachineWorkflowGraphState(TypedDict, total=False):
    session_id: str
    generated: GeneratedSource | None
    failure_report: dict | None
    repair_history: list[dict]
    build_slots_remaining: int
    outcome: Literal["generate", "submitted", "repair", "completed", "failed"]


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
        rockyou_path: Path | None = None,
        rockyou_min_line: int = 1,
        rockyou_max_line: int = 1,
        source_sandbox: SourceSandboxClient | None = None,
        source_workbench_action_limit: int = 20,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.source_archive = source_archive
        self.build_client = build_client
        self.source_generation_attempts = source_generation_attempts
        self.build_repair_max_attempts = build_repair_max_attempts
        self.scenario_sync_attempts = scenario_sync_attempts
        self.skill_service = skill_service or NoopSkillService()
        self.rockyou_path = rockyou_path
        self.rockyou_min_line = rockyou_min_line
        self.rockyou_max_line = rockyou_max_line
        self.source_sandbox = source_sandbox
        self.source_workbench_action_limit = source_workbench_action_limit
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.starting_sessions: set[str] = set()
        self.cancel_requests: set[str] = set()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(MachineWorkflowGraphState)
        graph.add_node("generate_and_submit", self._graph_generate_and_submit)
        graph.add_node("monitor_build", self._graph_monitor_build)
        graph.add_edge(START, "generate_and_submit")
        graph.add_conditional_edges(
            "generate_and_submit",
            self._route_after_generation,
            {"monitor_build": "monitor_build", END: END},
        )
        graph.add_conditional_edges(
            "monitor_build",
            self._route_after_build,
            {"generate_and_submit": "generate_and_submit", END: END},
        )
        return graph.compile()

    @staticmethod
    async def _route_after_generation(state: MachineWorkflowGraphState) -> str:
        return "monitor_build" if state.get("outcome") == "submitted" else END

    @staticmethod
    async def _route_after_build(state: MachineWorkflowGraphState) -> str:
        return "generate_and_submit" if state.get("outcome") == "repair" else END

    def is_running(self, session_id: str) -> bool:
        task = self.tasks.get(session_id)
        return session_id in self.starting_sessions or (task is not None and not task.done())

    def bind_construction_passwords(
        self, session_id: str, scenario: ScenarioDraft
    ) -> ScenarioDraft:
        """Bind repeatable construction-only values without changing the stored design."""
        if not any(step.password_cracking for step in scenario.attack_graph.steps):
            return scenario
        if self.rockyou_path is None:
            raise RuntimeError("rockyou selector is required to bind password cracking source")
        return bind_rockyou_passwords(
            scenario,
            RockYouPasswordSelector(
                self.rockyou_path,
                self.rockyou_min_line,
                self.rockyou_max_line,
                selection_key=session_id,
            ),
        )

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

    async def refresh_distribution_artifact(self, state: SessionState) -> SessionState:
        if not state.build_id:
            return state
        if state.status in {SessionStatus.BUILD_QUEUED, SessionStatus.BUILDING}:
            try:
                build = await self.build_client.get(state.build_id)
            except Exception:
                logger.warning(
                    "on-demand build status refresh failed",
                    exc_info=True,
                    extra={"session_id": state.session_id, "build_id": state.build_id},
                )
            else:
                state.build_status = build["status"]
                state.build_progress = build.get("progress", state.build_progress)
                if build["status"] == "completed":
                    self._capture_machine_access(state, build)
                    artifacts = await self.build_client.artifacts(state.build_id)
                    state.artifact = self._distribution_artifact(artifacts)
                    state.status = SessionStatus.COMPLETED
                    state = await self.repository.save(state)
                elif build["status"] in {"building", "uploading"}:
                    state.status = SessionStatus.BUILDING
                    state = await self.repository.save(state)
        if state.status != SessionStatus.COMPLETED:
            return state
        if (
            state.artifact is not None
            and state.artifact.artifact_type == DISTRIBUTION_ARTIFACT_TYPE
            and state.artifact.file_name == f"{state.artifact.artifact_id}.zip"
        ):
            return state
        artifacts = await self.build_client.artifacts(state.build_id)
        artifact = next(
            (item for item in artifacts if item.artifact_type == DISTRIBUTION_ARTIFACT_TYPE),
            None,
        )
        if artifact is None or state.artifact == artifact:
            return state
        state.artifact = artifact
        return await self.repository.save(state)

    async def start(self, session_id: str, scenario_id: str | None = None) -> SessionState:
        self.cancel_requests.discard(session_id)
        state = await self.repository.get(session_id)
        if (
            state.status == SessionStatus.FAILED
            and isinstance(state.repair_failure_report, dict)
            and state.repair_failure_report.get("kind") == "ai_safety_refusal"
        ):
            raise InvalidSessionStateError(
                "安全上の理由でAIが処理を拒否したため、同じ候補は再ビルドできません。"
            )
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
                    failed_commands, failed_checks, failure_context = _extract_build_failures(
                        build_log
                    )
                    if failed_checks:
                        repair_report["failed_checks"] = failed_checks
                    else:
                        # Before verify.sh starts there is no structured check ID, so
                        # retain the legacy evidence needed for provisioning failures.
                        repair_report["packer_log_tail"] = build_log
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
        if archive_path is not None:
            previous_semantic_review = self.source_archive.load_semantic_review_from_archive(
                archive_path
            )
            if previous_semantic_review is not None:
                repair_report["previous_semantic_review"] = previous_semantic_review
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
            self._run_graph(
                {
                    "session_id": session_id,
                    "generated": generated,
                    "failure_report": failure_report,
                    "repair_history": list(repair_history or []),
                    "build_slots_remaining": build_slots_remaining,
                    "outcome": "generate",
                }
            )
        )
        self.tasks[session_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(session_id, None))

    async def _run_graph(self, graph_state: MachineWorkflowGraphState) -> None:
        try:
            await self.graph.ainvoke(graph_state, {"recursion_limit": 100})
        except asyncio.CancelledError:
            raise
        except Exception as error:
            session_id = graph_state["session_id"]
            detail = exception_detail(error)
            logger.exception("machine workflow graph failed", extra={"session_id": session_id})
            state = await self.repository.get(session_id)
            state.status = SessionStatus.FAILED
            state.error_message = detail
            if isinstance(error, AIProviderSafetyRefusalError):
                state.repair_failure_report = {
                    "kind": "ai_safety_refusal",
                    "status": "blocked",
                    "summary": error.summary,
                    "retry_allowed": False,
                }
            else:
                state.repair_failure_report = {
                    "kind": "machine_workflow_graph",
                    "status": "failed",
                    "error_message": detail,
                }
            await self.repository.save(state)

    async def _graph_generate_and_submit(
        self, graph_state: MachineWorkflowGraphState
    ) -> MachineWorkflowGraphState:
        remaining = await self._generate_and_submit_once(
            graph_state["session_id"],
            graph_state.get("generated"),
            graph_state.get("failure_report"),
            graph_state.get("repair_history"),
            graph_state.get("build_slots_remaining", 1),
        )
        state = await self.repository.get(graph_state["session_id"])
        return {
            "build_slots_remaining": remaining or 0,
            "outcome": (
                "submitted"
                if remaining is not None
                and state.build_id is not None
                and state.status in {SessionStatus.BUILD_QUEUED, SessionStatus.BUILDING}
                else "failed"
            ),
        }

    async def _run_source_workbench(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        generated: GeneratedSource,
        failure_context: dict | None = None,
    ) -> tuple[GeneratedSource, dict]:
        if self.source_sandbox is None:
            return generated, {
                "kind": "source_workbench",
                "status": "skipped",
                "summary": "isolated source workbench is disabled",
                "observations": [],
            }

        initial_generated = generated
        sandbox_id = await self.source_sandbox.create(generated)
        observations: list[dict] = []
        if failure_context is not None:
            observations.append(
                {
                    "index": 0,
                    "kind": "incoming_failure",
                    "details": _bounded_context(
                        redact_scenario_secrets(
                            json.dumps(failure_context, ensure_ascii=False, default=str),
                            scenario,
                        ),
                        12_000,
                    ),
                }
            )
        final_summary = "workbench action limit reached after successful commands"
        pending_verifications: dict[str, dict] = {}
        unverified_patch = False
        successful_verifications = 0
        blocked_summary: str | None = None
        deferred_to_vm_summary: str | None = None

        def command_signature(command) -> str:
            return json.dumps(
                command.model_dump(mode="json", exclude={"purpose"}),
                sort_keys=True,
                separators=(",", ":"),
            )

        async def collect_changes() -> tuple[GeneratedSource, list[str], list[str]]:
            changes = await self.source_sandbox.changes(sandbox_id)
            if changes is None:
                return generated, [], []
            return (
                apply_source_patch(initial_generated, changes),
                sorted(file.path for file in changes.files),
                sorted(changes.delete_paths),
            )

        async def next_decision():
            task = asyncio.create_task(
                self.generator.next_source_workbench_action(
                    machine,
                    scenario,
                    generated,
                    observations,
                    self.source_workbench_action_limit - action_index,
                )
            )
            try:
                while True:
                    done, _ = await asyncio.wait(
                        {task}, timeout=SOURCE_SANDBOX_KEEPALIVE_SECONDS
                    )
                    if done:
                        return task.result()
                    await self.source_sandbox.touch(sandbox_id)
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

        try:
            action_index = 0
            policy_rejections = 0
            while action_index < self.source_workbench_action_limit:
                decision = await next_decision()
                final_summary = decision.summary
                if decision.action == "finish":
                    if decision.finish_status == "blocked":
                        blocked_summary = decision.summary
                        observations.append(
                            {
                                "index": len(observations) + 1,
                                "kind": "finish_blocked",
                                "reason": decision.summary,
                            }
                        )
                        break
                    for signature, failed in list(pending_verifications.items()):
                        if action_index >= self.source_workbench_action_limit:
                            break
                        command = SourceWorkbenchCommand.model_validate(failed["command"])
                        try:
                            result = await self.source_sandbox.execute(sandbox_id, command)
                        except SourceSandboxError as error:
                            if error.status_code != 400:
                                raise
                            action_index += 1
                            observations.append(
                                {
                                    "index": len(observations) + 1,
                                    "kind": "command",
                                    "purpose": command.purpose,
                                    "command": command.model_dump(mode="json"),
                                    "intent": command.intent,
                                    "automatic_recheck": True,
                                    "exit_code": 126,
                                    "timed_out": False,
                                    "policy_rejected": True,
                                    "accepted": False,
                                    "blocking": True,
                                    "stdout": "",
                                    "stderr": _bounded_context(str(error), 8_000),
                                }
                            )
                            continue
                        action_index += 1
                        command_succeeded = (
                            not result.timed_out
                            and result.exit_code in command.allowed_exit_codes
                        )
                        observation = {
                            "index": len(observations) + 1,
                            "kind": "command",
                            "purpose": command.purpose,
                            "command": command.model_dump(mode="json"),
                            "intent": command.intent,
                            "automatic_recheck": True,
                            "exit_code": result.exit_code,
                            "timed_out": result.timed_out,
                            "stdout": _bounded_context(result.stdout, 8_000),
                            "stderr": _bounded_context(result.stderr, 8_000),
                            "accepted": command_succeeded,
                            "blocking": not command_succeeded,
                        }
                        observations.append(observation)
                        if command_succeeded:
                            pending_verifications.pop(signature, None)
                            unverified_patch = False
                            successful_verifications += 1
                            observation["resolved_failure_index"] = failed["index"]
                        else:
                            pending_verifications[signature] = observation
                    if (
                        pending_verifications
                        or unverified_patch
                        or successful_verifications == 0
                    ):
                        action_index += 1
                        observations.append(
                            {
                                "index": len(observations) + 1,
                                "kind": "finish_rejected",
                                "reason": (
                                    "all previously failing commands must pass after the patch"
                                    if pending_verifications
                                    else (
                                        "the latest patch must be verified by a successful command"
                                        if unverified_patch
                                        else "at least one verification command must succeed"
                                    )
                                ),
                                "pending_commands": [
                                    item.get("command")
                                    for item in pending_verifications.values()
                                ],
                            }
                        )
                        continue
                    if decision.finish_status == "deferred_to_vm":
                        deferred_to_vm_summary = decision.summary
                        observations.append(
                            {
                                "index": len(observations) + 1,
                                "kind": "finish_deferred_to_vm",
                                "reason": decision.summary,
                            }
                        )
                    break
                if decision.action == "patch":
                    assert decision.patch is not None
                    try:
                        updated = apply_source_patch(generated, decision.patch)
                        await self.source_sandbox.apply_patch(sandbox_id, decision.patch)
                    except (InvalidSourceError, SourceSandboxError) as error:
                        if isinstance(error, SourceSandboxError) and error.status_code != 400:
                            raise
                        policy_rejections += 1
                        observations.append(
                            {
                                "index": len(observations) + 1,
                                "kind": "patch_rejected",
                                "changed_files": sorted(
                                    file.path for file in decision.patch.files
                                ),
                                "deleted_files": sorted(decision.patch.delete_paths),
                                "error": _bounded_context(str(error), 8_000),
                            }
                        )
                        if policy_rejections >= MAX_WORKBENCH_POLICY_REJECTIONS:
                            raise SourceSandboxError(
                                "source workbench agent repeatedly proposed invalid patches"
                            ) from error
                        continue
                    action_index += 1
                    generated = updated
                    unverified_patch = True
                    observations.append(
                        {
                            "index": len(observations) + 1,
                            "kind": "patch",
                            "summary": decision.summary,
                            "changed_files": sorted(file.path for file in decision.patch.files),
                            "deleted_files": sorted(decision.patch.delete_paths),
                            "verification_required": True,
                        }
                    )
                    continue
                assert decision.command is not None
                if is_target_vm_executable(decision.command.argv[0]):
                    action_index += 1
                    deferred_to_vm_summary = (
                        "Target VM integration checks were deferred to Packer and the booted VM."
                    )
                    observations.append(
                        {
                            "index": len(observations) + 1,
                            "kind": "command_deferred_to_vm",
                            "purpose": decision.command.purpose,
                            "command": decision.command.model_dump(mode="json"),
                            "intent": decision.command.intent,
                            "accepted": False,
                            "blocking": False,
                            "reason": (
                                "the command requires target VM integration that the Docker "
                                "workbench must not emulate"
                            ),
                        }
                    )
                    continue
                try:
                    result = await self.source_sandbox.execute(sandbox_id, decision.command)
                except SourceSandboxError as error:
                    if error.status_code != 400:
                        raise
                    policy_rejections += 1
                    observations.append(
                        {
                            "index": len(observations) + 1,
                            "purpose": decision.command.purpose,
                            "command": decision.command.model_dump(mode="json"),
                            "intent": decision.command.intent,
                            "exit_code": 126,
                            "timed_out": False,
                            "policy_rejected": True,
                            "blocking": False,
                            "stdout": "",
                            "stderr": _bounded_context(str(error), 8_000),
                        }
                    )
                    if policy_rejections >= MAX_WORKBENCH_POLICY_REJECTIONS:
                        raise SourceSandboxError(
                            "source workbench agent repeatedly proposed commands rejected by "
                            "sandbox policy"
                        ) from error
                    continue
                action_index += 1
                observation = {
                    "index": len(observations) + 1,
                    "kind": "command",
                    "purpose": decision.command.purpose,
                    "command": decision.command.model_dump(mode="json"),
                    "intent": decision.command.intent,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "stdout": _bounded_context(result.stdout, 8_000),
                    "stderr": _bounded_context(result.stderr, 8_000),
                }
                observations.append(observation)
                command_succeeded = (
                    not result.timed_out
                    and result.exit_code in decision.command.allowed_exit_codes
                )
                observation["accepted"] = command_succeeded
                observation["blocking"] = (
                    decision.command.intent == "verify" and not command_succeeded
                )
                if not command_succeeded:
                    if decision.command.intent == "verify":
                        pending_verifications[command_signature(decision.command)] = observation
                    continue
                if decision.command.intent == "verify":
                    unverified_patch = False
                    successful_verifications += 1
                    resolved = pending_verifications.pop(
                        command_signature(decision.command), None
                    )
                    if resolved is not None:
                        observation["resolved_failure_index"] = resolved["index"]

            if (
                blocked_summary is not None
                or pending_verifications
                or unverified_patch
                or successful_verifications == 0
            ):
                unresolved = list(pending_verifications.values())
                generated, changed_files, deleted_files = await collect_changes()
                return generated, {
                    "kind": "source_workbench",
                    "status": "fail",
                    "error_message": (
                        "source workbench agent reported a technical verification blocker"
                        if blocked_summary is not None
                        else (
                            "source workbench action budget ended before the failing command passed"
                            if pending_verifications
                            else (
                                "source workbench action budget ended before the latest patch was verified"
                                if unverified_patch
                                else "source workbench ended without a successful verification command"
                            )
                        )
                    ),
                    "blocked_summary": blocked_summary,
                    "failed_command": unresolved[-1] if unresolved else None,
                    "failed_commands": unresolved,
                    "observations": observations,
                    "changed_files": changed_files,
                    "deleted_files": deleted_files,
                    "candidate_changes_preserved": bool(changed_files or deleted_files),
                    "successful_verifications": successful_verifications,
                }

            generated, changed_files, deleted_files = await collect_changes()
            return generated, {
                "kind": "source_workbench",
                "status": "pass",
                "summary": final_summary,
                "observations": observations,
                "changed_files": changed_files,
                "deleted_files": deleted_files,
                "successful_verifications": successful_verifications,
                "deferred_to_vm": deferred_to_vm_summary,
            }
        finally:
            await self.source_sandbox.destroy(sandbox_id)

    async def _generate_and_submit_once(
        self,
        session_id: str,
        generated: GeneratedSource | None = None,
        failure_report: dict | None = None,
        existing_repair_history: list[dict] | None = None,
        build_slots_remaining: int = 1,
    ) -> int | None:
        usage_token = begin_token_usage_session(session_id)
        try:
            is_build_repair = failure_report is not None
            build_repair_has_approved_semantic_review = bool(
                isinstance(failure_report, dict)
                and isinstance(failure_report.get("previous_semantic_review"), dict)
                and failure_report["previous_semantic_review"].get("status")
                in {"approved", "resolved_by_scenario_sync"}
            )
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
            scenario_sync_required = False
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
                    if any(
                        step.password_cracking is not None
                        and not step.password_cracking.selection_bound
                        for step in working_scenario.attack_graph.steps
                    ):
                        working_scenario = self.bind_construction_passwords(
                            session_id, working_scenario
                        )
                        authoritative_attack_graph = working_scenario.attack_graph
                    retry_base = generated
                    retry_scenario = working_scenario
                    patch_applied = False
                    workbench_changed_source = False
                    workbench_report: dict | None = None
                    workbench_failure_context = failure_report
                    resume_preserved_workbench_candidate = bool(
                        isinstance(failure_report, dict)
                        and failure_report.get("kind") == "source_workbench"
                        and failure_report.get("candidate_changes_preserved") is True
                    )
                    prevalidated_review: SourceReview | None = None
                    if failure_report is not None and not resume_preserved_workbench_candidate:
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
                    elif resume_preserved_workbench_candidate:
                        # The workbench already repaired the candidate and checkpointed its
                        # filesystem diff. Revalidate that exact candidate in a fresh sandbox
                        # instead of asking a second AI repair pass to rewrite it again.
                        failure_report = None
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
                    if self.source_sandbox is not None:
                        workbench_base_checksum = _generated_source_checksum(generated)
                        generated, workbench_report = await self._run_source_workbench(
                            state.machine_information,
                            working_scenario,
                            generated,
                            workbench_failure_context,
                        )
                        if repair_history:
                            repair_history[-1]["source_workbench_after"] = workbench_report
                        if workbench_report["status"] != "pass":
                            if (
                                workbench_report.get("successful_verifications") == 0
                                and not workbench_report.get("candidate_changes_preserved")
                            ):
                                raise RuntimeError(
                                    "source workbench produced no successful verification evidence"
                                )
                            last_validation_error = InvalidSourceError(
                                workbench_report.get(
                                    "error_message", "isolated source workbench failed"
                                ),
                                workbench_report,
                            )
                            failure_report = workbench_report
                            archive_path = None
                            checksum = None
                            continue
                        workbench_changed_source = (
                            _generated_source_checksum(generated) != workbench_base_checksum
                        )
                        if workbench_changed_source:
                            prevalidated_review = None
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
                                failure_report = {
                                    "kind": "source_workbench_changes_validation",
                                    **_invalid_source_report(error, "source_validation"),
                                    "source_workbench": workbench_report,
                                }
                                archive_path = None
                                checksum = None
                                continue
                        checksum = self.source_archive.record_workbench_report(
                            archive_path, workbench_report
                        )
                    if prevalidated_review is not None:
                        review = prevalidated_review
                    elif review_revalidation is not None:
                        review = await self.generator.review_source(
                            state.machine_information,
                            working_scenario,
                            generated,
                            review_skills,
                            reconsideration={
                                **review_revalidation,
                                "source_workbench": workbench_report,
                            },
                        )
                        review_revalidation = None
                    elif patch_applied and (
                        pending_source_review is not None
                        or build_repair_has_approved_semantic_review
                    ):
                        changed_files = {
                            *(file.path for file in patch.files),
                            *patch.delete_paths,
                        }
                        blocking_review = pending_source_review or SourceReview(
                            approved=True,
                            summary=(
                                "The source passed semantic review before the concrete build "
                                "failure repair."
                            ),
                        )
                        full_review_reasons = _source_review_scope_invalidation_reasons(
                            retry_base,
                            generated,
                            blocking_review,
                            changed_files,
                            declared_repair_surface=(
                                changed_files if pending_source_review is None else None
                            ),
                        )
                        review = await self.generator.review_source(
                            state.machine_information,
                            working_scenario,
                            generated,
                            review_skills,
                            reconsideration={
                                "kind": (
                                    "source_full_reaudit"
                                    if full_review_reasons
                                    else "source_repair_verification"
                                ),
                                "blocking_review": _source_review_report(blocking_review),
                                "changed_files": sorted(changed_files),
                                "full_review_reasons": full_review_reasons,
                                "repair_origin": (
                                    "build_failure"
                                    if pending_source_review is None
                                    else "semantic_review"
                                ),
                                "source_workbench": workbench_report,
                            },
                        )
                        if not full_review_reasons:
                            review = _scope_source_repair_review(
                                blocking_review,
                                review,
                                changed_files,
                            )
                        repair_history[-1]["semantic_review_scope"] = (
                            "full" if full_review_reasons else "fixed_findings_and_regressions"
                        )
                        if full_review_reasons:
                            repair_history[-1]["full_review_reasons"] = full_review_reasons
                    else:
                        review = await self.generator.review_source(
                            state.machine_information,
                            working_scenario,
                            generated,
                            review_skills,
                            reconsideration=(
                                {
                                    "kind": "source_workbench_evidence",
                                    "workbench": workbench_report,
                                }
                                if workbench_report is not None
                                else None
                            ),
                        )
                    error_targets = _source_review_error_targets(review)
                    review_report = _source_review_report(review)
                    scenario_text_only = bool(error_targets) and error_targets <= {"scenario_text"}
                    checksum = self.source_archive.record_semantic_review(
                        archive_path,
                        review_report,
                        approved=review.approved,
                    )
                    if review.approved or scenario_text_only:
                        if (patch_applied or workbench_changed_source) and _source_review_contract(
                            retry_base
                        ) != _source_review_contract(generated):
                            scenario_sync_required = True
                        pending_source_review = None
                        pending_source_review_source = None
                        if scenario_sync_required or scenario_text_only:
                            scenario_feedback: dict | None = (
                                review_report if scenario_text_only else None
                            )
                            scenario_reviews: list[dict] = []
                            previous_scenario_review_signature: str | None = None
                            scenario_sync_limit = self.scenario_sync_attempts
                            state.scenario_sync_attempt_limit = (
                                state.scenario_sync_attempts + scenario_sync_limit
                            )
                            await self.repository.save(state)
                            for _ in range(scenario_sync_limit):
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
                                scenario_review = _scope_scenario_sync_review(scenario_review)
                                scenario_feedback = _scenario_review_report(scenario_review)
                                scenario_reviews.append(scenario_feedback)
                                if scenario_review.approved:
                                    break
                                scenario_review_signature = _scenario_review_error_signature(
                                    scenario_review
                                )
                                if scenario_review_signature == previous_scenario_review_signature:
                                    break
                                previous_scenario_review_signature = scenario_review_signature
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
                                approved=review.approved or scenario_text_only,
                                status=(
                                    "resolved_by_scenario_sync" if scenario_text_only else None
                                ),
                            )
                            scenario_sync_required = False
                        logger.info(
                            "source candidate cleared for build",
                            extra={
                                "session_id": session_id,
                                "summary": review.summary,
                            },
                        )
                        break
                    last_validation_error = InvalidSourceError(
                        f"source semantic review failed: {review.summary}", review_report
                    )
                    candidate_report = _source_review_report(review, repair_targets={"source_code"})
                    if (
                        pending_source_review is not None
                        and pending_source_review_source is not None
                    ):
                        failure_report = {
                            "kind": "source_semantic_repair_retry",
                            "status": "fail",
                            "error_message": (
                                "The current candidate still has unresolved fixed-scope findings or "
                                "a regression in a changed file. Continue from this candidate and "
                                "apply one minimal follow-up patch that preserves completed fixes."
                            ),
                            "blocking_review": _source_review_report(pending_source_review),
                            "candidate_review": candidate_report,
                            "rejected_patch": _serialized_source_patch(patch),
                        }
                        repair_history[-1]["semantic_review_after"] = candidate_report
                        repair_history[-1]["candidate_status"] = (
                            "rejected_retained_for_followup"
                        )
                        pending_source_review = review
                        pending_source_review_source = generated
                    elif patch_applied and build_repair_has_approved_semantic_review:
                        failure_report = {
                            "kind": "build_repair_semantic_retry",
                            "status": "fail",
                            "error_message": (
                                "The build-failure repair introduced a semantic regression. "
                                "Continue from the repaired candidate and remove the regression "
                                "without discarding the build fix."
                            ),
                            "original_trigger": _persistable_repair_trigger(repair_trigger),
                            "candidate_review": candidate_report,
                            "rejected_patch": _serialized_source_patch(patch),
                        }
                        repair_history[-1]["semantic_review_after"] = candidate_report
                        repair_history[-1]["candidate_status"] = (
                            "rejected_retained_for_followup"
                        )
                        pending_source_review = review
                        pending_source_review_source = generated
                    else:
                        failure_report = candidate_report
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
            state.scenario = strip_rockyou_selections(working_scenario)
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
            return build_slots_remaining
        except Exception as error:
            detail = exception_detail(error)
            logger.exception("machine workflow failed", extra={"session_id": session_id})
            state = await self.repository.get(session_id)
            state.status = SessionStatus.FAILED
            state.error_message = detail
            if isinstance(error, AIProviderSafetyRefusalError):
                failure_to_persist = {
                    "kind": "ai_safety_refusal",
                    "status": "blocked",
                    "summary": error.summary,
                    "retry_allowed": False,
                }
            elif isinstance(failure_report, dict):
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
            return None
        finally:
            end_token_usage_session(usage_token)

    async def _graph_monitor_build(
        self, graph_state: MachineWorkflowGraphState
    ) -> MachineWorkflowGraphState:
        session_id = graph_state["session_id"]
        build_slots_remaining = graph_state.get("build_slots_remaining", 0)
        while True:
            state = await self.repository.get(session_id)
            if not state.build_id:
                return {"outcome": "failed"}
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
                return {"outcome": "failed"}
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
                return {"outcome": "completed"}
            if build["status"] in {"failed", "cancelled"}:
                state.error_message = build.get("error_message") or f"build {build['status']}"
                state.repair_failure_report = None
                if build_slots_remaining <= 0:
                    state.build_repair_attempt_limit = state.build_repair_attempts
                    state.status = SessionStatus.FAILED
                    await self.repository.save(state)
                    return {"outcome": "failed"}
                prepared = await self._prepare_build_repair(state)
                if prepared is None:
                    return {"outcome": "failed"}
                repair_source, repair_report, repair_history = prepared
                return {
                    "generated": repair_source,
                    "failure_report": repair_report,
                    "repair_history": repair_history,
                    "build_slots_remaining": build_slots_remaining,
                    "outcome": "repair",
                }
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
            raise RuntimeError("build completed without a zip distribution artifact")
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
            for key in ("failed_commands", "failed_checks", "failure_log_context"):
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


def _source_review_finding_key(finding) -> tuple[str | None, str, str]:
    return finding.step_id, finding.category, finding.repair_target


def _source_review_contract(source: GeneratedSource) -> dict | None:
    manifest_file = next(
        (file for file in source.files if file.path == "contents/scenario_manifest.json"),
        None,
    )
    if manifest_file is None:
        return None
    try:
        manifest = json.loads(manifest_file.content)
    except json.JSONDecodeError:
        return None
    if not isinstance(manifest, dict):
        return None

    def sorted_values(field: str, *identity_fields: str):
        values = manifest.get(field)
        if not isinstance(values, list):
            return values
        return sorted(
            values,
            key=lambda value: tuple(
                str(value.get(identity, "")) if isinstance(value, dict) else str(value)
                for identity in identity_fields
            ),
        )

    return {
        "target_os": manifest.get("target_os"),
        "services": sorted_values("services", "name", "protocol", "port"),
        "expected_vulnerabilities": sorted_values("expected_vulnerabilities", "cve_id", "name"),
        # Attack-step order is part of the intended chain and must remain significant.
        "attack_steps": manifest.get("attack_steps"),
        "objectives": sorted_values("objectives", "objective_id", "objective_type"),
    }


def _source_review_scope_invalidation_reasons(
    base_source: GeneratedSource,
    candidate_source: GeneratedSource,
    blocking_review: SourceReview,
    changed_files: set[str],
    declared_repair_surface: set[str] | None = None,
) -> list[str]:
    """Detect semantic contract changes that require a new full source review."""

    reasons: list[str] = []
    if _source_review_contract(base_source) != _source_review_contract(candidate_source):
        reasons.append("the scenario manifest's review contract changed")

    def is_support_path(path: str) -> bool:
        name = path.rsplit("/", 1)[-1].lower()
        return (
            path == "contents/README.md"
            or "/tests/" in path.lower()
            or name.startswith(("test-", "test_"))
            or name.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts"))
        )

    base_inventory = {
        file.path for file in base_source.files if not is_support_path(file.path)
    }
    candidate_inventory = {
        file.path for file in candidate_source.files if not is_support_path(file.path)
    }
    if base_inventory != candidate_inventory:
        reasons.append("the generated implementation file inventory changed")

    if declared_repair_surface is None:
        declared_repair_surface = {
            path
            for finding in blocking_review.findings
            if finding.severity == "error"
            for path in finding.affected_files
        }
    supports_test_repair = any(
        finding.severity == "error"
        and finding.category in {"acceptance_test_gap", "unproven_exploit"}
        for finding in blocking_review.findings
    )
    if supports_test_repair:
        declared_repair_surface |= {
            path
            for path in changed_files
            if is_support_path(path) or path == "contents/scenario_manifest.json"
        }
    material_changed_files = {
        path for path in changed_files if path != "contents/README.md"
    }
    if material_changed_files and not declared_repair_surface:
        reasons.append("the blocking review did not declare a bounded repair surface")
    elif not material_changed_files <= declared_repair_surface:
        outside_scope = sorted(material_changed_files - declared_repair_surface)
        reasons.append(
            "the patch expanded beyond the declared repair surface: " + ", ".join(outside_scope)
        )
    return reasons


def _scope_source_repair_review(
    blocking_review: SourceReview,
    candidate_review: SourceReview,
    changed_files: set[str],
) -> SourceReview:
    """Keep follow-up review focused on fixed findings and patch-caused regressions."""

    blocking_keys = {
        _source_review_finding_key(finding)
        for finding in blocking_review.findings
        if finding.severity == "error"
    }
    scoped_findings = []
    deferred = 0
    for finding in candidate_review.findings:
        in_fixed_scope = _source_review_finding_key(finding) in blocking_keys
        is_patch_regression = bool(changed_files.intersection(finding.affected_files))
        if finding.severity == "error" and not (in_fixed_scope or is_patch_regression):
            deferred += 1
            finding = finding.model_copy(update={"severity": "warning"})
        scoped_findings.append(finding)
    has_error = any(finding.severity == "error" for finding in scoped_findings)
    summary = candidate_review.summary
    if deferred:
        summary += (
            f" {deferred} out-of-scope late finding(s) were retained as warnings because they "
            "were neither part of the fixed review nor caused by a changed file."
        )
    return SourceReview(
        approved=not has_error,
        summary=summary,
        findings=scoped_findings,
    )


def _scope_scenario_sync_review(review: ScenarioReview) -> ScenarioReview:
    """Scenario synchronization may correct prose, but must not reopen source design."""

    findings = [
        finding
        if finding.severity != "error" or finding.repair_target == "scenario_text"
        else finding.model_copy(update={"severity": "warning"})
        for finding in review.findings
    ]
    return ScenarioReview(
        approved=not any(finding.severity == "error" for finding in findings),
        summary=review.summary,
        findings=findings,
    )


def _scenario_review_error_signature(review: ScenarioReview) -> str:
    """Identify repeated sync blockers without depending on prose wording."""

    findings = sorted(
        (
            finding.step_id or "",
            finding.category,
            finding.repair_target,
            tuple(sorted(finding.repair_fields)),
        )
        for finding in review.findings
        if finding.severity == "error"
    )
    return json.dumps(findings, ensure_ascii=False)


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
            "affected_files": finding.affected_files,
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


def _extract_build_failures(
    log: str,
) -> tuple[list[str], list[dict[str, int | str]], list[str]]:
    """Extract failed verification IDs, traced commands, and nearby build errors."""

    lines = [line.rstrip() for line in log.splitlines() if line.strip()]
    error_pattern = re.compile(
        r"(?i)(?:\berror\b|\bfailed\b|failure|command not found|permission denied|"
        r"no such file|non[- ]zero|exit status|returned?\s+\d+)"
    )
    trace_pattern = re.compile(r"^\s*\+\s+(.+\S)\s*$")
    check_failure_pattern = re.compile(
        r"\bSLSG_CHECK_FAIL\s+"
        r"(?P<check_id>(?:health_checks|acceptance_tests)\[\d+\])\s+"
        r"exit=(?P<exit_code>\d+)\b"
    )
    script_failure_pattern = re.compile(
        r"\bSLSG_SCRIPT_FAIL\s+phase=(?P<phase>\S+)\s+"
        r"source=(?P<source>\S+)\s+line=(?P<line>\d+)\s+"
        r"exit=(?P<exit_code>\d+)\b"
    )
    commands: list[str] = []
    failed_checks: list[dict[str, int | str]] = []
    contexts: list[str] = []
    marker_indexes: set[int] = set()

    # Structured verification failures are more useful than generic Packer errors.
    # Capture them first so earlier non-fatal messages cannot consume the context limit.
    for index, line in enumerate(lines):
        script_match = script_failure_pattern.search(line)
        if script_match:
            marker_indexes.add(index)
            command = (
                f"{script_match.group('source')}:{script_match.group('line')} "
                f"(phase={script_match.group('phase')}, "
                f"exit={script_match.group('exit_code')})"
            )
            if command not in commands:
                commands.append(command)
            start = max(0, index - 4)
            end = min(len(lines), index + 2)
            context = "\n".join(lines[start:end])
            if context not in contexts and len(contexts) < 10:
                contexts.append(context)
        check_match = check_failure_pattern.search(line)
        if check_match:
            marker_indexes.add(index)
            failed_check: dict[str, int | str] = {
                "check_id": check_match.group("check_id"),
                "exit_code": int(check_match.group("exit_code")),
            }
            if failed_check not in failed_checks:
                failed_checks.append(failed_check)
            start = max(0, index - 3)
            end = min(len(lines), index + 2)
            context = "\n".join(lines[start:end])
            if context not in contexts and len(contexts) < 10:
                contexts.append(context)

    for index, line in enumerate(lines):
        if index in marker_indexes or not error_pattern.search(line):
            continue
        start = max(0, index - 3)
        end = min(len(lines), index + 2)
        context = "\n".join(lines[start:end])
        if context not in contexts and len(contexts) < 10:
            contexts.append(context)
        for candidate in reversed(lines[max(0, index - 12) : index + 1]):
            match = trace_pattern.match(candidate)
            if match:
                command = match.group(1)
                if command not in commands:
                    commands.append(command)
                break
    return commands[:10], failed_checks[:10], contexts[:10]
