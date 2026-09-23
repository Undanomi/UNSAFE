from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

NonEmptyString = Annotated[str, Field(min_length=1)]
ManifestPath = Annotated[str, Field(min_length=1, pattern=r"^contents/.+")]
CveId = Annotated[str, Field(pattern=r"^CVE-\d{4}-\d{4,7}$")]


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


class ScenarioManifest(StrictManifestModel):
    target_os: NonEmptyString
    required_files: list[ManifestPath] = Field(min_length=1)
    services: list[ManifestService] = Field(min_length=1)
    acceptance_tests: list[ManifestCommand] = Field(min_length=1)
    expected_vulnerabilities: list[
        ManifestNonCveVulnerability | ManifestCveVulnerability
    ] = Field(min_length=1)
    health_checks: list[ManifestCommand] = Field(min_length=1)
    attack_steps: list[ManifestAttackStep] = Field(min_length=1)
    objectives: list[ManifestObjective]


def scenario_manifest_json_schema() -> str:
    return json.dumps(ScenarioManifest.model_json_schema(), ensure_ascii=False, indent=2)
