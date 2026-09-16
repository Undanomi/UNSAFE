from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .admin import configure_sqladmin
from .config import AdminSettings
from .repository import SessionRepository


def create_admin_app(settings: AdminSettings | None = None) -> FastAPI:
    resolved = settings or AdminSettings()
    repository = SessionRepository(
        resolved.database_url,
        resolved.database_pool_min_size,
        resolved.database_pool_max_size,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await repository.ping()
            yield
        finally:
            await repository.close()

    app = FastAPI(
        title=f"{resolved.app_name} Admin",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.repository = repository
    app.state.sqladmin = configure_sqladmin(app, repository.engine, resolved)
    return app


def run() -> None:
    uvicorn.run(
        "ai_server.admin_app:create_admin_app",
        factory=True,
        host="0.0.0.0",
        port=8001,
        reload=False,
    )
