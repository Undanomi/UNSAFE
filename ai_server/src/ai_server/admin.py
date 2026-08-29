from __future__ import annotations

import secrets
from typing import Any

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request

from .config import Settings
from .database import (
    AISessionRecord,
    GenerationJobRecord,
    ScenarioRecord,
    ScenarioVersionRecord,
)
from .models import AttackGraph


class AdminAuthentication(AuthenticationBackend):
    def __init__(self, settings: Settings) -> None:
        assert settings.sqladmin_username is not None
        assert settings.sqladmin_password is not None
        assert settings.sqladmin_session_secret is not None
        super().__init__(
            secret_key=settings.sqladmin_session_secret.get_secret_value(),
            session_cookie="slsg_admin_session",
            same_site="strict",
            https_only=settings.sqladmin_secure_cookies,
            max_age=settings.sqladmin_session_max_age_seconds,
        )
        self.username = settings.sqladmin_username
        self.password = settings.sqladmin_password.get_secret_value()

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        authenticated = secrets.compare_digest(username, self.username) and secrets.compare_digest(
            password, self.password
        )
        if authenticated:
            request.session.clear()
            request.session["sqladmin_authenticated"] = True
        return authenticated

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("sqladmin_authenticated") is True


class EditableModelView(ModelView):
    can_create = False
    can_edit = True
    can_delete = False
    can_import = False
    can_export = True
    can_view_details = True
    page_size = 25
    page_size_options = (25, 50, 100)


class AISessionAdmin(EditableModelView, model=AISessionRecord):
    name = "AI session"
    name_plural = "AI sessions"
    icon = "fa-solid fa-layer-group"
    category = "AI server"
    column_list = (
        AISessionRecord.session_id,
        AISessionRecord.owner_user_id,
        AISessionRecord.status,
        AISessionRecord.scenario_id,
        AISessionRecord.build_status,
        AISessionRecord.build_progress,
        AISessionRecord.build_repair_attempts,
        AISessionRecord.updated_at,
    )
    column_searchable_list = (
        AISessionRecord.owner_user_id,
        AISessionRecord.status,
        AISessionRecord.scenario_id,
    )
    column_sortable_list = (
        AISessionRecord.status,
        AISessionRecord.build_progress,
        AISessionRecord.created_at,
        AISessionRecord.updated_at,
    )
    column_default_sort = (AISessionRecord.updated_at, True)
    column_details_list = "__all__"
    form_excluded_columns = (AISessionRecord.created_at,)


class ScenarioAdmin(EditableModelView, model=ScenarioRecord):
    name = "Scenario"
    name_plural = "Scenarios"
    icon = "fa-solid fa-shield-halved"
    category = "AI server"
    column_list = (
        ScenarioRecord.scenario_id,
        ScenarioRecord.owner_user_id,
        ScenarioRecord.title,
        ScenarioRecord.difficulty,
        ScenarioRecord.status,
        ScenarioRecord.updated_at,
    )
    column_searchable_list = (
        ScenarioRecord.scenario_id,
        ScenarioRecord.owner_user_id,
        ScenarioRecord.title,
        ScenarioRecord.status,
    )
    column_sortable_list = (
        ScenarioRecord.title,
        ScenarioRecord.difficulty,
        ScenarioRecord.status,
        ScenarioRecord.created_at,
        ScenarioRecord.updated_at,
    )
    column_default_sort = (ScenarioRecord.updated_at, True)
    column_details_list = "__all__"
    form_excluded_columns = (ScenarioRecord.created_at,)


class ScenarioVersionAdmin(EditableModelView, model=ScenarioVersionRecord):
    name = "Scenario version"
    name_plural = "Scenario versions"
    icon = "fa-solid fa-code-branch"
    category = "AI server"
    column_list = (
        ScenarioVersionRecord.scenario_id,
        ScenarioVersionRecord.scenario_version_id,
        ScenarioVersionRecord.version,
        ScenarioVersionRecord.target_os,
        ScenarioVersionRecord.created_at,
    )
    column_searchable_list = (
        ScenarioVersionRecord.scenario_id,
        ScenarioVersionRecord.scenario_version_id,
        ScenarioVersionRecord.target_os,
    )
    column_sortable_list = (
        ScenarioVersionRecord.version,
        ScenarioVersionRecord.target_os,
        ScenarioVersionRecord.created_at,
    )
    column_default_sort = (ScenarioVersionRecord.created_at, True)
    column_details_list = "__all__"
    form_excluded_columns = (ScenarioVersionRecord.created_at,)

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        if "attack_graph" in data:
            AttackGraph.model_validate(data["attack_graph"])


class GenerationJobAdmin(EditableModelView, model=GenerationJobRecord):
    name = "Generation job"
    name_plural = "Generation jobs"
    icon = "fa-solid fa-gears"
    category = "AI server"
    column_list = (
        GenerationJobRecord.generation_job_id,
        GenerationJobRecord.session_id,
        GenerationJobRecord.generation_type,
        GenerationJobRecord.status,
        GenerationJobRecord.model_name,
        GenerationJobRecord.started_at,
        GenerationJobRecord.completed_at,
    )
    column_searchable_list = (
        GenerationJobRecord.generation_type,
        GenerationJobRecord.status,
        GenerationJobRecord.model_name,
    )
    column_sortable_list = (
        GenerationJobRecord.generation_type,
        GenerationJobRecord.status,
        GenerationJobRecord.started_at,
        GenerationJobRecord.completed_at,
    )
    column_default_sort = (GenerationJobRecord.started_at, True)
    column_details_list = "__all__"


def configure_sqladmin(app: FastAPI, engine: AsyncEngine, settings: Settings) -> Admin | None:
    if not settings.sqladmin_enabled:
        return None
    admin = Admin(
        app=app,
        engine=engine,
        title=f"{settings.app_name} Admin",
        base_url="/admin",
        authentication_backend=AdminAuthentication(settings),
    )
    for view in (AISessionAdmin, ScenarioAdmin, ScenarioVersionAdmin, GenerationJobAdmin):
        admin.add_view(view)
    return admin
