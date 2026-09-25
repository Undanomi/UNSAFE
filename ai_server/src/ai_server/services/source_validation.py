from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from pydantic import ValidationError

from ..models import AttackGraph, ScenarioDraft, rockyou_password_placeholder
from ..scenario_manifest import ScenarioManifest
from .scenario_secrets import redact_scenario_flags

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
URL_PATTERN = re.compile(r"https?://[^\s'\"`<>]+", re.IGNORECASE)
LOCAL_TEST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def validate_source(root: Path, scenario: ScenarioDraft) -> dict:
    checks: list[dict[str, object]] = []

    def add(
        status: str,
        name: str,
        message: str,
    ) -> None:
        message = redact_scenario_flags(message, scenario)
        for step in scenario.attack_graph.steps:
            spec = step.password_cracking
            if spec is not None and spec.password:
                message = message.replace(
                    spec.password, rockyou_password_placeholder(step.step_id)
                )
        check: dict[str, object] = {"status": status, "name": name, "message": message}
        checks.append(check)

    for relative in sorted(REQUIRED_FILES):
        add("pass" if (root / relative).is_file() else "fail", f"required:{relative}", "exists")
    manifest = _load_manifest(root / "contents/scenario_manifest.json", add)
    manifest_schema_valid = False
    if manifest is not None:
        manifest_schema_valid = _validate_manifest(root, manifest, scenario.target_os, add)
        if manifest_schema_valid:
            _validate_local_test_commands(manifest, add)
            _validate_attack_graph(manifest, scenario.attack_graph, add)
            _validate_cve_grounding(manifest, scenario.attack_graph, add)
    _validate_password_selection(scenario.attack_graph, add)
    _validate_materialized_password_usage(root, scenario.attack_graph, add)
    _validate_materialized_flag_usage(root, scenario, add)
    _validate_source_syntax(root, add)
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


def _text_files(root: Path):
    for path in sorted((root / "contents").rglob("*")):
        if not path.is_file():
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue


def _validate_materialized_flag_usage(root: Path, scenario: ScenarioDraft, add) -> None:
    configured = {
        "user": scenario.user_flag,
        "system": scenario.system_flag,
    }
    occurrences = {kind: 0 for kind, value in configured.items() if value}
    unsupported_injections: list[str] = []
    injection_pattern = re.compile(
        r"\$(?:\{)?[A-Z][A-Z0-9_]*(?:USER|SYSTEM)_FLAG(?:\b|[:}?])"
        r"|\$(?:\{)?(?:USER|SYSTEM)_FLAG(?:\b|[:}?])"
    )
    for path, content in _text_files(root):
        relative = path.relative_to(root).as_posix()
        if injection_pattern.search(content):
            unsupported_injections.append(relative)
        for kind, value in configured.items():
            if value:
                occurrences[kind] += content.count(value)

    if unsupported_injections:
        add(
            "fail",
            "flags:unsupported_injection",
            (
                "flag environment variables are not injected by the build platform; use the "
                "typed server-managed placeholders in: "
                + ", ".join(sorted(set(unsupported_injections)))
            ),
        )
    for kind, count in occurrences.items():
        add(
            "pass" if count else "fail",
            f"flags:{kind}:materialized",
            (
                "server-managed flag was materialized"
                if count
                else "configured flag is absent from generated source"
            ),
        )


def _validate_source_syntax(root: Path, add) -> None:
    bash = shutil.which("bash")
    for path, content in _text_files(root):
        relative = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix == ".py":
            try:
                ast.parse(content, filename=relative)
            except SyntaxError as error:
                add(
                    "fail",
                    f"preflight:python:{relative}",
                    f"{error.msg} at line {error.lineno}",
                )
            else:
                add("pass", f"preflight:python:{relative}", "valid Python syntax")
        elif suffix == ".json" and path.name != "scenario_manifest.json":
            try:
                json.loads(content)
            except json.JSONDecodeError as error:
                add(
                    "fail",
                    f"preflight:json:{relative}",
                    f"{error.msg} at line {error.lineno} column {error.colno}",
                )
            else:
                add("pass", f"preflight:json:{relative}", "valid JSON")
        elif suffix == ".sh" and bash:
            try:
                result = subprocess.run(
                    [bash, "--noprofile", "--norc", "-n", str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env={"PATH": os.defpath, "LC_ALL": "C"},
                )
            except subprocess.TimeoutExpired:
                add("fail", f"preflight:shell:{relative}", "bash -n timed out")
            else:
                message = (result.stderr or result.stdout).strip()
                add(
                    "pass" if result.returncode == 0 else "fail",
                    f"preflight:shell:{relative}",
                    message or "valid Bash syntax",
                )


def _validate_local_test_commands(manifest: dict, add) -> None:
    external_urls: list[str] = []
    for field in ("health_checks", "acceptance_tests"):
        for check in manifest.get(field, []):
            command = check.get("command", "") if isinstance(check, dict) else ""
            for raw_url in URL_PATTERN.findall(command):
                hostname = (urlsplit(raw_url).hostname or "").casefold()
                if hostname not in LOCAL_TEST_HOSTS:
                    external_urls.append(raw_url)
    add(
        "fail" if external_urls else "pass",
        "manifest:test_network_scope",
        (
            "health and acceptance tests must not fetch external URLs: "
            + ", ".join(sorted(set(external_urls)))
            if external_urls
            else "health and acceptance test URLs are local"
        ),
    )


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
    selected_passwords = [
        spec.password
        for step in cracking_steps
        if (spec := step.password_cracking) is not None and spec.password is not None
    ]
    if len(selected_passwords) == len(cracking_steps):
        unique = len(selected_passwords) == len(set(selected_passwords))
        add(
            "pass" if unique else "fail",
            "password_cracking:selection_unique",
            "each password cracking step must have a distinct server-selected password",
        )


def _validate_materialized_password_usage(root: Path, attack_graph: AttackGraph, add) -> None:
    passwords = {
        spec.password
        for step in attack_graph.steps
        if (spec := step.password_cracking) is not None and spec.password is not None
    }
    if not passwords:
        return

    invalid_comparisons: list[str] = []
    unsupported_injections: list[str] = []
    for path in sorted((root / "contents").rglob("*")):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        if "SLSG_ROCKYOU_PASSWORD" in content:
            unsupported_injections.append(relative)
        for line_number, line in enumerate(content.splitlines(), start=1):
            if any(
                password in line and _looks_like_password_comparison(line, password)
                for password in passwords
            ):
                invalid_comparisons.append(f"{relative}:{line_number}")

    if unsupported_injections:
        add(
            "fail",
            "password_cracking:unsupported_password_injection",
            (
                "SLSG_ROCKYOU_PASSWORD is not injected by the build platform; use only the "
                "server-managed placeholder as credential or hash input in: "
                + ", ".join(unsupported_injections)
            ),
        )
    if invalid_comparisons:
        add(
            "fail",
            "password_cracking:materialized_secret_comparison",
            (
                "the server-selected password must not be used in a comparison, placeholder "
                "guard, grep, case, or assertion; use it only as credential or hash input in: "
                + ", ".join(invalid_comparisons)
            ),
        )
    if not unsupported_injections and not invalid_comparisons:
        add(
            "pass",
            "password_cracking:materialized_secret_usage",
            "server-selected password is not used as a placeholder guard or injected variable",
        )


def _looks_like_password_comparison(line: str, password: str) -> bool:
    if any(operator in line for operator in ("==", "!=", "=~")):
        return True
    prefix = line[: line.find(password)]
    return bool(
        re.search(
            r"(?:^|[;&\s])(?:if|elif|while|until|test|case|grep|assert)\b",
            prefix,
        )
        or re.search(r"(?:^|\s)\[\[?(?:\s|$)", prefix)
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
