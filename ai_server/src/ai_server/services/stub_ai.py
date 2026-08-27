from __future__ import annotations

import json
from uuid import uuid4

from ..models import GeneratedSource, MachineInformation, ScenarioDraft, SourceFile, SourcePatch


class StubGenerator:
    """Deterministic generator for local integration tests without an API key."""

    async def generate_scenario(self, machine: MachineInformation) -> ScenarioDraft:
        definition = f"""# {machine.name} シナリオ設計書

## 1. 基本情報 (Metadata)
- **難易度**: {machine.difficulty}
- **OS**: Linux
- **主テーマ**: {machine.theme}

## 2. 背景ストーリー & コンテキスト
隔離された演習環境で、設定確認と最小権限の考え方を学びます。

## 3. 初期潜入フェーズ
SSHで演習ユーザーとしてログインし、公開情報とサービス設定を調査します。

## 4. 権限昇格フェーズ (Privilege Escalation)
意図的に用意したローカル設定を調査し、管理者権限の境界を確認します。

## 5. 教育的価値
列挙、設定監査、証跡確認という基本的な調査手順を学べます。
"""
        return ScenarioDraft(
            scenario_id=f"scenario-{uuid4().hex}",
            title=machine.name,
            definition=definition,
            target_os=machine.operating_system,
        )

    async def generate_source(
        self, machine: MachineInformation, scenario: ScenarioDraft
    ) -> GeneratedSource:
        build = """#!/bin/bash
set -euo pipefail
install -d -m 0755 /opt/slsg-scenario
install -m 0644 ./README.md /opt/slsg-scenario/README.md
bash ./scripts/provision.sh
install -d -m 0755 /etc/motd.d
printf '%s\n' 'SLSG local demonstration scenario is ready.' > /etc/motd.d/90-slsg-scenario
"""
        provision = """#!/bin/bash
set -euo pipefail
id slsg-student >/dev/null 2>&1 || useradd --create-home --shell /bin/bash slsg-student
"""
        readme = (
            f"# {machine.name}\n\nTheme: {machine.theme}; difficulty: {machine.difficulty}.\n\n"
            "Packer executes `contents/build.sh`. Use `systemctl` or the MOTD for a health check. "
            "Validate the scenario and flag placement only in an isolated training VM.\n\n"
            f"{scenario.definition}\n"
        )
        manifest = json.dumps(
            {
                "title": machine.name,
                "difficulty": machine.difficulty,
                "target_os": machine.operating_system,
                "required_files": [
                    "contents/README.md",
                    "contents/scenario_manifest.json",
                    "contents/build.sh",
                    "contents/scripts/provision.sh",
                ],
                "services": [{"name": "ssh", "port": 22}],
                "acceptance_tests": [{"command": "test -f /opt/slsg-scenario/README.md"}],
                "expected_vulnerabilities": [{"name": "local demonstration setting"}],
                "health_checks": [{"command": "test -f /etc/motd.d/90-slsg-scenario"}],
            },
            ensure_ascii=False,
            indent=2,
        )
        return GeneratedSource(
            files=[
                SourceFile(path="contents/build.sh", content=build, mode="0755"),
                SourceFile(path="contents/scripts/provision.sh", content=provision, mode="0755"),
                SourceFile(path="contents/README.md", content=readme),
                SourceFile(path="contents/scenario_manifest.json", content=manifest),
            ]
        )

    async def repair_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        failure_report: dict,
    ) -> SourcePatch:
        return SourcePatch(
            files=[
                SourceFile(
                    path="contents/README.md",
                    content=next(
                        file.content for file in current.files if file.path == "contents/README.md"
                    )
                    + "\nRepair applied for local integration testing.\n",
                )
            ]
        )
