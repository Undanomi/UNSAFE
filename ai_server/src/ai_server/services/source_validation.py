from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

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
}


def validate_source(root: Path) -> dict:
    checks: list[dict[str, str]] = []

    def add(status: str, name: str, message: str) -> None:
        checks.append({"status": status, "name": name, "message": message})

    for relative in sorted(REQUIRED_FILES):
        add("pass" if (root / relative).is_file() else "fail", f"required:{relative}", "exists")
    manifest = _load_manifest(root / "contents/scenario_manifest.json", add)
    _validate_manifest(root, manifest, add)
    _validate_build(root / "contents/build.sh", add)
    _validate_base_image_compatibility(root / "contents", manifest, add)
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


def _load_manifest(path: Path, add) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        add("fail", "manifest:json", str(error))
        return {}
    if not isinstance(value, dict):
        add("fail", "manifest:json", "root must be an object")
        return {}
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


def _validate_base_image_compatibility(contents: Path, manifest: dict, add) -> None:
    if not contents.is_dir():
        return
    scripts = list(contents.rglob("*.sh"))
    combined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in scripts)
    target_os = str(manifest.get("target_os", "Ubuntu 26.04"))
    unsupported = "ubuntu 26.04" in target_os.lower() and re.search(
        r"\bapt(?:-get)?\s+install\b[^\n]*\btomcat9\b", combined
    )
    add(
        "fail" if unsupported else "pass",
        "base_image:unsupported_apt_packages",
        "tomcat9 is unavailable on the Ubuntu 26.04 base image"
        if unsupported
        else "no known unsupported APT package is requested",
    )
    full_upgrade = re.search(r"\bapt(?:-get)?\s+(?:-\S+\s+)*upgrade\b", combined)
    add(
        "fail" if full_upgrade else "pass",
        "base_image:full_upgrade",
        "full OS upgrades are not allowed during image provisioning"
        if full_upgrade
        else "no full OS upgrade is requested",
    )
