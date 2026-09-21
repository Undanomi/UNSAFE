from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from fastapi import FastAPI
from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request
from wtforms import SelectField
from wtforms.validators import Length, NumberRange

from .config import AdminSettings
from .database import (
    AISessionRecord,
    ScenarioRecord,
    ScenarioVersionRecord,
    SessionSkillPlanRecord,
    SessionSkillSnapshotItemRecord,
    SessionSkillSnapshotRecord,
    SkillRecord,
    SkillVersionRecord,
)
from .models import (
    Artifact,
    AttackGraph,
    MachineAccess,
    MachineInformation,
    SessionStatus,
    utcnow,
)
from .skills.models import SkillCreate, SkillStatus


@dataclass(frozen=True)
class RuntimeLimit:
    setting: str
    environment: str
    label: str
    allowed: str
    description: str


RUNTIME_LIMITS = (
    RuntimeLimit(
        "gemini_max_output_tokens",
        "GEMINI_MAX_OUTPUT_TOKENS",
        "Gemini output tokens",
        "1,024–65,536",
        "Maximum output tokens requested from Gemini.",
    ),
    RuntimeLimit(
        "generation_retries",
        "GENERATION_RETRIES",
        "AI structured-output retries",
        "1–10",
        "Retries used inside one generation, repair, synchronization, or review operation.",
    ),
    RuntimeLimit(
        "cve_min_year",
        "CVE_MIN_YEAR",
        "Minimum CVE year",
        "1,999–2,100",
        "Oldest CVE publication year accepted by skill selection.",
    ),
    RuntimeLimit(
        "scenario_generation_attempts",
        "SCENARIO_GENERATION_ATTEMPTS",
        "Scenario generation attempts",
        "1–10",
        "Maximum generation and review attempts for one scenario.",
    ),
    RuntimeLimit(
        "source_generation_attempts",
        "SOURCE_GENERATION_ATTEMPTS",
        "Source generation attempts",
        "1–5",
        "Validation and repair attempts available within each build slot.",
    ),
    RuntimeLimit(
        "scenario_sync_attempts",
        "SCENARIO_SYNC_ATTEMPTS",
        "Scenario synchronization attempts",
        "1–10",
        "Scenario-text synchronization and semantic-review attempts after a source repair.",
    ),
    RuntimeLimit(
        "ai_timeout_seconds",
        "AI_TIMEOUT_SECONDS",
        "AI timeout",
        "> 0 seconds",
        "Overall timeout used for AI provider requests.",
    ),
    RuntimeLimit(
        "build_timeout_seconds",
        "BUILD_TIMEOUT_SECONDS",
        "Build API timeout",
        "> 0 seconds",
        "HTTP timeout used for build server requests.",
    ),
    RuntimeLimit(
        "build_repair_max_attempts",
        "BUILD_REPAIR_MAX_ATTEMPTS",
        "Build repair attempts",
        "0–10",
        "Automatic repair builds added to each explicitly started cycle.",
    ),
    RuntimeLimit(
        "download_url_ttl_seconds",
        "DOWNLOAD_URL_TTL_SECONDS",
        "Download URL lifetime",
        "60–86,400 seconds",
        "Lifetime of an artifact download URL.",
    ),
    RuntimeLimit(
        "scenario_chunk_size",
        "SCENARIO_CHUNK_SIZE",
        "Scenario event chunk size",
        "1–4,096 characters",
        "Maximum text size emitted in one scenario stream event.",
    ),
    RuntimeLimit(
        "skills_max_active",
        "SKILLS_MAX_ACTIVE",
        "Active Skills",
        "1–100",
        "Maximum active Skill versions loaded into the selection catalog.",
    ),
    RuntimeLimit(
        "skills_max_per_phase",
        "SKILLS_MAX_PER_PHASE",
        "Skills per phase",
        "1–20",
        "Maximum Skills selected for one generation phase.",
    ),
    RuntimeLimit(
        "skill_context_max_chars",
        "SKILL_CONTEXT_MAX_CHARS",
        "Skill context size",
        "1,000–200,000 characters",
        "Maximum rendered Skill context for one phase.",
    ),
    RuntimeLimit(
        "skill_selection_max_chars",
        "SKILL_SELECTION_MAX_CHARS",
        "Skill catalog size",
        "1,000–300,000 characters",
        "Maximum catalog size passed to semantic Skill selection.",
    ),
    RuntimeLimit(
        "skill_selection_retries",
        "SKILL_SELECTION_RETRIES",
        "Skill selection retries",
        "1–3",
        "Maximum attempts to obtain a valid semantic selection.",
    ),
    RuntimeLimit(
        "skill_selection_max_cves",
        "SKILL_SELECTION_MAX_CVES",
        "Selected CVEs",
        "1–10",
        "Maximum CVE references selected for one scenario.",
    ),
)


def _choices(values) -> list[tuple[str, str]]:
    return [(item.value, item.value) for item in values]


def _validate_checksum(value: str | None, field_name: str) -> None:
    if value not in (None, "") and not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 checksum")


def _runtime_limit_rows(settings: AdminSettings) -> list[dict[str, Any]]:
    return [
        {
            "environment": limit.environment,
            "label": limit.label,
            "value": getattr(settings, limit.setting),
            "allowed": limit.allowed,
            "description": limit.description,
        }
        for limit in RUNTIME_LIMITS
    ]


class RuntimeLimitsAdmin(BaseView):
    name = "Runtime limits"
    icon = "fa-solid fa-gauge-high"
    category = "AI server"
    settings: ClassVar[AdminSettings]

    @expose("/runtime-limits", methods=["GET"], identity="runtime-limits")
    async def limits(self, request: Request):
        return await self.templates.TemplateResponse(
            request,
            "runtime_limits.html",
            {
                "title": "AI server runtime limits",
                "subtitle": "Current non-secret settings (read only; restart to apply changes)",
                "rows": _runtime_limit_rows(self.settings),
            },
        )


class AdminAuthentication(AuthenticationBackend):
    def __init__(self, settings: AdminSettings) -> None:
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


class ReadOnlyModelView(EditableModelView):
    can_edit = False


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
        AISessionRecord.scenario_generation_attempts,
        AISessionRecord.scenario_generation_attempt_limit,
        AISessionRecord.source_generation_attempts,
        AISessionRecord.source_generation_attempt_limit,
        AISessionRecord.scenario_sync_attempts,
        AISessionRecord.scenario_sync_attempt_limit,
        AISessionRecord.build_status,
        AISessionRecord.build_progress,
        AISessionRecord.build_repair_attempts,
        AISessionRecord.build_repair_attempt_limit,
        AISessionRecord.updated_at,
    )
    column_searchable_list = (
        AISessionRecord.owner_user_id,
        AISessionRecord.status,
        AISessionRecord.scenario_id,
    )
    column_sortable_list = (
        AISessionRecord.status,
        AISessionRecord.scenario_generation_attempts,
        AISessionRecord.scenario_generation_attempt_limit,
        AISessionRecord.source_generation_attempts,
        AISessionRecord.source_generation_attempt_limit,
        AISessionRecord.scenario_sync_attempts,
        AISessionRecord.scenario_sync_attempt_limit,
        AISessionRecord.build_progress,
        AISessionRecord.build_repair_attempts,
        AISessionRecord.build_repair_attempt_limit,
        AISessionRecord.created_at,
        AISessionRecord.updated_at,
    )
    column_default_sort = (AISessionRecord.updated_at, True)
    column_details_list = "__all__"
    form_excluded_columns = (AISessionRecord.created_at,)
    form_overrides: ClassVar = {"status": SelectField}
    form_args: ClassVar = {
        "status": {"choices": _choices(SessionStatus)},
        "scenario_generation_attempts": {"validators": [NumberRange(min=0)]},
        "scenario_generation_attempt_limit": {"validators": [NumberRange(min=0)]},
        "source_generation_attempts": {"validators": [NumberRange(min=0)]},
        "source_generation_attempt_limit": {"validators": [NumberRange(min=0)]},
        "scenario_sync_attempts": {"validators": [NumberRange(min=0)]},
        "scenario_sync_attempt_limit": {"validators": [NumberRange(min=0)]},
        "build_progress": {"validators": [NumberRange(min=0, max=100)]},
        "build_repair_attempts": {"validators": [NumberRange(min=0)]},
        "build_repair_attempt_limit": {"validators": [NumberRange(min=0)]},
    }
    form_widget_args: ClassVar = {
        "scenario_generation_attempts": {"min": 0},
        "scenario_generation_attempt_limit": {"min": 0},
        "source_generation_attempts": {"min": 0},
        "source_generation_attempt_limit": {"min": 0},
        "scenario_sync_attempts": {"min": 0},
        "scenario_sync_attempt_limit": {"min": 0},
        "build_progress": {"min": 0, "max": 100},
        "build_repair_attempts": {"min": 0},
        "build_repair_attempt_limit": {"min": 0},
    }

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        if "status" in data:
            SessionStatus(data["status"])
        if data.get("machine_information") is not None:
            MachineInformation.model_validate(data["machine_information"])
        if data.get("machine_access") is not None:
            MachineAccess.model_validate(data["machine_access"])
        if data.get("artifact") is not None:
            Artifact.model_validate(data["artifact"])
        if "build_progress" in data and not 0 <= data["build_progress"] <= 100:
            raise ValueError("build_progress must be between 0 and 100")
        for field_name in (
            "scenario_generation_attempts",
            "scenario_generation_attempt_limit",
            "source_generation_attempts",
            "source_generation_attempt_limit",
            "scenario_sync_attempts",
            "scenario_sync_attempt_limit",
            "build_repair_attempts",
            "build_repair_attempt_limit",
        ):
            if field_name in data and data[field_name] < 0:
                raise ValueError(f"{field_name} must not be negative")
        _validate_checksum(data.get("generated_code_checksum"), "generated_code_checksum")


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
    form_overrides: ClassVar = {"difficulty": SelectField}
    form_args: ClassVar = {
        "title": {"validators": [Length(min=1, max=40)]},
        "description": {"validators": [Length(max=1000)]},
        "difficulty": {
            "choices": [(item, item) for item in ("Very Easy", "Easy", "Medium", "High")]
        },
        "current_version": {"validators": [NumberRange(min=1)]},
    }
    form_widget_args: ClassVar = {"current_version": {"min": 1}}

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        if "title" in data and not 1 <= len(data["title"].strip()) <= 40:
            raise ValueError("title must contain between 1 and 40 characters")
        if "description" in data and len(data["description"]) > 1000:
            raise ValueError("description must not exceed 1000 characters")
        if "difficulty" in data and data["difficulty"] not in {
            "Very Easy",
            "Easy",
            "Medium",
            "High",
        }:
            raise ValueError("unsupported difficulty")
        if "current_version" in data and data["current_version"] < 1:
            raise ValueError("current_version must be positive")


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
    form_args: ClassVar = {
        "version": {"validators": [NumberRange(min=1)]},
        "scenario_definition": {"validators": [Length(min=1, max=12000)]},
    }
    form_widget_args: ClassVar = {"version": {"min": 1}}

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        if "attack_graph" in data:
            AttackGraph.model_validate(data["attack_graph"])
        if "target_os" in data:
            MachineInformation(
                name="admin-validation",
                visibility="private",
                theme="admin-validation",
                difficulty="Easy",
                operating_system=data["target_os"],
            )
        if "version" in data and data["version"] < 1:
            raise ValueError("version must be positive")
        if "scenario_definition" in data:
            definition_length = len(data["scenario_definition"].strip())
            if not 1 <= definition_length <= 12000:
                raise ValueError("scenario_definition must contain 1 to 12000 characters")
        _validate_checksum(data.get("generated_code_checksum"), "generated_code_checksum")


class SkillAdmin(EditableModelView, model=SkillRecord):
    name = "Skill"
    name_plural = "Skills"
    icon = "fa-solid fa-wand-magic-sparkles"
    category = "Skills"
    column_list = (
        SkillRecord.skill_id,
        SkillRecord.name,
        SkillRecord.status,
        SkillRecord.current_version,
        SkillRecord.updated_at,
    )
    column_searchable_list = (SkillRecord.name, SkillRecord.description, SkillRecord.status)
    column_sortable_list = (
        SkillRecord.name,
        SkillRecord.status,
        SkillRecord.current_version,
        SkillRecord.created_at,
        SkillRecord.updated_at,
    )
    column_default_sort = (SkillRecord.name, False)
    column_details_list = "__all__"
    form_excluded_columns = (
        SkillRecord.current_version,
        SkillRecord.created_at,
        SkillRecord.updated_at,
    )
    form_overrides: ClassVar = {"status": SelectField}
    form_args: ClassVar = {
        "name": {"validators": [Length(min=1, max=64)]},
        "description": {"validators": [Length(min=1, max=2000)]},
        "status": {"choices": _choices(SkillStatus)},
    }

    async def on_model_change(
        self, data: dict, model: SkillRecord, is_created: bool, request: Request
    ) -> None:
        SkillCreate(
            name=data.get("name", model.name),
            description=data.get("description", model.description),
        )
        status = SkillStatus(data.get("status", model.status))
        if status is SkillStatus.ACTIVE and model.current_version is None:
            raise ValueError("a Skill without a published version cannot be active")
        data["updated_at"] = utcnow()


class SkillVersionAdmin(ReadOnlyModelView, model=SkillVersionRecord):
    name = "Skill version"
    name_plural = "Skill versions"
    icon = "fa-solid fa-code-branch"
    category = "Skills"
    column_list = (
        SkillVersionRecord.skill_id,
        SkillVersionRecord.version,
        SkillVersionRecord.phases,
        SkillVersionRecord.priority,
        SkillVersionRecord.created_by,
        SkillVersionRecord.published_at,
    )
    column_searchable_list = (SkillVersionRecord.created_by,)
    column_sortable_list = (
        SkillVersionRecord.version,
        SkillVersionRecord.priority,
        SkillVersionRecord.created_at,
        SkillVersionRecord.published_at,
    )
    column_default_sort = (SkillVersionRecord.created_at, True)
    column_details_list = "__all__"


class SessionSkillPlanAdmin(ReadOnlyModelView, model=SessionSkillPlanRecord):
    name = "Session Skill plan"
    name_plural = "Session Skill plans"
    icon = "fa-solid fa-list-check"
    category = "Skills"
    column_list = (SessionSkillPlanRecord.session_id, SessionSkillPlanRecord.plan)
    column_details_list = "__all__"


class SessionSkillSnapshotAdmin(ReadOnlyModelView, model=SessionSkillSnapshotRecord):
    name = "Session Skill snapshot"
    name_plural = "Session Skill snapshots"
    icon = "fa-solid fa-camera"
    category = "Skills"
    column_list = (
        SessionSkillSnapshotRecord.session_id,
        SessionSkillSnapshotRecord.phase,
        SessionSkillSnapshotRecord.resolved_at,
    )
    column_searchable_list = (SessionSkillSnapshotRecord.phase,)
    column_sortable_list = (
        SessionSkillSnapshotRecord.phase,
        SessionSkillSnapshotRecord.resolved_at,
    )
    column_default_sort = (SessionSkillSnapshotRecord.resolved_at, True)
    column_details_list = "__all__"


class SessionSkillSnapshotItemAdmin(ReadOnlyModelView, model=SessionSkillSnapshotItemRecord):
    name = "Session Skill snapshot item"
    name_plural = "Session Skill snapshot items"
    icon = "fa-solid fa-puzzle-piece"
    category = "Skills"
    column_list = (
        SessionSkillSnapshotItemRecord.session_id,
        SessionSkillSnapshotItemRecord.phase,
        SessionSkillSnapshotItemRecord.position,
        SessionSkillSnapshotItemRecord.skill_id,
        SessionSkillSnapshotItemRecord.skill_version,
        SessionSkillSnapshotItemRecord.selection_reason,
    )
    column_searchable_list = (
        SessionSkillSnapshotItemRecord.phase,
        SessionSkillSnapshotItemRecord.selection_reason,
    )
    column_sortable_list = (
        SessionSkillSnapshotItemRecord.phase,
        SessionSkillSnapshotItemRecord.position,
        SessionSkillSnapshotItemRecord.skill_version,
    )
    column_default_sort = (SessionSkillSnapshotItemRecord.position, False)
    column_details_list = "__all__"


def configure_sqladmin(app: FastAPI, engine: AsyncEngine, settings: AdminSettings) -> Admin:
    configured_limits_view = type(
        "ConfiguredRuntimeLimitsAdmin",
        (RuntimeLimitsAdmin,),
        {"settings": settings},
    )
    admin = Admin(
        app=app,
        engine=engine,
        title=f"{settings.app_name} Admin",
        base_url="/admin",
        templates_dir=str(Path(__file__).with_name("templates")),
        authentication_backend=AdminAuthentication(settings),
    )
    admin.add_base_view(configured_limits_view)
    for view in (
        AISessionAdmin,
        ScenarioAdmin,
        ScenarioVersionAdmin,
        SkillAdmin,
        SkillVersionAdmin,
        SessionSkillPlanAdmin,
        SessionSkillSnapshotAdmin,
        SessionSkillSnapshotItemAdmin,
    ):
        admin.add_view(view)
    return admin
