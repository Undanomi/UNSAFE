from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .admin import configure_sqladmin
from .api import router
from .config import Settings, get_settings
from .repository import SessionNotFoundError, SessionRepository
from .services.ai import GeminiGenerator
from .services.build_client import BuildClient
from .services.events import EventBroker
from .services.scenarios import ScenarioCoordinator
from .services.source_archive import SourceArchive
from .services.stub_ai import StubGenerator
from .services.workflow import MachineWorkflow


def create_app(
    settings: Settings | None = None,
    repository_override: SessionRepository | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    repository = repository_override or SessionRepository(
        resolved.database_url,
        resolved.database_pool_min_size,
        resolved.database_pool_max_size,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=resolved.log_level)
        await repository.initialize()
        ai_client = httpx.AsyncClient(
            timeout=httpx.Timeout(resolved.ai_timeout_seconds, connect=15)
        )
        build_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(resolved.build_timeout_seconds, connect=10)
        )
        generator = (
            StubGenerator()
            if resolved.ai_provider.lower() == "stub"
            else GeminiGenerator(resolved, ai_client)
        )
        broker = EventBroker()
        build_client = BuildClient(
            build_http_client,
            resolved.build_server_url,
            resolved.build_server_token.get_secret_value(),
        )
        app.state.repository = repository
        app.state.scenarios = ScenarioCoordinator(
            repository, generator, broker, resolved.scenario_chunk_size
        )
        app.state.workflow = MachineWorkflow(
            repository,
            generator,
            SourceArchive(resolved.source_root),
            build_client,
            resolved.source_generation_attempts,
            resolved.build_repair_max_attempts,
        )
        yield
        for task in [
            *app.state.scenarios.tasks.values(),
            *app.state.workflow.tasks.values(),
        ]:
            task.cancel()
        await ai_client.aclose()
        await build_http_client.aclose()
        await repository.close()

    app = FastAPI(title=resolved.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    if resolved.sqladmin_enabled and isinstance(repository, SessionRepository):
        app.state.sqladmin = configure_sqladmin(app, repository.engine, resolved)

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found(_: Request, __: SessionNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "session not found"})

    return app


app = create_app()


def run() -> None:
    uvicorn.run("ai_server.main:app", host="0.0.0.0", port=8000, reload=False)
