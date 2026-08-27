from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_server.models import GeneratedSource, ScenarioDraft, SourceFile
from ai_server.services.source_archive import InvalidSourceError, SourceArchive


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
            ScenarioDraft(scenario_id="scenario-1", title="test", definition="test"),
            generated,
        )


def test_requires_build_entrypoint(tmp_path: Path) -> None:
    generated = GeneratedSource(files=[SourceFile(path="contents/README.md", content="test")])
    with pytest.raises(InvalidSourceError, match="generated source validation failed"):
        SourceArchive(tmp_path).create(
            "session",
            ScenarioDraft(scenario_id="scenario-1", title="test", definition="test"),
            generated,
        )


@pytest.mark.parametrize(
    "provision",
    [
        "#!/bin/bash\nset -euo pipefail\napt install -y tomcat9\n",
        "#!/bin/bash\nset -euo pipefail\napt-get upgrade -y\n",
    ],
)
def test_rejects_ubuntu_base_image_incompatible_commands(tmp_path: Path, provision: str) -> None:
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
            SourceFile(path="contents/scripts/provision.sh", content=provision, mode="0755"),
        ]
    )
    with pytest.raises(InvalidSourceError, match="base_image"):
        SourceArchive(tmp_path).create(
            "session",
            ScenarioDraft(scenario_id="scenario-1", title="test", definition="test"),
            generated,
        )
