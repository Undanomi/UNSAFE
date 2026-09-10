from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_server.models import AttackGraph, AttackStep, GeneratedSource, ScenarioDraft, SourceFile
from ai_server.services.source_archive import InvalidSourceError, SourceArchive


def scenario() -> ScenarioDraft:
    return ScenarioDraft(
        scenario_id="scenario-1",
        title="test",
        definition="test",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="training-step",
                    title="training",
                    kind="custom",
                    phase="initial_access",
                    description="training step",
                    implementation_steps=["provision"],
                )
            ]
        ),
    )


def web_generated_source(
    *,
    complete_checks: bool = True,
    php_path: str = "contents/app/index.php",
    php_mode: str = "0644",
    provision_mode: str = "0755",
) -> GeneratedSource:
    root_check = (
        "body=$(curl -fsSL http://127.0.0.1/); "
        "printf '%s' \"$body\" | grep -q 'SLSG_PORTAL'; "
        "! grep -qi 'Index of' <<<\"$body\""
    )
    permission_check = (
        "namei -l /var/www/html/index.php; runuser -u www-data -- test -r /var/www/html/index.php"
    )
    acceptance_tests = (
        [{"command": root_check}, {"command": permission_check}]
        if complete_checks
        else [{"command": "curl http://localhost"}]
    )
    shell_checks = f"{root_check}\n{permission_check}\n" if complete_checks else "echo ready\n"
    required = [
        "contents/README.md",
        "contents/scenario_manifest.json",
        "contents/build.sh",
        "contents/scripts/provision.sh",
        php_path,
    ]
    manifest = json.dumps(
        {
            "target_os": "Ubuntu 26.04",
            "required_files": required,
            "services": [{"name": "web", "protocol": "http", "port": 80}],
            "acceptance_tests": acceptance_tests,
            "expected_vulnerabilities": ["training-only"],
            "health_checks": acceptance_tests,
            "attack_steps": [
                {
                    "step_id": "training-step",
                    "kind": "custom",
                    "requires": [],
                    "achieves": [],
                }
            ],
            "objectives": [],
        }
    )
    php_content = (
        "#!/usr/bin/php\n<?php echo 'SLSG_PORTAL';\n"
        if "cgi-bin" in php_path
        else "<?php echo 'SLSG_PORTAL';\n"
    )
    return GeneratedSource(
        files=[
            SourceFile(path="contents/README.md", content="test"),
            SourceFile(path="contents/scenario_manifest.json", content=manifest),
            SourceFile(
                path="contents/build.sh",
                content="#!/bin/bash\nset -euo pipefail\nbash ./scripts/provision.sh\n",
                mode="0755",
            ),
            SourceFile(
                path="contents/scripts/provision.sh",
                content=f"#!/bin/bash\nset -euo pipefail\n{shell_checks}",
                mode=provision_mode,
            ),
            SourceFile(path=php_path, content=php_content, mode=php_mode),
        ]
    )


def test_rejects_parent_traversal(tmp_path: Path) -> None:
    generated = GeneratedSource(
        files=[
            SourceFile(path="contents/build.sh", content="#!/bin/sh\n", mode="0755"),
            SourceFile(path="../outside", content="unsafe"),
        ]
    )
    with pytest.raises(InvalidSourceError, match="unsafe generated path"):
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            generated,
        )


def test_accepts_complete_web_entrypoint_and_runtime_permission_checks(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        web_generated_source(),
    )
    assert archive_path.is_file()


def test_generation_manifest_records_pinned_skills(tmp_path: Path) -> None:
    skill_snapshot = {
        "source": [
            {
                "skill_id": "11111111-1111-1111-1111-111111111111",
                "name": "web-sqli",
                "version": 2,
                "checksum": "a" * 64,
                "selection_reason": "attack_step_kind:web_vulnerability",
            }
        ]
    }
    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        web_generated_source(),
        skill_snapshot=skill_snapshot,
    )

    manifest = json.loads((archive_path.parent / "source" / "generation_manifest.json").read_text())
    assert manifest["skills"] == skill_snapshot


def test_rejects_web_source_without_ip_root_quality_checks(tmp_path: Path) -> None:
    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            web_generated_source(complete_checks=False),
        )
    failures = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "web:manifest:application_identity" in failures
    assert "web:manifest:directory_listing" in failures
    assert "web:build:ip_root_entrypoint" in failures
    assert "permissions:build:web_runtime_access" in failures


def test_accepts_negated_curl_pipeline_and_failing_if_directory_checks(
    tmp_path: Path,
) -> None:
    generated = web_generated_source()
    manifest_file = next(
        file for file in generated.files if file.path == "contents/scenario_manifest.json"
    )
    manifest = json.loads(manifest_file.content)
    manifest_root_check = (
        "curl -fsSL http://127.0.0.1/ | grep -q 'SLSG_PORTAL'; "
        "! curl -fsSL http://127.0.0.1/ | grep -qi 'Index of'"
    )
    manifest["acceptance_tests"][0]["command"] = manifest_root_check
    manifest["health_checks"][0]["command"] = manifest_root_check
    manifest_file.content = json.dumps(manifest)

    provision = next(
        file for file in generated.files if file.path == "contents/scripts/provision.sh"
    )
    provision.content = provision.content.replace(
        "! grep -qi 'Index of' <<<\"$body\"",
        (
            "if curl -fsSL http://127.0.0.1/ | grep -qi 'Index of'; then\n"
            "  echo 'directory listing detected' >&2\n"
            "  exit 1\n"
            "fi"
        ),
    )

    archive_path, _ = SourceArchive(tmp_path).create("session", scenario(), generated)
    assert archive_path.is_file()


def test_invalid_manifest_json_reports_only_the_root_parse_error(tmp_path: Path) -> None:
    generated = web_generated_source()
    manifest = next(
        file for file in generated.files if file.path == "contents/scenario_manifest.json"
    )
    manifest.content = r'{"command":"find /tmp -exec test -f {} \;"}'

    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create("session", scenario(), generated)

    failures = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "manifest:json" in failures
    assert "manifest:target_os" not in failures
    assert "manifest:attack_graph_steps" not in failures
    assert "manifest:attack_graph_objectives" not in failures


def test_rejects_non_executable_shell_script(tmp_path: Path) -> None:
    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            web_generated_source(provision_mode="0644"),
        )
    failures = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "permissions:executable:scripts/provision.sh" in failures


def test_rejects_non_executable_cgi_php(tmp_path: Path) -> None:
    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            web_generated_source(php_path="contents/app/cgi-bin/index.php", php_mode="0644"),
        )
    failures = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "permissions:php_cgi:app/cgi-bin/index.php" in failures


def test_rejects_cgi_php_without_shebang(tmp_path: Path) -> None:
    generated = web_generated_source(php_path="contents/app/cgi-bin/index.php", php_mode="0755")
    php = next(file for file in generated.files if file.path.endswith("index.php"))
    php.content = "<?php echo 'SLSG_PORTAL';\n"
    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create("session", scenario(), generated)
    failures = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "permissions:php_cgi:app/cgi-bin/index.php" in failures


def test_rejects_unnecessary_execute_mode_on_non_cgi_php(tmp_path: Path) -> None:
    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            web_generated_source(php_mode="0755"),
        )
    failures = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "permissions:php_source:app/index.php" in failures


def test_requires_build_entrypoint(tmp_path: Path) -> None:
    generated = GeneratedSource(files=[SourceFile(path="contents/README.md", content="test")])
    with pytest.raises(InvalidSourceError, match="generated source validation failed"):
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            generated,
        )


def test_rejects_full_os_upgrade(tmp_path: Path) -> None:
    required = [
        "contents/README.md",
        "contents/scenario_manifest.json",
        "contents/build.sh",
        "contents/scripts/provision.sh",
    ]
    manifest = json.dumps(
        {
            "target_os": "Ubuntu 26.04",
            "required_files": required,
            "services": [{"name": "web", "port": 80}],
            "acceptance_tests": ["curl http://localhost"],
            "expected_vulnerabilities": ["training-only"],
            "health_checks": ["curl http://localhost"],
        }
    )
    generated = GeneratedSource(
        files=[
            SourceFile(path="contents/README.md", content="test"),
            SourceFile(path="contents/scenario_manifest.json", content=manifest),
            SourceFile(
                path="contents/build.sh",
                content="#!/bin/bash\nset -euo pipefail\nbash ./scripts/provision.sh\n",
                mode="0755",
            ),
            SourceFile(
                path="contents/scripts/provision.sh",
                content="#!/bin/bash\nset -euo pipefail\napt-get upgrade -y\n",
                mode="0755",
            ),
        ]
    )
    with pytest.raises(InvalidSourceError, match="base_image"):
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            generated,
        )


def test_rejects_package_previously_reported_as_unavailable(tmp_path: Path) -> None:
    required = [
        "contents/README.md",
        "contents/scenario_manifest.json",
        "contents/build.sh",
        "contents/scripts/provision.sh",
    ]
    manifest = json.dumps(
        {
            "target_os": "Ubuntu 26.04",
            "required_files": required,
            "services": [{"name": "web", "port": 80}],
            "acceptance_tests": ["curl http://localhost"],
            "expected_vulnerabilities": ["training-only"],
            "health_checks": ["curl http://localhost"],
        }
    )
    generated = GeneratedSource(
        files=[
            SourceFile(path="contents/README.md", content="test"),
            SourceFile(path="contents/scenario_manifest.json", content=manifest),
            SourceFile(
                path="contents/build.sh",
                content="#!/bin/bash\nset -euo pipefail\nbash ./scripts/provision.sh\n",
                mode="0755",
            ),
            SourceFile(
                path="contents/scripts/provision.sh",
                content=("#!/bin/bash\nset -euo pipefail\napt-get install -y example-runtime9\n"),
                mode="0755",
            ),
        ]
    )
    repair_history = [
        {
            "attempt": 1,
            "trigger": {
                "kind": "packer_build",
                "error_message": "Unable to locate package example-runtime9",
            },
        }
    ]

    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            generated,
            repair_history=repair_history,
        )

    failed_checks = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "base_image:previously_unavailable_apt_packages" in failed_checks


def test_rejects_systemd_unit_previously_reported_as_missing(tmp_path: Path) -> None:
    required = [
        "contents/README.md",
        "contents/scenario_manifest.json",
        "contents/build.sh",
        "contents/scripts/provision.sh",
    ]
    manifest = json.dumps(
        {
            "target_os": "Ubuntu 26.04",
            "required_files": required,
            "services": [{"name": "web", "port": 80}],
            "acceptance_tests": ["curl http://localhost"],
            "expected_vulnerabilities": ["training-only"],
            "health_checks": ["curl http://localhost"],
        }
    )
    generated = GeneratedSource(
        files=[
            SourceFile(path="contents/README.md", content="test"),
            SourceFile(path="contents/scenario_manifest.json", content=manifest),
            SourceFile(
                path="contents/build.sh",
                content="#!/bin/bash\nset -euo pipefail\nbash ./scripts/provision.sh\n",
                mode="0755",
            ),
            SourceFile(
                path="contents/scripts/provision.sh",
                content=(
                    "#!/bin/bash\nset -euo pipefail\nsystemctl enable example-runtime.service\n"
                ),
                mode="0755",
            ),
        ]
    )
    repair_history = [
        {
            "attempt": 1,
            "trigger": {
                "kind": "packer_build",
                "error_message": (
                    "Failed to enable unit: Unit example-runtime.service does not exist"
                ),
            },
        }
    ]

    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            generated,
            repair_history=repair_history,
        )

    failed_checks = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "base_image:previously_missing_systemd_units" in failed_checks


def test_rejects_manifest_that_does_not_match_attack_graph(tmp_path: Path) -> None:
    required = [
        "contents/README.md",
        "contents/scenario_manifest.json",
        "contents/build.sh",
        "contents/scripts/provision.sh",
    ]
    manifest = json.dumps(
        {
            "target_os": "Ubuntu 26.04",
            "required_files": required,
            "services": [{"name": "web", "port": 80}],
            "acceptance_tests": ["curl http://localhost"],
            "expected_vulnerabilities": ["training-only"],
            "health_checks": ["curl http://localhost"],
            "attack_steps": [
                {
                    "step_id": "different-step",
                    "kind": "custom",
                    "requires": [],
                    "achieves": [],
                }
            ],
            "objectives": [],
        }
    )
    generated = GeneratedSource(
        files=[
            SourceFile(path="contents/README.md", content="test"),
            SourceFile(path="contents/scenario_manifest.json", content=manifest),
            SourceFile(
                path="contents/build.sh",
                content="#!/bin/bash\nset -euo pipefail\nbash ./scripts/provision.sh\n",
                mode="0755",
            ),
            SourceFile(
                path="contents/scripts/provision.sh",
                content="#!/bin/bash\nset -euo pipefail\n",
                mode="0755",
            ),
        ]
    )

    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create("session", scenario(), generated)

    failed_checks = {
        check["name"] for check in captured.value.report["checks"] if check["status"] == "fail"
    }
    assert "manifest:attack_graph_steps" in failed_checks


def test_rejected_candidate_does_not_replace_last_valid_source(tmp_path: Path) -> None:
    required = [
        "contents/README.md",
        "contents/scenario_manifest.json",
        "contents/build.sh",
        "contents/scripts/provision.sh",
    ]
    manifest = json.dumps(
        {
            "target_os": "Ubuntu 26.04",
            "required_files": required,
            "services": [{"name": "ssh", "port": 22}],
            "acceptance_tests": ["test -f /etc/passwd"],
            "expected_vulnerabilities": ["training-only"],
            "health_checks": ["test -f /etc/passwd"],
            "attack_steps": [
                {
                    "step_id": "training-step",
                    "kind": "custom",
                    "requires": [],
                    "achieves": [],
                }
            ],
            "objectives": [],
        }
    )

    def generated(provision: str) -> GeneratedSource:
        return GeneratedSource(
            files=[
                SourceFile(path="contents/README.md", content="test"),
                SourceFile(path="contents/scenario_manifest.json", content=manifest),
                SourceFile(
                    path="contents/build.sh",
                    content="#!/bin/bash\nset -euo pipefail\nbash ./scripts/provision.sh\n",
                    mode="0755",
                ),
                SourceFile(path="contents/scripts/provision.sh", content=provision, mode="0755"),
            ]
        )

    archive = SourceArchive(tmp_path)
    archive_path, _ = archive.create(
        "session",
        scenario(),
        generated("#!/bin/bash\nset -euo pipefail\necho valid\n"),
    )

    with pytest.raises(InvalidSourceError):
        archive.create(
            "session",
            scenario(),
            generated("#!/bin/bash\nset -euo pipefail\napt-get upgrade -y\n"),
        )

    source = archive.load(str(tmp_path / "session" / "v1" / "source"))
    archived = archive.load_archive(archive_path)
    assert source is not None and archived is not None
    assert next(file.content for file in source.files if file.path.endswith("provision.sh")) == (
        "#!/bin/bash\nset -euo pipefail\necho valid\n"
    )
    assert source == archived
