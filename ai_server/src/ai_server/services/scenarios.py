from __future__ import annotations

import asyncio
import logging
import secrets

from ..models import (
    AttackGraph,
    ScenarioDraft,
    ScenarioReview,
    SessionState,
    SessionStatus,
    scenario_is_valid_for_machine,
)
from ..repository import SessionRepository
from ..skills.models import ScenarioSkillContexts, SkillPhase
from ..skills.service import NoopSkillService, SkillResolver
from .ai import AIGenerator
from .errors import ScenarioInputRevisionRequiredError, exception_detail
from .events import EventBroker, ServerEvent
from .scenario_archive import ScenarioDraftArchive

logger = logging.getLogger(__name__)


def _new_flag(kind: str) -> str:
    return f"flag{{{kind}_{secrets.token_hex(16)}}}"


class ScenarioAttemptObserver:
    def __init__(
        self,
        repository: SessionRepository,
        archive: ScenarioDraftArchive,
        state: SessionState,
    ) -> None:
        self.repository = repository
        self.archive = archive
        self.state = state
        self.current_attempt = max(
            state.scenario_generation_attempts,
            archive.latest_attempt_number(state.session_id),
        )
        resumed = (
            archive.load_latest(state.session_id, state.machine_information)
            if state.machine_information is not None
            else None
        )
        self.resume_scenario = resumed[0] if resumed is not None else None
        self.resume_review = resumed[1] if resumed is not None else None

    async def __call__(self) -> None:
        self.state.scenario_generation_attempts += 1
        self.current_attempt += 1
        await self.repository.save(self.state)
        self.archive.start_attempt(
            self.state.session_id,
            self.current_attempt,
            self.state.machine_information,
        )

    async def record_attack_graph(self, graph: AttackGraph) -> None:
        self.archive.record_attack_graph(
            self.state.session_id,
            self.current_attempt,
            graph,
        )

    async def record_failure(self, phase: str, error: Exception) -> None:
        self.archive.record_failure(
            self.state.session_id,
            self.current_attempt,
            phase,
            error,
        )

    async def record_draft(
        self, scenario: ScenarioDraft, review: ScenarioReview | None = None
    ) -> None:
        self.archive.record(
            self.state.session_id,
            self.current_attempt,
            scenario,
            review,
            self.state.machine_information,
        )


class ScenarioCoordinator:
    def __init__(
        self,
        repository: SessionRepository,
        generator: AIGenerator,
        broker: EventBroker,
        chunk_size: int,
        scenario_generation_attempts: int,
        draft_archive: ScenarioDraftArchive,
        skill_service: SkillResolver | None = None,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.broker = broker
        self.chunk_size = chunk_size
        self.scenario_generation_attempts = scenario_generation_attempts
        self.draft_archive = draft_archive
        self.skill_service = skill_service or NoopSkillService()
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def ensure_started(self, session_id: str) -> None:
        task = self.tasks.get(session_id)
        if task is None or task.done():
            task = asyncio.create_task(self._run(session_id))
            self.tasks[session_id] = task
            task.add_done_callback(
                lambda completed: (
                    self.tasks.pop(session_id, None)
                    if self.tasks.get(session_id) is completed
                    else None
                )
            )

    def is_running(self, session_id: str) -> bool:
        task = self.tasks.get(session_id)
        return task is not None and not task.done()

    async def cancel(self, session_id: str) -> None:
        task = self.tasks.pop(session_id, None)
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _run(self, session_id: str) -> None:
        try:
            state = await self.repository.get(session_id)
            if state.scenario:
                if state.machine_information and scenario_is_valid_for_machine(
                    state.machine_information, state.scenario
                ):
                    await self.broker.publish(
                        session_id,
                        ServerEvent(
                            "scenario.completed", {"scenario": state.scenario.model_dump()}
                        ),
                    )
                    return
                state.scenario = None
                state.status = SessionStatus.READY
                state.error_message = None
                await self.repository.save(state)
            if not state.machine_information:
                raise ValueError(
                    "machine information must be registered before scenario generation"
                )
            state.status = SessionStatus.GENERATING_SCENARIO
            state.error_message = None
            state.scenario_generation_attempt_limit = (
                state.scenario_generation_attempts + self.scenario_generation_attempts
            )
            await self.repository.save(state)
            await self.broker.publish(
                session_id, ServerEvent("scenario.started", {"session_id": session_id})
            )
            attack_graph_skills = await self.skill_service.resolve(
                session_id,
                SkillPhase.ATTACK_GRAPH,
                state.machine_information,
            )
            scenario_skills = await self.skill_service.resolve(
                session_id,
                SkillPhase.SCENARIO,
                state.machine_information,
            )
            attempt_observer = ScenarioAttemptObserver(
                self.repository,
                self.draft_archive,
                state,
            )

            scenario = await self.generator.generate_scenario(
                state.machine_information,
                ScenarioSkillContexts(
                    attack_graph=attack_graph_skills,
                    scenario=scenario_skills,
                ),
                attempt_observer,
            )
            scenario = ScenarioDraft.model_validate(
                {
                    **scenario.model_dump(),
                    "user_flag": (
                        _new_flag("user") if state.machine_information.needs_user_flag else None
                    ),
                    "system_flag": (
                        _new_flag("system") if state.machine_information.needs_system_flag else None
                    ),
                }
            )
            if not scenario_is_valid_for_machine(state.machine_information, scenario):
                raise ValueError("generated scenario does not match machine requirements")
            await self.skill_service.finalize_scenario(session_id, scenario)
            state.scenario = scenario
            state.status = SessionStatus.SCENARIO_READY
            await self.repository.save(state)
            for offset in range(0, len(scenario.definition), self.chunk_size):
                await self.broker.publish(
                    session_id,
                    ServerEvent(
                        "scenario.delta",
                        {"content": scenario.definition[offset : offset + self.chunk_size]},
                    ),
                )
                await asyncio.sleep(0)
            await self.broker.publish(
                session_id,
                ServerEvent("scenario.completed", {"scenario": scenario.model_dump()}),
            )
        except ScenarioInputRevisionRequiredError as error:
            logger.warning(
                "scenario input requires revision",
                extra={"session_id": session_id, "review_summary": error.summary},
            )
            state = await self.repository.get(session_id)
            state.status = SessionStatus.FAILED
            state.error_message = error.summary
            await self.repository.save(state)
            await self.broker.publish(
                session_id,
                ServerEvent("scenario.error", error.event_data()),
            )
        except Exception as error:
            detail = exception_detail(error)
            logger.exception("scenario generation failed", extra={"session_id": session_id})
            state = await self.repository.get(session_id)
            state.status = SessionStatus.FAILED
            state.error_message = detail
            await self.repository.save(state)
            await self.broker.publish(session_id, ServerEvent("scenario.error", {"detail": detail}))
        finally:
            await self.broker.close(session_id)
