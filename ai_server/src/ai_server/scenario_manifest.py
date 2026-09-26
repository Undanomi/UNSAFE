from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonEmptyString = Annotated[str, Field(min_length=1)]
ManifestPath = Annotated[str, Field(min_length=1, pattern=r"^contents/.+")]
CveId = Annotated[str, Field(pattern=r"^CVE-\d{4}-\d{4,7}$")]
LinuxAccount = Annotated[str, Field(pattern=r"^[a-z_][a-z0-9_-]{0,31}$")]


class StrictManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManifestService(StrictManifestModel):
    name: NonEmptyString
    protocol: Literal["http", "https", "tcp", "udp"]
    port: int = Field(ge=1, le=65535)


class ManifestCommand(StrictManifestModel):
    command: NonEmptyString


class ManifestNonCveVulnerability(StrictManifestModel):
    name: NonEmptyString
    description: NonEmptyString


class ManifestCveVulnerability(StrictManifestModel):
    cve_id: CveId
    official_title: NonEmptyString
    description: NonEmptyString
    references: list[NonEmptyString] = Field(min_length=1)
    installation_artifact: Literal[
        "os_repository_package",
        "vendor_repository_package",
        "vendor_release_binary",
        "other_prebuilt",
        "source_build",
    ]
    artifact_source: NonEmptyString
    source_build_reason: NonEmptyString | None


class ManifestAttackStep(StrictManifestModel):
    step_id: NonEmptyString
    kind: NonEmptyString
    requires: list[NonEmptyString]
    achieves: list[NonEmptyString]


class ManifestObjective(StrictManifestModel):
    objective_id: NonEmptyString
    objective_type: Literal["user_flag", "system_flag"]
    description: NonEmptyString


class ManifestFlagPlacement(StrictManifestModel):
    kind: Literal["user", "system"]
    path: NonEmptyString
    owner: LinuxAccount
    group: LinuxAccount
    mode: Literal["0400", "0440", "0600", "0640"] = "0400"

    @field_validator("path")
    @classmethod
    def persistent_absolute_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts or value.endswith("/"):
            raise ValueError("flag path must be an absolute file path without traversal")
        if path == PurePosixPath("/") or path.parts[1:2] in {
            ("dev",),
            ("proc",),
            ("run",),
            ("sys",),
            ("tmp",),
        }:
            raise ValueError("flag path must be on the persistent VM filesystem")
        return value


class ScenarioManifest(StrictManifestModel):
    target_os: NonEmptyString
    required_files: list[ManifestPath] = Field(min_length=1)
    services: list[ManifestService] = Field(min_length=1)
    acceptance_tests: list[ManifestCommand] = Field(min_length=1)
    expected_vulnerabilities: list[ManifestNonCveVulnerability | ManifestCveVulnerability] = Field(
        min_length=1
    )
    health_checks: list[ManifestCommand] = Field(min_length=1)
    attack_steps: list[ManifestAttackStep] = Field(min_length=1)
    objectives: list[ManifestObjective]
    flag_placements: list[ManifestFlagPlacement] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_flag_placement_kinds_and_paths(self) -> ScenarioManifest:
        kinds = [placement.kind for placement in self.flag_placements]
        paths = [placement.path for placement in self.flag_placements]
        if len(kinds) != len(set(kinds)):
            raise ValueError("flag_placements must contain at most one entry per kind")
        if len(paths) != len(set(paths)):
            raise ValueError("user and system flags must use distinct paths")
        return self


def scenario_manifest_json_schema() -> str:
    return json.dumps(ScenarioManifest.model_json_schema(), ensure_ascii=False, indent=2)
