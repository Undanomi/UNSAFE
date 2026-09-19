from __future__ import annotations

import os
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import delete

from ai_server.admin import AISessionAdmin, ScenarioVersionAdmin, configure_sqladmin
from ai_server.admin_app import create_admin_app
from ai_server.config import AdminSettings, Settings
from ai_server.database import AISessionRecord, create_database_engine, sqlalchemy_database_url
from ai_server.main import create_app


def admin_settings(**overrides) -> AdminSettings:
    values = {
        "sqladmin_username": "admin-user",
        "sqladmin_password": "a-long-admin-password",
        "sqladmin_session_secret": "test-session-secret-that-is-at-least-32-characters",
    }
    values.update(overrides)
    return AdminSettings(**values)


def test_sqlalchemy_database_url_uses_asyncpg() -> None:
    url = sqlalchemy_database_url("postgresql://user:p%40ss@db:5432/service")
    assert url.drivername == "postgresql+asyncpg"
    assert url.password == "p@ss"


def test_sqladmin_requires_credentials() -> None:
    with pytest.raises(ValidationError, match="SQLADMIN_USERNAME"):
        AdminSettings(
            sqladmin_username="",
            sqladmin_password="",
            sqladmin_session_secret="",
        )


def test_admin_views_allow_editing_only() -> None:
    assert AISessionAdmin.can_create is False
    assert AISessionAdmin.can_edit is True
    assert AISessionAdmin.can_delete is False
    assert AISessionAdmin.form_excluded_columns == (AISessionAdmin.model.created_at,)


@pytest.mark.asyncio
async def test_scenario_version_admin_rejects_invalid_attack_graph() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        await ScenarioVersionAdmin().on_model_change(
            {"attack_graph": {"objectives": [], "steps": []}},
            model=None,
            is_created=False,
            request=None,
        )


@pytest.mark.asyncio
async def test_sqladmin_login_protects_admin_routes() -> None:
    settings = admin_settings()
    app = FastAPI()
    engine = create_database_engine(settings.database_url, 1, 1)
    configure_sqladmin(app, engine, settings)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            anonymous = await client.get("/admin/")
            assert anonymous.status_code == 302
            assert anonymous.headers["location"].endswith("/admin/login")

            rejected = await client.post(
                "/admin/login", data={"username": "admin-user", "password": "wrong"}
            )
            assert rejected.status_code == 400

            accepted = await client.post(
                "/admin/login",
                data={"username": "admin-user", "password": "a-long-admin-password"},
            )
            assert accepted.status_code == 302
            assert "slsg_admin_session=" in accepted.headers["set-cookie"]

            index = await client.get("/admin/")
            assert index.status_code == 200
    finally:
        await engine.dispose()


def test_api_app_does_not_expose_sqladmin() -> None:
    app = create_app(Settings())

    assert all(
        not path.startswith("/admin")
        for route in app.routes
        if (path := getattr(route, "path", None)) is not None
    )


@pytest.mark.asyncio
async def test_admin_app_redirects_root_to_admin() -> None:
    app = create_admin_app(admin_settings())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as client:
        response = await client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/admin"


@pytest.mark.asyncio
async def test_sqladmin_lists_sessions_from_postgres() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")
    settings = admin_settings(database_url=database_url)
    api_app = create_app(Settings(database_url=database_url, ai_provider="stub"))
    admin_app = create_admin_app(settings)
    async with api_app.router.lifespan_context(api_app):
        repository = api_app.state.repository
        state = await repository.create("admin-edit-before")
        try:
            async with admin_app.router.lifespan_context(admin_app):
                transport = httpx.ASGITransport(app=admin_app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://test", follow_redirects=False
                ) as client:
                    accepted = await client.post(
                        "/admin/login",
                        data={"username": "admin-user", "password": "a-long-admin-password"},
                    )
                    assert accepted.status_code == 302
                    sessions = await client.get("/admin/ai-session-record/list")
                    assert sessions.status_code == 200
                    assert "AI sessions" in sessions.text

                    edit_form = await client.get(
                        f"/admin/ai-session-record/edit/{state.session_id}"
                    )
                    assert edit_form.status_code == 200
                    assert 'name="owner_user_id"' in edit_form.text
                    assert 'name="session_id"' not in edit_form.text
                    assert 'name="created_at"' not in edit_form.text

                    edited = await client.post(
                        f"/admin/ai-session-record/edit/{state.session_id}",
                        data={
                            "owner_user_id": "admin-edit-after",
                            "status": state.status.value,
                            "machine_information": "",
                            "scenario_id": "",
                            "scenario_version_id": "",
                            "generated_code_path": "",
                            "generated_code_checksum": "",
                            "build_id": "",
                            "build_status": "",
                            "build_progress": "0",
                            "build_repair_attempts": "0",
                            "machine_access": "",
                            "artifact": "",
                            "error_message": "",
                            "updated_at": state.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    )
                    assert edited.status_code == 302, edited.text
                    assert (
                        await repository.get(state.session_id)
                    ).owner_user_id == "admin-edit-after"
        finally:
            async with repository.session_factory.begin() as session:
                await session.execute(
                    delete(AISessionRecord).where(
                        AISessionRecord.session_id == UUID(state.session_id)
                    )
                )
