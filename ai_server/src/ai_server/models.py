from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


class SessionStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    GENERATING_SCENARIO = "generating_scenario"
    SCENARIO_READY = "scenario_ready"
    GENERATING_CODE = "generating_code"
    BUILD_QUEUED = "build_queued"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


class MachineInformation(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    visibility: Literal["private", "public", "非公開", "公開"]
    theme: str = Field(min_length=1, max_length=500)
    difficulty: Literal["Very Easy", "Easy", "Medium", "High"]
    operating_system: str = Field(default="Ubuntu 26.04", min_length=1, max_length=100)
    needs_user_flag: bool | None = None
    user_flag_details: str = Field(default="", max_length=4000)
    needs_system_flag: bool | None = None
    system_flag_details: str = Field(default="", max_length=4000)

    @field_validator("operating_system", mode="before")
    @classmethod
    def default_operating_system(cls, value):
        if value is None or not str(value).strip():
            return "Ubuntu 26.04"
        return str(value).strip()

    @model_validator(mode="after")
    def validate_flag_details(self) -> MachineInformation:
        if self.needs_user_flag is True and not self.user_flag_details.strip():
            raise ValueError("user_flag_details is required when needs_user_flag is true")
        if self.needs_system_flag is True and not self.system_flag_details.strip():
            raise ValueError("system_flag_details is required when needs_system_flag is true")
        return self


class CVEInstallationPlan(BaseModel):
    cve_id: str
    role: Literal["initial_access", "privilege_escalation"]
    software: str
    vulnerable_version: str
    os_compatible: bool
    compatibility_reason: str
    installation_method: str | None = None
    installation_steps: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_installation_for_compatible_cve(self) -> CVEInstallationPlan:
        if self.os_compatible and (not self.installation_method or not self.installation_steps):
            raise ValueError("compatible CVE requires installation_method and installation_steps")
        return self


class ScenarioDraft(BaseModel):
    scenario_id: str
    scenario_version_id: str = "v1"
    title: str
    definition: str
    target_os: str = "Ubuntu 26.04"
    initial_cve: str | None = None
    privilege_escalation_cve: str | None = None
    cve_installation: list[CVEInstallationPlan] = Field(default_factory=list)


class SourceFile(BaseModel):
    path: str
    content: str
    mode: Literal["0644", "0755"] = "0644"


class GeneratedSource(BaseModel):
    files: list[SourceFile] = Field(min_length=1, max_length=100)


class SourcePatch(BaseModel):
    files: list[SourceFile] = Field(min_length=1, max_length=50)
    delete_paths: list[str] = Field(default_factory=list, max_length=50)


class Artifact(BaseModel):
    artifact_id: str
    artifact_type: str
    file_name: str
    file_size: int
    checksum: str


class SessionState(BaseModel):
    session_id: str
    owner_user_id: str
    status: SessionStatus = SessionStatus.CREATED
    machine_information: MachineInformation | None = None
    scenario: ScenarioDraft | None = None
    source_path: str | None = None
    source_checksum: str | None = None
    build_id: str | None = None
    build_status: str | None = None
    build_progress: int = 0
    artifact: Artifact | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CreateMachineRequest(BaseModel):
    scenario_id: str | None = None


class SessionResponse(SessionState):
    scenario_events_url: str
    download_url: str | None = None
