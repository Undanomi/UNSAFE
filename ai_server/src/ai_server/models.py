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


class AttackObjective(BaseModel):
    objective_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    objective_type: Literal["user_flag", "system_flag"]
    description: str = Field(min_length=1, max_length=4000)


class AttackStep(BaseModel):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    kind: str = Field(min_length=1, max_length=64)
    phase: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=4000)
    requires: list[str] = Field(default_factory=list, max_length=20)
    achieves: list[str] = Field(default_factory=list, max_length=10)
    cve_id: str | None = Field(default=None, pattern=r"^CVE-\d{4}-\d{4,7}$")
    software: str | None = Field(default=None, max_length=200)
    vulnerable_version: str | None = Field(default=None, max_length=200)
    os_compatible: bool | None = None
    compatibility_reason: str | None = Field(default=None, max_length=2000)
    installation_method: str | None = Field(default=None, max_length=500)
    implementation_steps: list[str] = Field(min_length=1, max_length=50)
    references: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_cve_fields(self) -> AttackStep:
        if self.kind == "cve" and not self.cve_id:
            raise ValueError("a cve attack step requires cve_id")
        if self.kind != "cve" and self.cve_id:
            raise ValueError("cve_id is only valid when kind is cve")
        return self


class AttackGraph(BaseModel):
    objectives: list[AttackObjective] = Field(default_factory=list, max_length=10)
    steps: list[AttackStep] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_graph(self) -> AttackGraph:
        objective_ids = [objective.objective_id for objective in self.objectives]
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError("attack objective IDs must be unique")
        objective_types = [objective.objective_type for objective in self.objectives]
        if len(objective_types) != len(set(objective_types)):
            raise ValueError("attack objective types must be unique")

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("attack step IDs must be unique")
        known_steps = set(step_ids)
        known_objectives = set(objective_ids)
        for step in self.steps:
            if len(step.requires) != len(set(step.requires)):
                raise ValueError(f"attack step {step.step_id} has duplicate requirements")
            if len(step.achieves) != len(set(step.achieves)):
                raise ValueError(f"attack step {step.step_id} has duplicate objectives")
            if step.step_id in step.requires:
                raise ValueError(f"attack step {step.step_id} cannot require itself")
            unknown_steps = set(step.requires) - known_steps
            if unknown_steps:
                raise ValueError(
                    f"attack step {step.step_id} has unknown requirements: {sorted(unknown_steps)}"
                )
            unknown_objectives = set(step.achieves) - known_objectives
            if unknown_objectives:
                raise ValueError(
                    f"attack step {step.step_id} has unknown objectives: "
                    f"{sorted(unknown_objectives)}"
                )

        self._validate_acyclic_graph()
        achieved = {objective for step in self.steps for objective in step.achieves}
        missing = known_objectives - achieved
        if missing:
            raise ValueError(f"attack objectives are not achieved by any step: {sorted(missing)}")
        return self

    def _validate_acyclic_graph(self) -> None:
        dependencies = {step.step_id: step.requires for step in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError(f"attack graph contains a cycle at {step_id}")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in dependencies[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in dependencies:
            visit(step_id)


class ScenarioDraft(BaseModel):
    scenario_id: str
    scenario_version_id: str = "v1"
    title: str
    definition: str
    target_os: str = "Ubuntu 26.04"
    attack_graph: AttackGraph


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


class MachineAccess(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)


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
    build_repair_attempts: int = Field(default=0, ge=0)
    machine_access: MachineAccess | None = None
    artifact: Artifact | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CreateMachineRequest(BaseModel):
    scenario_id: str | None = None


class SessionResponse(SessionState):
    scenario_events_url: str
    download_url: str | None = None
