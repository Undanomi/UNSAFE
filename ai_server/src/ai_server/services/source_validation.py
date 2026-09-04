from __future__ import annotations

import json
import re
import stat
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from ..models import AttackGraph

REQUIRED_FILES = {
    "contents/README.md",
    "contents/scenario_manifest.json",
    "contents/build.sh",
    "contents/scripts/provision.sh",
}
MANIFEST_LISTS = {
    "required_files",
    "services",
    "acceptance_tests",
    "expected_vulnerabilities",
    "health_checks",
    "attack_steps",
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
WEB_SERVICE_PORTS = {80, 443, 3000, 8000, 8080, 8443}
WEB_SERVICE_NAMES = {"apache", "caddy", "http", "https", "lighttpd", "nginx", "php", "web"}


def validate_source(
    root: Path, attack_graph: AttackGraph, repair_history: list[dict] | None = None
) -> dict:
    checks: list[dict[str, str]] = []

    def add(status: str, name: str, message: str) -> None:
        checks.append({"status": status, "name": name, "message": message})

    for relative in sorted(REQUIRED_FILES):
        add("pass" if (root / relative).is_file() else "fail", f"required:{relative}", "exists")
    manifest = _load_manifest(root / "contents/scenario_manifest.json", add)
    if manifest is not None:
        _validate_manifest(root, manifest, add)
        _validate_attack_graph(manifest, attack_graph, add)
    _validate_build(root / "contents/build.sh", add)
    _validate_source_modes(root / "contents", add)
    if manifest is not None:
        _validate_web_delivery(root / "contents", manifest, add)
    _validate_base_image_compatibility(root / "contents", repair_history or [], add)
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


def _validate_manifest(root: Path, manifest: dict, add) -> None:
    target_os = manifest.get("target_os")
    add(
        "pass" if isinstance(target_os, str) and target_os.strip() else "fail",
        "manifest:target_os",
        "non-empty target_os required",
    )
    for field in MANIFEST_LISTS:
        value = manifest.get(field)
        status = "pass" if isinstance(value, list) and value else "fail"
        add(status, f"manifest:{field}", "non-empty list required")
    objectives = manifest.get("objectives")
    add(
        "pass" if isinstance(objectives, list) else "fail",
        "manifest:objectives",
        "objectives must be a list",
    )
    for item in manifest.get("required_files", []):
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
    for index, service in enumerate(manifest.get("services", [])):
        valid = isinstance(service, dict) and "name" in service and "port" in service
        add("pass" if valid else "fail", f"manifest:service:{index}", "name and port required")


def _validate_build(path: Path, add) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    add(
        "pass" if "set -euo pipefail" in text else "fail",
        "build:strict_mode",
        "set -euo pipefail required",
    )
    add(
        "pass" if "scripts/provision.sh" in text else "fail",
        "build:provision",
        "scripts/provision.sh reference required",
    )


def _validate_source_modes(contents: Path, add) -> None:
    if not contents.is_dir():
        return
    for path in sorted(contents.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(contents).as_posix()
        mode = stat.S_IMODE(path.stat().st_mode)
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() == ".sh":
            add(
                "pass" if mode & 0o111 and text.startswith("#!") else "fail",
                f"permissions:executable:{relative}",
                f"shell scripts must have a shebang and executable mode; mode is {mode:04o}",
            )
        elif text.startswith("#!"):
            add(
                "pass" if mode & 0o111 else "fail",
                f"permissions:shebang:{relative}",
                f"files with a shebang must be executable; mode is {mode:04o}",
            )
        if path.suffix.lower() == ".php":
            is_cgi_path = "cgi-bin" in {part.lower() for part in path.parts}
            has_shebang = text.startswith("#!")
            if is_cgi_path or has_shebang:
                add(
                    "pass" if has_shebang and mode & 0o111 else "fail",
                    f"permissions:php_cgi:{relative}",
                    f"CGI PHP must have a shebang and executable mode; mode is {mode:04o}",
                )
            else:
                add(
                    "fail" if mode & 0o111 else "pass",
                    f"permissions:php_source:{relative}",
                    f"non-CGI PHP should be readable but not executable; mode is {mode:04o}",
                )


def _validate_web_delivery(contents: Path, manifest: dict, add) -> None:
    if not _has_web_service(manifest):
        return
    manifest_checks = json.dumps(
        {
            "health_checks": manifest.get("health_checks", []),
            "acceptance_tests": manifest.get("acceptance_tests", []),
        },
        ensure_ascii=False,
    )
    shell_checks = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(contents.rglob("*.sh"))
    )
    _validate_web_check_text(manifest_checks, "manifest", add)
    _validate_web_check_text(shell_checks, "build", add)


def _has_web_service(manifest: dict) -> bool:
    for service in manifest.get("services", []):
        if not isinstance(service, dict):
            continue
        name = str(service.get("name", "")).lower()
        protocol = str(service.get("protocol", "")).lower()
        try:
            port = int(service.get("port"))
        except (TypeError, ValueError):
            port = None
        if (
            any(token in name for token in WEB_SERVICE_NAMES)
            or protocol in {"http", "https"}
            or port in WEB_SERVICE_PORTS
        ):
            return True
    return False


def _validate_web_check_text(text: str, location: str, add) -> None:
    lowered = text.lower()
    root_request = bool(
        re.search(
            r"curl\b[^\n]*https?://(?:127\.0\.0\.1|localhost)(?::\d+)?/?(?:[\s'\";|)]|$)",
            text,
            re.IGNORECASE,
        )
    )
    add(
        "pass" if root_request else "fail",
        f"web:{location}:ip_root_entrypoint",
        "numeric/localhost root URL must be requested",
    )
    add(
        "pass" if root_request and "grep" in lowered else "fail",
        f"web:{location}:application_identity",
        "root response must be checked for a scenario-specific marker",
    )
    negative_index_check = _rejects_directory_listing(text)
    add(
        "pass" if negative_index_check else "fail",
        f"web:{location}:directory_listing",
        "root response must explicitly reject 'Index of'",
    )
    permission_tool = any(token in lowered for token in ("namei ", "stat ", "test -r", "test -x"))
    runtime_identity = any(token in lowered for token in ("runuser ", "sudo -u ", "su -s "))
    add(
        "pass" if permission_tool and runtime_identity else "fail",
        f"permissions:{location}:web_runtime_access",
        "web runtime user readability/traversal and deployed modes must be checked",
    )


def _rejects_directory_listing(text: str) -> bool:
    lowered = text.lower()
    if "index of" not in lowered:
        return False
    if "must_not_contain" in lowered:
        return True
    if re.search(r"\bgrep\b[^\n;&]*(?:-[a-z]*v[a-z]*\b)[^\n;&]*index of", lowered):
        return True
    if re.search(
        r"(?:^|&&|\|\||;)\s*!\s*[^\n;&]*\bgrep\b[^\n;&]*index of",
        lowered,
    ):
        return True
    return bool(
        re.search(
            r"\bif\s+[^;\n]*\bgrep\b[^;\n]*index of[^;\n]*;\s*then"
            r"(?:(?!\bfi\b).)*\bexit\s+[1-9][0-9]*\b(?:(?!\bfi\b).)*\bfi\b",
            lowered,
            re.DOTALL,
        )
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


def _validate_base_image_compatibility(contents: Path, repair_history: list[dict], add) -> None:
    if not contents.is_dir():
        return
    scripts = list(contents.rglob("*.sh"))
    combined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in scripts)
    shell_lines = combined.replace("\\\n", " ")
    install_commands = "\n".join(
        match.group(0)
        for match in re.finditer(r"\bapt(?:-get)?\s+(?:-\S+\s+)*install\b[^\n]*", shell_lines)
    )
    systemctl_commands = "\n".join(
        match.group(0) for match in re.finditer(r"\bsystemctl\b[^\n]*", shell_lines)
    )
    unavailable_packages = _extract_unavailable_packages(repair_history)
    repeated_packages = [
        package
        for package in sorted(unavailable_packages)
        if re.search(
            rf"(?<![a-z0-9+.-]){re.escape(package)}(?![a-z0-9+.-])",
            install_commands,
            re.IGNORECASE,
        )
    ]
    add(
        "fail" if repeated_packages else "pass",
        "base_image:previously_unavailable_apt_packages",
        f"previously unavailable APT packages are requested: {', '.join(repeated_packages)}"
        if repeated_packages
        else "no package previously reported as unavailable is requested",
    )
    missing_units = _extract_missing_systemd_units(repair_history)
    repeated_units = [
        unit
        for unit in sorted(missing_units)
        if re.search(
            rf"(?<![a-z0-9@_.:-]){re.escape(unit)}(?![a-z0-9@_.:-])",
            systemctl_commands,
            re.IGNORECASE,
        )
    ]
    add(
        "fail" if repeated_units else "pass",
        "base_image:previously_missing_systemd_units",
        f"previously missing systemd units are requested: {', '.join(repeated_units)}"
        if repeated_units
        else "no systemd unit previously reported as missing is requested",
    )
    full_upgrade = re.search(r"\bapt(?:-get)?\s+(?:-\S+\s+)*upgrade\b", combined)
    add(
        "fail" if full_upgrade else "pass",
        "base_image:full_upgrade",
        "full OS upgrades are not allowed during image provisioning"
        if full_upgrade
        else "no full OS upgrade is requested",
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
