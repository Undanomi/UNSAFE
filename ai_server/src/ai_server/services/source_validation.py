from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from ..models import AttackGraph, ScenarioDraft
from ..scenario_manifest import ScenarioManifest

REQUIRED_FILES = {
    "contents/README.md",
    "contents/scenario_manifest.json",
    "contents/build.sh",
    "contents/scripts/provision.sh",
    "contents/scripts/verify.sh",
}
UNAVAILABLE_PACKAGE_PATTERNS = (
    re.compile(r"unable to locate package\s+([a-z0-9][a-z0-9+.-]*)", re.IGNORECASE),
    re.compile(
        r"package\s+['\"]([a-z0-9][a-z0-9+.-]*)['\"]\s+has no installation candidate",
        re.IGNORECASE,
    ),
    re.compile(
        r"couldn't find any package by (?:glob|regex)\s+['\"]([a-z0-9][a-z0-9+.-]*)['\"]",
        re.IGNORECASE,
    ),
)
MISSING_SYSTEMD_UNIT_PATTERNS = (
    re.compile(
        r"unit\s+([a-z0-9@_.:-]+\.(?:service|socket|timer|target|path|mount))"
        r"\s+does not exist",
        re.IGNORECASE,
    ),
    re.compile(
        r"unit\s+([a-z0-9@_.:-]+\.(?:service|socket|timer|target|path|mount))"
        r"\s+(?:could not be found|not found)",
        re.IGNORECASE,
    ),
)


def validate_source(root: Path, scenario: ScenarioDraft) -> dict:
    checks: list[dict[str, object]] = []

    def add(
        status: str,
        name: str,
        message: str,
    ) -> None:
        check: dict[str, object] = {"status": status, "name": name, "message": message}
        checks.append(check)

    for relative in sorted(REQUIRED_FILES):
        add("pass" if (root / relative).is_file() else "fail", f"required:{relative}", "exists")
    manifest = _load_manifest(root / "contents/scenario_manifest.json", add)
    manifest_schema_valid = False
    if manifest is not None:
        manifest_schema_valid = _validate_manifest(root, manifest, scenario.target_os, add)
        if manifest_schema_valid:
            _validate_attack_graph(manifest, scenario.attack_graph, add)
            _validate_cve_grounding(manifest, scenario.attack_graph, add)
    _validate_password_selection(scenario.attack_graph, add)
    for path in (root / "contents").rglob("*"):
        if path.is_file() and path.suffix.lower() in {".xml", ".pom"}:
            try:
                ET.parse(path)
            except ET.ParseError as error:
                add("fail", f"xml:{path.relative_to(root)}", str(error))
            else:
                add("pass", f"xml:{path.relative_to(root)}", "valid XML")
    failed = sum(check["status"] == "fail" for check in checks)
    return {
        "status": "fail" if failed else "pass",
        "summary": {
            "passed": sum(check["status"] == "pass" for check in checks),
            "failed": failed,
            "warnings": sum(check["status"] == "warn" for check in checks),
        },
        "checks": checks,
    }


def known_failed_resources(repair_history: list[dict]) -> dict[str, list[str]]:
    return {
        "unavailable_apt_packages": sorted(_extract_unavailable_packages(repair_history)),
        "missing_systemd_units": sorted(_extract_missing_systemd_units(repair_history)),
    }


def _load_manifest(path: Path, add) -> dict | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        add("fail", "manifest:json", str(error))
        return None
    if not isinstance(value, dict):
        add("fail", "manifest:json", "root must be an object")
        return None
    add("pass", "manifest:json", "valid JSON object")
    return value


def _validate_manifest(root: Path, manifest: dict, expected_target_os: str, add) -> bool:
    schema_valid = True
    try:
        ScenarioManifest.model_validate(manifest)
    except ValidationError as error:
        schema_valid = False
        for detail in error.errors(include_url=False):
            location = ".".join(str(part) for part in detail["loc"])
            message = detail["msg"]
            if detail["loc"] == ("expected_vulnerabilities",):
                message = "at least one implemented vulnerability entry is required"
            add("fail", f"manifest:schema:{location}", message)
    else:
        add("pass", "manifest:schema", "matches the declared JSON Schema")

    target_os = manifest.get("target_os")
    add(
        "pass" if target_os == expected_target_os else "fail",
        "manifest:target_os",
        f"target_os must exactly match {expected_target_os}",
    )
    required_files = manifest.get("required_files")
    declared_files = set(required_files) if isinstance(required_files, list) else set()
    for required in sorted(REQUIRED_FILES):
        add(
            "pass" if required in declared_files else "fail",
            f"manifest:required_file:{required}",
            "required_files must declare every mandatory source file",
        )
    for item in required_files if isinstance(required_files, list) else []:
        if not isinstance(item, str):
            add("fail", "manifest:file", "path must be a string")
            continue
        path = PurePosixPath(item)
        if path.is_absolute() or ".." in path.parts:
            add("fail", f"manifest:file:{item}", "unsafe path")
            continue
        normalized = path if path.parts[:1] == ("contents",) else PurePosixPath("contents") / path
        exists = root.joinpath(*normalized.parts).is_file()
        add("pass" if exists else "fail", f"manifest:file:{normalized}", "exists")
    return schema_valid


def _validate_password_selection(attack_graph: AttackGraph, add) -> None:
    cracking_steps = [step for step in attack_graph.steps if step.password_cracking is not None]
    if not cracking_steps:
        return

    for step in cracking_steps:
        spec = step.password_cracking
        assert spec is not None
        selection_bound = spec.selection_bound
        add(
            "pass" if selection_bound else "fail",
            f"password_cracking:{step.step_id}:selection_bound",
            (
                "rockyou password was selected after source generation"
                if selection_bound
                else "rockyou password must be selected after source generation"
            ),
        )


def _validate_cve_grounding(manifest: dict, attack_graph: AttackGraph, add) -> None:
    cve_steps = [step for step in attack_graph.steps if step.cve_id]
    if not cve_steps:
        return
    vulnerabilities = manifest.get("expected_vulnerabilities", [])
    indexed = {
        item.get("cve_id"): item
        for item in vulnerabilities
        if isinstance(item, dict) and isinstance(item.get("cve_id"), str)
    }
    for step in cve_steps:
        assert step.cve_id is not None
        item = indexed.get(step.cve_id)
        add(
            "pass" if item is not None else "fail",
            f"cve:{step.cve_id}:manifest_entry",
            "each verified CVE must have an expected_vulnerabilities entry",
        )
        if item is None:
            continue
        official_title = item.get("official_title")
        title_matches = bool(step.cve_title) and official_title == step.cve_title
        add(
            "pass" if title_matches else "fail",
            f"cve:{step.cve_id}:official_title",
            "expected_vulnerabilities.official_title must exactly match the verified CVE title",
        )
        installation_matches = (
            item.get("installation_artifact") == step.installation_artifact
            and item.get("artifact_source") == step.artifact_source
            and item.get("source_build_reason") == step.source_build_reason
        )
        add(
            "pass" if installation_matches else "fail",
            f"cve:{step.cve_id}:installation_strategy",
            (
                "expected_vulnerabilities must preserve installation_artifact, "
                "artifact_source, and source_build_reason from the verified attack graph"
            ),
        )


def _validate_attack_graph(manifest: dict, attack_graph: AttackGraph, add) -> None:
    expected_steps = {
        step.step_id: {
            "kind": step.kind,
            "requires": sorted(step.requires),
            "achieves": sorted(step.achieves),
        }
        for step in attack_graph.steps
    }
    actual_steps = {}
    for item in manifest.get("attack_steps", []):
        if not isinstance(item, dict) or not isinstance(item.get("step_id"), str):
            continue
        requires = item.get("requires")
        achieves = item.get("achieves")
        if not isinstance(requires, list) or not isinstance(achieves, list):
            continue
        actual_steps[item["step_id"]] = {
            "kind": item.get("kind"),
            "requires": sorted(requires),
            "achieves": sorted(achieves),
        }
    add(
        "pass" if actual_steps == expected_steps else "fail",
        "manifest:attack_graph_steps",
        "attack_steps must match the verified attack graph",
    )

    expected_objectives = {
        objective.objective_id: objective.objective_type for objective in attack_graph.objectives
    }
    actual_objectives = {}
    for item in manifest.get("objectives", []):
        if not isinstance(item, dict) or not isinstance(item.get("objective_id"), str):
            continue
        actual_objectives[item["objective_id"]] = item.get("objective_type")
    add(
        "pass" if actual_objectives == expected_objectives else "fail",
        "manifest:attack_graph_objectives",
        "objectives must match the verified attack graph",
    )


def _extract_unavailable_packages(repair_history: list[dict]) -> set[str]:
    history_text = json.dumps(repair_history, ensure_ascii=False)
    return {
        match.group(1).lower()
        for pattern in UNAVAILABLE_PACKAGE_PATTERNS
        for match in pattern.finditer(history_text)
    }


def _extract_missing_systemd_units(repair_history: list[dict]) -> set[str]:
    history_text = json.dumps(repair_history, ensure_ascii=False)
    return {
        match.group(1).lower()
        for pattern in MISSING_SYSTEMD_UNIT_PATTERNS
        for match in pattern.finditer(history_text)
    }
