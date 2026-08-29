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
                content=(
                    "#!/bin/bash\nset -euo pipefail\n"
                    "apt-get install -y example-runtime9\n"
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
                    "#!/bin/bash\nset -euo pipefail\n"
                    "systemctl enable example-runtime.service\n"
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
            "services": [{"name": "web", "port": 80}],
            "acceptance_tests": ["curl http://localhost"],
            "expected_vulnerabilities": ["training-only"],
            "health_checks": ["curl http://localhost"],
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
                SourceFile(
                    path="contents/scripts/provision.sh", content=provision, mode="0755"
                ),
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
