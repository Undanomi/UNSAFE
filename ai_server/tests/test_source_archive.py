from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ai_server.models import (
    ROCKYOU_PASSWORD_PLACEHOLDER,
    AttackGraph,
    AttackStep,
    GeneratedSource,
    PasswordCrackingSpec,
    ScenarioDraft,
    SourceFile,
)
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


def cve_scenario() -> ScenarioDraft:
    return ScenarioDraft(
        scenario_id="scenario-cve",
        title="CVE test",
        definition="official CVE test",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="training-step",
                    title="CVE-2026-1234: Official test vulnerability",
                    kind="cve",
                    phase="initial_access",
                    description="Official vulnerability mechanism.",
                    cve_id="CVE-2026-1234",
                    cve_title="Official test vulnerability",
                    cve_description="Official vulnerability mechanism.",
                    cwe_ids=["CWE-79"],
                    installation_artifact="vendor_release_binary",
                    artifact_source="official vendor release",
                    implementation_steps=["Provision the exact official mechanism"],
                )
            ]
        ),
    )


def password_cracking_scenario() -> ScenarioDraft:
    return ScenarioDraft(
        scenario_id="scenario-password-cracking",
        title="Password cracking test",
        definition="Generate the MD5 credential during provisioning.",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="training-step",
                    title="Crack database password",
                    kind="password_cracking",
                    phase="initial_access",
                    description="Crack the extracted training credential.",
                    implementation_steps=["Generate the hash with PHP while provisioning"],
                    password_cracking=PasswordCrackingSpec(
                        wordlist="rockyou.txt",
                        password="22062531",
                        line_number=150_000,
                        search_space_lines=200_000,
                        hash_algorithm="MD5",
                        hash_runtime="php",
                        hash_api="md5",
                        hashcat_mode=0,
                        target_crack_seconds=150,
                    ),
                )
            ]
        ),
    )


def cve_generated_source(*, simulated: bool = False) -> GeneratedSource:
    generated = web_generated_source()
    manifest_file = next(
        file for file in generated.files if file.path == "contents/scenario_manifest.json"
    )
    manifest = json.loads(manifest_file.content)
    manifest["attack_steps"][0]["kind"] = "cve"
    manifest["expected_vulnerabilities"] = [
        {
            "cve_id": "CVE-2026-1234",
            "official_title": "Official test vulnerability",
            "description": "Official vulnerability mechanism.",
            "references": ["https://www.cve.org/CVERecord?id=CVE-2026-1234"],
            "installation_artifact": "vendor_release_binary",
            "artifact_source": "official vendor release",
            "source_build_reason": None,
        }
    ]
    manifest_file.content = json.dumps(manifest)
    if simulated:
        readme = next(file for file in generated.files if file.path == "contents/README.md")
        readme.content = "CVE-2026-1234 is implemented as a simulated vulnerability."
    return generated


def web_generated_source(
    *,
    complete_checks: bool = True,
    php_path: str = "contents/app/index.php",
    php_mode: str = "0644",
    provision_mode: str = "0755",
) -> GeneratedSource:
    root_check = (
        "body=$(curl -fsSL http://127.0.0.1/); printf '%s' \"$body\" | grep -q 'SLSG_PORTAL'"
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
        "contents/scripts/verify.sh",
        php_path,
    ]
    manifest = json.dumps(
        {
            "target_os": "Debian 13.7.0",
            "required_files": required,
            "services": [{"name": "web", "protocol": "http", "port": 80}],
            "acceptance_tests": acceptance_tests,
            "expected_vulnerabilities": [
                {"name": "training-only", "description": "Intentional training weakness"}
            ],
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


def test_accepts_web_checks_without_directory_listing_policy(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        web_generated_source(),
    )
    assert archive_path.is_file()


def test_rejects_service_outside_the_manifest_schema(tmp_path: Path) -> None:
    generated = web_generated_source()
    manifest_file = next(
        source_file
        for source_file in generated.files
        if source_file.path == "contents/scenario_manifest.json"
    )
    manifest = json.loads(manifest_file.content)
    manifest["services"] = [{"service": "web", "ports": [80]}]
    manifest_file.content = json.dumps(manifest)

    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create("session-invalid-service", scenario(), generated)

    failure = next(
        check
        for check in captured.value.report["checks"]
        if check["name"] == "manifest:schema:services.0.name"
    )
    assert failure["message"] == "Field required"


def test_rejects_empty_expected_vulnerabilities_with_specific_message(tmp_path: Path) -> None:
    generated = web_generated_source()
    manifest_file = next(
        source_file
        for source_file in generated.files
        if source_file.path == "contents/scenario_manifest.json"
    )
    manifest = json.loads(manifest_file.content)
    manifest["expected_vulnerabilities"] = []
    manifest_file.content = json.dumps(manifest)

    with pytest.raises(InvalidSourceError) as captured:
        SourceArchive(tmp_path).create("session-empty-vulnerabilities", scenario(), generated)

    failure = next(
        check
        for check in captured.value.report["checks"]
        if check["name"] == "manifest:schema:expected_vulnerabilities"
    )
    assert failure["message"] == "at least one implemented vulnerability entry is required"


def password_cracking_source(provision_line: str) -> GeneratedSource:
    generated = web_generated_source()
    for source_file in generated.files:
        if source_file.path == "contents/scripts/provision.sh":
            source_file.content += provision_line + "\n"
        if source_file.path == "contents/scenario_manifest.json":
            manifest = json.loads(source_file.content)
            manifest["attack_steps"][0]["kind"] = "password_cracking"
            source_file.content = json.dumps(manifest)
    return generated


def test_digest_shaped_package_checksum_does_not_trigger_password_rejection(
    tmp_path: Path,
) -> None:
    generated = password_cracking_source(
        "PACKAGE_SHA256='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'\n"
        f"PASSWORD_HASH=$(php -r \"echo md5('{ROCKYOU_PASSWORD_PLACEHOLDER}');\"); "
        "mysql -e \"INSERT INTO users VALUES ('webuser', '$PASSWORD_HASH')\""
    )

    archive_path, _ = SourceArchive(tmp_path).create(
        "session-package-checksum",
        password_cracking_scenario(),
        generated,
    )
    assert archive_path.is_file()


def test_digest_shaped_value_in_extensionless_file_is_not_a_hard_error(tmp_path: Path) -> None:
    generated = password_cracking_source(
        f"PASSWORD_HASH=$(php -r \"echo md5('{ROCKYOU_PASSWORD_PLACEHOLDER}');\")"
    )
    generated.files.append(
        SourceFile(
            path="contents/config/credential-seed",
            content="password_hash=78b1d9603099c2793139268f635606df\n",
        )
    )
    manifest_file = next(
        source_file
        for source_file in generated.files
        if source_file.path == "contents/scenario_manifest.json"
    )
    manifest = json.loads(manifest_file.content)
    manifest["required_files"].append("contents/config/credential-seed")
    manifest_file.content = json.dumps(manifest)

    archive_path, _ = SourceArchive(tmp_path).create(
        "session-extensionless-hash",
        password_cracking_scenario(),
        generated,
    )
    assert archive_path.is_file()


def test_accepts_runtime_generated_selected_password_hash(tmp_path: Path) -> None:
    generated = password_cracking_source(
        f"PASSWORD_HASH=$(php -r \"echo md5('{ROCKYOU_PASSWORD_PLACEHOLDER}');\"); "
        "mysql -e \"INSERT INTO users VALUES ('webuser', '$PASSWORD_HASH')\""
    )

    archive_path, _ = SourceArchive(tmp_path).create(
        "session-runtime-hash",
        password_cracking_scenario(),
        generated,
    )

    assert archive_path.is_file()
    with zipfile.ZipFile(archive_path) as archive:
        provision = archive.read("contents/scripts/provision.sh").decode()
    assert ROCKYOU_PASSWORD_PLACEHOLDER not in provision
    assert "22062531" in provision


def test_does_not_statically_parse_runtime_hash_generation(tmp_path: Path) -> None:
    generated = password_cracking_source(
        f"PASSWORD='{ROCKYOU_PASSWORD_PLACEHOLDER}'\n"
        'PASSWORD_HASH=$(php /tmp/scenario/contents/scripts/hash-password.php "$PASSWORD")'
    )
    generated.files.append(
        SourceFile(
            path="contents/scripts/hash-password.php",
            content="<?php echo md5($argv[1]);\n",
        )
    )
    manifest_file = next(
        source_file
        for source_file in generated.files
        if source_file.path == "contents/scenario_manifest.json"
    )
    manifest = json.loads(manifest_file.content)
    manifest["required_files"].append("contents/scripts/hash-password.php")
    manifest_file.content = json.dumps(manifest)

    archive_path, _ = SourceArchive(tmp_path).create(
        "session-helper-runtime-hash",
        password_cracking_scenario(),
        generated,
    )

    with zipfile.ZipFile(archive_path) as archive:
        report = json.loads(archive.read("validation_report.json"))
    assert all(
        not check["name"].endswith(":runtime_hash_generation")
        for check in report["checks"]
    )


def test_accepts_source_grounded_in_official_cve_facts(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session-cve",
        cve_scenario(),
        cve_generated_source(),
    )
    assert archive_path.is_file()


def test_static_validation_does_not_infer_cve_semantics_from_prose(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session-cve",
        cve_scenario(),
        cve_generated_source(simulated=True),
    )
    assert archive_path.is_file()


def test_static_validation_does_not_compare_embedded_flag_literals(tmp_path: Path) -> None:
    expected = "flag{user_a1d51d7f803f51f0356f3e547c842a0b}"
    mismatched = expected.upper()
    flag_scenario = scenario().model_copy(update={"user_flag": expected})
    generated = web_generated_source()
    for source_file in generated.files:
        if source_file.path == "contents/scripts/provision.sh":
            source_file.content += f"printf '%s\\n' '{mismatched}' > /home/user/user.txt\n"
        if source_file.path == "contents/scenario_manifest.json":
            manifest = json.loads(source_file.content)
            manifest["acceptance_tests"].append(
                {"command": f"grep -Fxq '{mismatched}' /home/user/user.txt"}
            )
            source_file.content = json.dumps(manifest)

    archive_path, _ = SourceArchive(tmp_path).create("session", flag_scenario, generated)
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


def test_static_validation_does_not_require_specific_web_check_commands(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        web_generated_source(complete_checks=False),
    )
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


def test_static_validation_does_not_infer_shell_execution_from_mode(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        web_generated_source(provision_mode="0644"),
    )
    assert archive_path.is_file()


def test_static_validation_does_not_infer_php_execution_from_path(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        web_generated_source(php_path="contents/app/cgi-bin/index.php", php_mode="0644"),
    )
    assert archive_path.is_file()


def test_static_validation_does_not_require_php_shebang_from_path(tmp_path: Path) -> None:
    generated = web_generated_source(php_path="contents/app/cgi-bin/index.php", php_mode="0755")
    php = next(file for file in generated.files if file.path.endswith("index.php"))
    php.content = "<?php echo 'SLSG_PORTAL';\n"
    archive_path, _ = SourceArchive(tmp_path).create("session", scenario(), generated)
    assert archive_path.is_file()


def test_static_validation_does_not_infer_php_execution_from_mode(tmp_path: Path) -> None:
    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        web_generated_source(php_mode="0755"),
    )
    assert archive_path.is_file()


def test_requires_build_entrypoint(tmp_path: Path) -> None:
    generated = GeneratedSource(files=[SourceFile(path="contents/README.md", content="test")])
    with pytest.raises(InvalidSourceError, match="generated source validation failed"):
        SourceArchive(tmp_path).create(
            "session",
            scenario(),
            generated,
        )


def test_generates_runtime_verification_entrypoint_from_manifest(tmp_path: Path) -> None:
    generated = web_generated_source()
    assert all(file.path != "contents/scripts/verify.sh" for file in generated.files)
    generated.files.append(
        SourceFile(
            path="contents/scripts/verify.sh",
            content="#!/bin/bash\nexit 0\n",
            mode="0755",
        )
    )

    archive_path, _ = SourceArchive(tmp_path).create(
        "session-generated-verify", scenario(), generated
    )

    with zipfile.ZipFile(archive_path) as archive:
        script = archive.read("contents/scripts/verify.sh").decode()
        mode = (archive.getinfo("contents/scripts/verify.sh").external_attr >> 16) & 0o777
    assert "bash -o pipefail -c" in script
    assert "curl -fsSL http://127.0.0.1/" in script
    assert "runuser -u www-data -- test -r /var/www/html/index.php" in script
    assert "exit 0" not in script
    assert mode == 0o755


def test_static_validation_does_not_parse_package_manager_commands(tmp_path: Path) -> None:
    generated = web_generated_source()
    provision = next(
        file for file in generated.files if file.path == "contents/scripts/provision.sh"
    )
    provision.content += "apt-get upgrade -y\n"

    archive_path, _ = SourceArchive(tmp_path).create("session", scenario(), generated)
    assert archive_path.is_file()


def test_static_validation_does_not_reparse_failed_package_commands(tmp_path: Path) -> None:
    generated = web_generated_source()
    provision = next(
        file for file in generated.files if file.path == "contents/scripts/provision.sh"
    )
    provision.content += "apt-get install -y example-runtime9\n"
    repair_history = [
        {
            "attempt": 1,
            "trigger": {
                "kind": "packer_build",
                "error_message": "Unable to locate package example-runtime9",
            },
        }
    ]

    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        generated,
        repair_history=repair_history,
    )
    assert archive_path.is_file()


def test_static_validation_does_not_reparse_failed_systemd_commands(tmp_path: Path) -> None:
    generated = web_generated_source()
    provision = next(
        file for file in generated.files if file.path == "contents/scripts/provision.sh"
    )
    provision.content += "systemctl enable example-runtime.service\n"
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

    archive_path, _ = SourceArchive(tmp_path).create(
        "session",
        scenario(),
        generated,
        repair_history=repair_history,
    )
    assert archive_path.is_file()


def test_rejects_manifest_that_does_not_match_attack_graph(tmp_path: Path) -> None:
    required = [
        "contents/README.md",
        "contents/scenario_manifest.json",
        "contents/build.sh",
        "contents/scripts/provision.sh",
        "contents/scripts/verify.sh",
    ]
    manifest = json.dumps(
        {
            "target_os": "Debian 13.7.0",
            "required_files": required,
            "services": [{"name": "web", "protocol": "http", "port": 80}],
            "acceptance_tests": [{"command": "curl http://localhost"}],
            "expected_vulnerabilities": [
                {"name": "training-only", "description": "Intentional training weakness"}
            ],
            "health_checks": [{"command": "curl http://localhost"}],
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
        "contents/scripts/verify.sh",
    ]
    manifest = json.dumps(
        {
            "target_os": "Debian 13.7.0",
            "required_files": required,
            "services": [{"name": "ssh", "protocol": "tcp", "port": 22}],
            "acceptance_tests": [{"command": "test -f /etc/passwd"}],
            "expected_vulnerabilities": [
                {"name": "training-only", "description": "Intentional training weakness"}
            ],
            "health_checks": [{"command": "test -f /etc/passwd"}],
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

    rejected = generated("#!/bin/bash\nset -euo pipefail\nfalse\n")
    rejected.files = [
        source_file
        for source_file in rejected.files
        if source_file.path != "contents/README.md"
    ]
    with pytest.raises(InvalidSourceError):
        archive.create(
            "session",
            scenario(),
            rejected,
        )

    source = archive.load(str(tmp_path / "session" / "v1" / "source"))
    archived = archive.load_archive(archive_path)
    assert source is not None and archived is not None
    assert next(file.content for file in source.files if file.path.endswith("provision.sh")) == (
        "#!/bin/bash\nset -euo pipefail\necho valid\n"
    )
    assert source == archived


def test_static_validation_does_not_guess_test_markers_from_names(tmp_path: Path) -> None:
    generated = web_generated_source()
    marker = "RSC_RCE_TEST_PAYLOAD_MARKER"
    for source_file in generated.files:
        if source_file.path == "contents/app/index.php":
            source_file.content += (
                f"if ($_POST['payload'] === '{marker}') {{ file_put_contents('/tmp/rce', 'ok'); }}\n"
            )
        if source_file.path == "contents/scenario_manifest.json":
            manifest = json.loads(source_file.content)
            manifest["acceptance_tests"].append(
                {"command": f"curl -d '{marker}' http://127.0.0.1/"}
            )
            source_file.content = json.dumps(manifest)

    archive_path, _ = SourceArchive(tmp_path).create("session", scenario(), generated)
    assert archive_path.is_file()


def test_static_validation_does_not_infer_acceptance_test_semantics(tmp_path: Path) -> None:
    expected = "flag{user_a1d51d7f803f51f0356f3e547c842a0b}"
    flag_scenario = scenario().model_copy(update={"user_flag": expected})
    generated = web_generated_source()
    for source_file in generated.files:
        if source_file.path == "contents/scripts/provision.sh":
            source_file.content += f"printf '%s\\n' '{expected}' > /home/rscuser/user.txt\n"
        if source_file.path == "contents/scenario_manifest.json":
            manifest = json.loads(source_file.content)
            manifest["acceptance_tests"].append(
                {
                    "command": (
                        "sudo -u rscuser cat /home/rscuser/user.txt | "
                        f"grep -Fxq '{expected}'"
                    )
                }
            )
            source_file.content = json.dumps(manifest)

    archive_path, _ = SourceArchive(tmp_path).create("session", flag_scenario, generated)
    assert archive_path.is_file()


def test_records_rejected_semantic_review_in_source_and_archive(tmp_path: Path) -> None:
    archive = SourceArchive(tmp_path)
    archive_path, original_checksum = archive.create(
        "session", scenario(), web_generated_source()
    )
    review_report = {
        "kind": "source_semantic_review",
        "status": "rejected",
        "summary": "Exploit verification is simulated.",
        "checks": [],
    }

    updated_checksum = archive.record_semantic_review(
        archive_path, review_report, approved=False
    )

    report = json.loads(
        (archive_path.parent / "source" / "repair_report.json").read_text()
    )
    assert report["source_semantic_review"]["status"] == "rejected"
    assert report["source_semantic_review"]["report"] == review_report
    with zipfile.ZipFile(archive_path) as zipped:
        archived_report = json.loads(zipped.read("repair_report.json"))
    assert archived_report["source_semantic_review"]["status"] == "rejected"
    assert archive.load_semantic_review_from_archive(archive_path) == archived_report[
        "source_semantic_review"
    ]
    assert updated_checksum != original_checksum
