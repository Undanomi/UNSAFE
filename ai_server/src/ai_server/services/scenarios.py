from __future__ import annotations

import asyncio
import logging
import secrets

from ..models import SessionStatus
from ..repository import SessionRepository
from .ai import AIGenerator
from .errors import exception_detail
from .events import EventBroker, ServerEvent

logger = logging.getLogger(__name__)


def _new_flag(kind: str) -> str:
    return f"flag{{{kind}_{secrets.token_hex(16)}}}"


class ScenarioCoordinator:
    def __init__(
        self,
        repository: SessionRepository,
        generator: AIGenerator,
        broker: EventBroker,
        chunk_size: int,
    ) -> None:
        self.repository = repository
        self.generator = generator
        self.broker = broker
        self.chunk_size = chunk_size
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def ensure_started(self, session_id: str) -> None:
        task = self.tasks.get(session_id)
        if task is None or task.done():
            self.tasks[session_id] = asyncio.create_task(self._run(session_id))

    async def _run(self, session_id: str) -> None:
        try:
            state = await self.repository.get(session_id)
            if state.scenario:
                await self.broker.publish(
                    session_id,
                    ServerEvent("scenario.completed", {"scenario": state.scenario.model_dump()}),
                )
                return
            if not state.machine_information:
                raise ValueError(
                    "machine information must be registered before scenario generation"
                )
            state.status = SessionStatus.GENERATING_SCENARIO
            state.error_message = None
            await self.repository.save(state)
            await self.broker.publish(
                session_id, ServerEvent("scenario.started", {"session_id": session_id})
            )
            scenario = await self.generator.generate_scenario(state.machine_information)
            scenario = scenario.model_copy(
                update={
                    "user_flag": (
                        _new_flag("user") if state.machine_information.needs_user_flag else None
                    ),
                    "system_flag": (
                        _new_flag("system") if state.machine_information.needs_system_flag else None
                    ),
                }
            )
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
