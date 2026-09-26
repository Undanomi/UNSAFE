from __future__ import annotations

import json
import shlex
from collections.abc import Awaitable, Callable
from uuid import uuid4

from ..models import (
    AttackGraph,
    AttackObjective,
    AttackStep,
    AutomaticFlagPlan,
    GeneratedSource,
    GuidanceItem,
    GuidancePlan,
    MachineInformation,
    ScenarioDraft,
    ScenarioReview,
    ScenarioRevision,
    SourceFile,
    SourcePatch,
    SourceReview,
    SourceWorkbenchCommand,
    SourceWorkbenchDecision,
)
from ..skills.models import ScenarioSkillContexts, SkillContext
from .ai import _record_scenario_draft


class StubGenerator:
    """Deterministic generator for local integration tests without an API key."""

    async def plan_automatic_flags(
        self,
        machine: MachineInformation,
    ) -> AutomaticFlagPlan:
        theme = machine.theme.casefold()
        system_markers = ("system", "root", "kernel", "sudo", "権限昇格", "システム")
        initial_markers = ("web", "認証", "initial", "初期侵入", "ユーザー")
        focuses_on_system = any(marker in theme for marker in system_markers)
        includes_initial_access = any(marker in theme for marker in initial_markers)
        if focuses_on_system and not includes_initial_access:
            return AutomaticFlagPlan(
                selection="system",
                user_flag_details="",
                system_flag_details=(
                    "ユーザーフラグを前提にせず、管理者権限で動作する対象を攻略してroot権限を取得し、"
                    "/root/system.txtを読み取る。"
                ),
            )
        if machine.difficulty in {"Medium", "High"}:
            return AutomaticFlagPlan(
                selection="both",
                user_flag_details=(
                    "公開サービスを調査して一般ユーザーstudentの権限を取得し、"
                    "/home/student/user.txtを読み取る。"
                ),
                system_flag_details=(
                    "userフラグ取得後の足場からローカル権限設定を調査してroot権限を取得し、"
                    "/root/system.txtを読み取る。"
                ),
            )
        return AutomaticFlagPlan(
            selection="user",
            user_flag_details=(
                "公開サービスを調査して一般ユーザーstudentの権限を取得し、"
                "/home/student/user.txtを読み取る。"
            ),
            system_flag_details="",
        )

    async def generate_scenario(
        self,
        machine: MachineInformation,
        skills: ScenarioSkillContexts | None = None,
        on_attempt: Callable[[], Awaitable[None]] | None = None,
    ) -> ScenarioDraft:
        resumed = getattr(on_attempt, "resume_scenario", None)
        resumed_review = getattr(on_attempt, "resume_review", None)
        if (
            isinstance(resumed, ScenarioDraft)
            and isinstance(resumed_review, ScenarioReview)
            and resumed_review.approved
        ):
            return resumed
        if on_attempt is not None:
            await on_attempt()
        if isinstance(resumed, ScenarioDraft):
            review = await self.review_scenario(machine, resumed)
            await _record_scenario_draft(on_attempt, resumed, review)
            return resumed
        objectives = []
        initial_achievements = []
        system_achievements = []
        if machine.needs_user_flag:
            objectives.append(
                AttackObjective(
                    objective_id="user-flag",
                    objective_type="user_flag",
                    description=machine.user_flag_details,
                )
            )
            initial_achievements.append("user-flag")
        if machine.needs_system_flag:
            objectives.append(
                AttackObjective(
                    objective_id="system-flag",
                    objective_type="system_flag",
                    description=machine.system_flag_details,
                )
            )
            system_achievements.append("system-flag")
        steps = [
            AttackStep(
                step_id="enumerate-service",
                title="公開サービスの列挙",
                kind="reconnaissance",
                phase="reconnaissance",
                description="公開サービスと設定情報を調査します。",
                installation_method="provisioning script",
                implementation_steps=["演習用サービスと確認可能なバナーを配置する"],
            ),
            AttackStep(
                step_id="abuse-web-config",
                title="Web設定不備の悪用",
                kind="misconfiguration",
                phase="initial_access",
                description="意図的な設定不備から演習ユーザーの権限を取得します。",
                requires=["enumerate-service"],
                achieves=initial_achievements,
                installation_method="provisioning script",
                implementation_steps=["隔離された教材用の設定不備を作成する"],
            ),
        ]
        for index, cve_id in enumerate(machine.cve_ids, start=1):
            steps.append(
                AttackStep(
                    step_id=f"exercise-cve-{index}",
                    title=f"{cve_id}の再現",
                    kind="cve",
                    phase="initial_access",
                    description=f"隔離環境で{cve_id}の成立条件を検証します。",
                    requires=["enumerate-service"],
                    cve_id=cve_id,
                    cve_title=f"Stub record for {cve_id}",
                    cve_description=(
                        f"Deterministic test-only description for the published {cve_id} record."
                    ),
                    installation_artifact="other_prebuilt",
                    artifact_source="bundled deterministic test fixture",
                    software="stub-training-service",
                    vulnerable_version="1.0",
                    os_compatible=True,
                    compatibility_reason="Deterministic local stub scenario.",
                    installation_method="provisioning script",
                    implementation_steps=["教材用の決定的な再現条件を構成する"],
                )
            )
        if machine.needs_system_flag:
            steps.append(
                AttackStep(
                    step_id="abuse-local-permission",
                    title="ローカル権限設定の悪用",
                    kind="misconfiguration",
                    phase="privilege_escalation",
                    description="ローカル権限設定を調査して管理者権限を取得します。",
                    requires=["abuse-web-config"],
                    achieves=system_achievements,
                    installation_method="provisioning script",
                    implementation_steps=["教材用の最小権限違反を構成する"],
                )
            )
        attack_graph = AttackGraph(objectives=objectives, steps=steps)
        definition = f"""# {machine.name} シナリオ設計書

## 1. 基本情報 (Metadata)
- **難易度**: {machine.difficulty}
- **OS**: Linux
- **主テーマ**: {machine.theme}

## 2. 背景ストーリー & コンテキスト
隔離された演習環境で、設定確認と最小権限の考え方を学びます。

## 3. 到達目標
設定されたuser/system flagを攻撃グラフに沿って取得します。

## 4. 攻撃グラフ
公開サービスの列挙からWeb設定不備へ進み、必要な場合はローカル権限設定を調査します。

## 5. 環境実装計画
すべての弱点は隔離された演習VM内にプロビジョニングします。

## 6. 教育的価値
列挙、設定監査、証跡確認という基本的な調査手順を学べます。
"""
        scenario = ScenarioDraft(
            scenario_id=f"scenario-{uuid4().hex}",
            title=machine.name,
            scenario_description=(
                f"{machine.theme}を題材に、隔離された環境を調査するセキュリティ演習です。"
                "マシンの構成や動作を詳しく調べ、演習環境に隠されたフラグを見つけ出してください。"
            ),
            definition=definition,
            target_os=machine.operating_system,
            attack_graph=attack_graph,
        )
        await _record_scenario_draft(on_attempt, scenario)
        review = await self.review_scenario(machine, scenario)
        await _record_scenario_draft(on_attempt, scenario, review)
        return scenario

    async def generate_guidance(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        acquired_flags: list[str],
    ) -> GuidancePlan:
        del current
        initial_target = (
            "user"
            if scenario.user_flag and "user" not in acquired_flags
            else "system"
            if scenario.system_flag and "system" not in acquired_flags
            else None
        )
        items = []
        if initial_target:
            items.append(
                GuidanceItem(
                    target_flag=initial_target,
                    title="公開サービスを整理する",
                    question="対象ホストでは、どのサービスとバージョン情報を観察できますか？",
                    hint="まずポートとサービスを列挙し、Webがあればトップページやレスポンスも確認してください。",
                )
            )
        if "user" not in acquired_flags and scenario.user_flag:
            items.append(
                GuidanceItem(
                    target_flag="user",
                    title="初期侵入の手掛かりを探す",
                    question="公開サービスの設定や入力から、一般ユーザー権限へつながる不備はありませんか？",
                    hint="列挙結果を攻撃グラフの初期アクセス段階と照らし合わせてください。",
                )
            )
        if "system" not in acquired_flags and scenario.system_flag:
            items.append(
                GuidanceItem(
                    target_flag="system",
                    title="権限境界を調べる",
                    question="現在のユーザーから管理者権限へ進むために、どのローカル設定を確認すべきですか？",
                    hint="sudo権限、実行ファイルの所有権、サービス設定などを順に調査してください。",
                )
            )
        return GuidancePlan(
            introduction=(
                f"{machine.name}の攻略経路を段階的に確認します。"
                "回答の自動判定は行わず、調査できたら次の項目へ進んでください。"
            ),
            items=items,
        )

    async def review_scenario(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        review_context: str = "generation",
        reconsideration: dict | None = None,
    ) -> ScenarioReview:
        return ScenarioReview(
            approved=True,
            summary="Deterministic stub scenario is accepted for local integration testing.",
        )

    async def generate_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        skills: SkillContext | None = None,
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
        acceptance_tests = [{"command": "test -f /opt/slsg-scenario/README.md"}]
        if scenario.user_flag:
            quoted_user_flag = shlex.quote(scenario.user_flag)
            provision += (
                f"printf '%s\\n' {quoted_user_flag} > /home/slsg-student/user.txt\n"
                "chown slsg-student:slsg-student /home/slsg-student/user.txt\n"
                "chmod 0400 /home/slsg-student/user.txt\n"
            )
            acceptance_tests.append(
                {
                    "command": (
                        f"test \"$(cat /home/slsg-student/user.txt)\" = {quoted_user_flag}"
                    )
                }
            )
        if scenario.system_flag:
            quoted_system_flag = shlex.quote(scenario.system_flag)
            provision += (
                f"printf '%s\\n' {quoted_system_flag} > /root/system.txt\n"
                "chmod 0400 /root/system.txt\n"
            )
            acceptance_tests.append(
                {"command": f"test \"$(cat /root/system.txt)\" = {quoted_system_flag}"}
            )
        readme = (
            f"# {machine.name}\n\nTheme: {machine.theme}; difficulty: {machine.difficulty}.\n\n"
            "Packer executes `contents/build.sh`. Use `systemctl` or the MOTD for a health check. "
            "Validate the scenario and flag placement only in an isolated training VM.\n\n"
            f"{scenario.definition}\n"
        )
        manifest = json.dumps(
            {
                "target_os": machine.operating_system,
                "required_files": [
                    "contents/README.md",
                    "contents/scenario_manifest.json",
                    "contents/build.sh",
                    "contents/scripts/provision.sh",
                    "contents/scripts/verify.sh",
                ],
                "services": [{"name": "ssh", "protocol": "tcp", "port": 22}],
                "acceptance_tests": acceptance_tests,
                "expected_vulnerabilities": [
                    {
                        "name": "local demonstration setting",
                        "description": (
                            "The generated training service intentionally exposes the attack path."
                        ),
                    },
                    *[
                        {
                            "cve_id": step.cve_id,
                            "official_title": step.cve_title,
                            "description": step.cve_description,
                            "references": step.references,
                            "installation_artifact": step.installation_artifact,
                            "artifact_source": step.artifact_source,
                            "source_build_reason": step.source_build_reason,
                        }
                        for step in scenario.attack_graph.steps
                        if step.cve_id
                    ],
                ],
                "health_checks": [{"command": "test -f /etc/motd.d/90-slsg-scenario"}],
                "attack_steps": [
                    {
                        "step_id": step.step_id,
                        "kind": step.kind,
                        "requires": step.requires,
                        "achieves": step.achieves,
                    }
                    for step in scenario.attack_graph.steps
                ],
                "objectives": [
                    objective.model_dump(mode="json")
                    for objective in scenario.attack_graph.objectives
                ],
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
        skills: SkillContext | None = None,
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

    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision:
        del machine, scenario, current, commands_remaining
        if not observations:
            return SourceWorkbenchDecision(
                action="run",
                command=SourceWorkbenchCommand(
                    argv=["apt-get", "update"],
                    cwd="contents",
                    purpose="Validate package repository availability in a fresh target container.",
                    intent="verify",
                    network_access=True,
                    run_as_root=True,
                ),
                summary="Validate the fresh target container package repository.",
            )
        return SourceWorkbenchDecision(
            action="finish",
            summary="The deterministic stub syntax check completed.",
        )

    async def synchronize_scenario(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        review_feedback: dict | None = None,
    ) -> ScenarioRevision:
        return ScenarioRevision(
            scenario_description=(
                scenario.scenario_description
                or "この教育用マシンを調査し、設定されたフラグを獲得してください。"
            ),
            definition=scenario.definition,
            attack_graph=scenario.attack_graph,
            summary="The deterministic stub source remains synchronized with the scenario.",
        )

    async def review_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        skills: SkillContext | None = None,
        reconsideration: dict | None = None,
    ) -> SourceReview:
        return SourceReview(
            approved=True,
            summary="Deterministic stub source is accepted for local integration testing.",
        )
