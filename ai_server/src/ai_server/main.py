from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import router
from .config import Settings, get_settings
from .repository import SessionNotFoundError, SessionRepository
from .services.ai import GeminiGenerator, OpenAIGenerator
from .services.build_client import BuildClient
from .services.download_signing import DownloadSigner
from .services.events import EventBroker
from .services.scenario_archive import ScenarioDraftArchive
from .services.scenarios import ScenarioCoordinator
from .services.source_archive import SourceArchive
from .services.source_sandbox import SourceSandboxClient
from .services.stub_ai import StubGenerator
from .services.workflow import MachineWorkflow
from .skills.planning import SemanticSkillPlanner
from .skills.repository import SkillRepository
from .skills.service import NoopSkillService, SkillResolver, SkillService


def create_app(
    settings: Settings | None = None,
    repository_override: SessionRepository | None = None,
    skill_service_override: SkillResolver | None = None,
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
        sandbox_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(resolved.source_sandbox_timeout_seconds, connect=10)
        )
        if resolved.ai_provider == "stub":
            generator = StubGenerator()
        elif resolved.ai_provider == "gemini":
            generator = GeminiGenerator(resolved, ai_client)
        else:
            generator = OpenAIGenerator(resolved, ai_client)
        if isinstance(generator, (GeminiGenerator, OpenAIGenerator)) and isinstance(
            repository, SessionRepository
        ):
            generator.set_token_usage_recorder(repository.increment_ai_token_usage)
        if skill_service_override is not None:
            skill_service = skill_service_override
        elif resolved.skills_enabled and isinstance(repository, SessionRepository):
            skill_service = SkillService(
                SkillRepository(repository.session_factory),
                max_active=resolved.skills_max_active,
                max_per_phase=resolved.skills_max_per_phase,
                max_context_chars=resolved.skill_context_max_chars,
                planner=SemanticSkillPlanner(
                    generator._generate,
                    model=generator.model,
                    min_cve_year=resolved.cve_min_year,
                    max_catalog_chars=resolved.skill_selection_max_chars,
                    max_skills=resolved.skills_max_per_phase,
                    max_cves=resolved.skill_selection_max_cves,
                    retries=resolved.skill_selection_retries,
                )
                if isinstance(generator, (GeminiGenerator, OpenAIGenerator))
                else None,
            )
        else:
            skill_service = NoopSkillService()
        broker = EventBroker()
        build_client = BuildClient(
            build_http_client,
            resolved.build_server_url,
            resolved.build_server_token.get_secret_value(),
        )
        source_sandbox = (
            SourceSandboxClient(
                sandbox_http_client,
                resolved.source_sandbox_url,
                resolved.source_sandbox_token.get_secret_value(),
                resolved.source_sandbox_timeout_seconds,
            )
            if resolved.source_sandbox_enabled
            else None
        )
        scenario_archive = ScenarioDraftArchive(resolved.source_root)
        app.state.repository = repository
        app.state.skills = skill_service
        app.state.scenarios = ScenarioCoordinator(
            repository,
            generator,
            broker,
            resolved.scenario_chunk_size,
            resolved.scenario_generation_attempts,
            scenario_archive,
            skill_service,
        )
        app.state.workflow = MachineWorkflow(
            repository,
            generator,
            SourceArchive(resolved.source_root),
            build_client,
            resolved.source_generation_attempts,
            resolved.build_repair_max_attempts,
            resolved.scenario_sync_attempts,
            skill_service,
            rockyou_path=resolved.rockyou_path,
            rockyou_min_line=resolved.rockyou_min_line,
            rockyou_max_line=resolved.rockyou_max_line,
            source_sandbox=source_sandbox,
            source_workbench_action_limit=resolved.source_workbench_action_limit,
            scenario_archive=scenario_archive,
        )
        app.state.download_signer = DownloadSigner(
            resolved.download_signing_secret.get_secret_value(),
            resolved.download_url_ttl_seconds,
        )
        yield
        background_tasks = [
            *app.state.scenarios.tasks.values(),
            *app.state.workflow.tasks.values(),
        ]
        for task in background_tasks:
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        await ai_client.aclose()
        await build_http_client.aclose()
        await sandbox_http_client.aclose()
        await repository.close()

    app = FastAPI(title=resolved.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found(_: Request, __: SessionNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "session not found"})

    return app


app = create_app()


def run() -> None:
    uvicorn.run("ai_server.main:app", host="0.0.0.0", port=8000, reload=False)
