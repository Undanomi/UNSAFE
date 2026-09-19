from __future__ import annotations

from ai_server.models import (
    AttackGraph,
    AttackStep,
    GeneratedSource,
    MachineInformation,
    ScenarioDraft,
    SourceFile,
)
from ai_server.prompts import (
    attack_graph_prompt,
    code_prompt,
    repair_prompt,
    scenario_prompt,
    scenario_review_prompt,
    scenario_sync_prompt,
    source_review_prompt,
)


def test_all_generation_prompts_include_shared_constraints() -> None:
    machine = MachineInformation(
        name="Test",
        visibility="private",
        theme="Web",
        difficulty="Easy",
    )
    scenario = ScenarioDraft(
        scenario_id="scenario-test",
        title="Test",
        definition="# Test",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="test-step",
                    title="Test step",
                    kind="custom",
                    phase="initial_access",
                    description="Test the generated machine",
                    implementation_steps=["Create a deterministic test target"],
                )
            ]
        ),
    )
    source = GeneratedSource(files=[SourceFile(path="contents/build.sh", content="#!/bin/bash\n")])
    design_prompts = [
        attack_graph_prompt(machine, [], 2024),
        scenario_prompt(machine, scenario.attack_graph.model_dump_json()),
    ]
    implementation_prompts = [
        code_prompt(machine, scenario),
        repair_prompt(machine, scenario, source, {"error": "test"}),
    ]

    for prompt in design_prompts:
        assert "必要最小限のステップ" in prompt
        assert "rockyou.txtは平文wordlist" in prompt
        assert "通常は攻撃者側で使う" in prompt
        assert "標準的な構文・設定検査と実行時検査" in prompt
        assert "完全なスクリプトや全コマンドはコード生成段階へ委ねる" in prompt
        assert "全親ディレクトリのowner/group/mode" in prompt

    assert "対象マシンを調査すること" in design_prompts[1]
    assert "フラグを獲得すること" in design_prompts[1]
    assert "表記や語彙は、文章全体として自然で意味が明確なら自由" in design_prompts[1]

    assert len(design_prompts[0]) < 3000
    assert len(design_prompts[1]) < 3000

    for prompt in implementation_prompts:
        assert "rockyou.txt" in prompt
        assert "約3分以内" in prompt
        assert "平文パスワード" in prompt
        assert "HashcatのモードまたはJohnの形式" in prompt
        assert "ハッシュクラックを攻略の必須ステップにしない" in prompt
        assert "rockyou.txtはハッシュの一覧ではなく" in prompt
        assert "ターゲットVMへ辞書を導入" in prompt
        assert "使用してよい" in prompt
        assert "単一の未検証URLへ無条件に依存せず" in prompt
        assert "既定ページ、サンプルアプリ、既定VirtualHost" in prompt
        assert "入口の選択と優先順位" in prompt
        assert "肯定確認と否定確認" in prompt
        assert "`php -l`" in prompt
        assert "`bash -n`" in prompt
        assert "`python3 -m py_compile`" in prompt
        assert "`node --check`" in prompt
        assert "`ruby -c`" in prompt
        assert "`perl -c`" in prompt
        assert "`nginx -t`" in prompt
        assert "`apache2ctl configtest`" in prompt
        assert "`sshd -t`" in prompt
        assert "`systemd-analyze verify`" in prompt
        assert "意図しないリテラル`\\n`" in prompt
        assert "IPアドレスだけを入力" in prompt
        assert "`Index of`" in prompt
        assert "PHP-FPMやApache module" in prompt
        assert "CGIとして直接実行するPHP" in prompt
        assert "chmod -R 777" in prompt
        assert "Web実行ユーザー" in prompt
        assert "files[].path" in prompt
        assert "VM内の最終配置先" in prompt
        assert "`/var/www`" in prompt
        assert "最終VM内の正規の配置先として厳密に使用" in prompt
        assert "シンボリックリンク、ハードリンク、bind mount" in prompt
        assert "対応する攻撃グラフの" in prompt
        assert "同じフラグ内容を取得できる場所が指定パスの1か所だけ" in prompt
        assert "指定パス以外に同じ内容があることを理由" in prompt


def test_generation_and_review_prompts_require_exploit_specific_controls() -> None:
    machine = MachineInformation(
        name="SQLi Test",
        visibility="private",
        theme="SQL Injection",
        difficulty="Easy",
    )
    scenario = ScenarioDraft(
        scenario_id="scenario-sqli",
        title="SQLi Test",
        definition="# SQLi",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="extract-secret",
                    title="Extract a protected row",
                    kind="web_vulnerability",
                    phase="initial_access",
                    description="Use SQL injection to extract a protected row.",
                    implementation_steps=["Create an injectable query"],
                )
            ]
        ),
    )
    source = GeneratedSource(
        files=[SourceFile(path="contents/app/index.php", content="<?php echo 'test';")]
    )

    design_prompts = [
        attack_graph_prompt(machine, [], 2024),
        scenario_prompt(machine, scenario.attack_graph.model_dump_json()),
    ]
    implementation_prompts = [
        code_prompt(machine, scenario),
        repair_prompt(machine, scenario, source, {"error": "test"}),
    ]
    for prompt in [*design_prompts, *implementation_prompts]:
        assert "benign control" in prompt
        assert "negative control" in prompt

    for prompt in design_prompts:
        assert "前提なしでは失敗" in prompt

    scenario_retry = scenario_prompt(
        machine,
        scenario.attack_graph.model_dump_json(),
        [
            (
                'scenario_semantic_review: {"summary":"service ordering is inconsistent",'
                '"findings":[{"evidence":"sshd is configured before installation",'
                '"remediation":"install OpenSSH before writing its configuration"}]}'
            )
        ],
    )
    assert "service ordering is inconsistent" in scenario_retry
    assert "sshd is configured before installation" in scenario_retry
    assert "install OpenSSH before writing its configuration" in scenario_retry

    for prompt in implementation_prompts:
        assert "意図した脆弱性が「存在する」だけでなく「攻略に必要」" in prompt
        assert "より短い別経路" in prompt

    review_prompt = source_review_prompt(machine, scenario, source)
    assert "独立した敵対的レビュー担当" in review_prompt
    assert "作者の説明やmanifestの自己申告を信用せず" in review_prompt
    assert "unintended_shortcut" in review_prompt
    assert "実際のデータフロー" in review_prompt
    assert "シナリオ設計書" in review_prompt
    assert scenario.definition in review_prompt

    scenario_review = scenario_review_prompt(machine, scenario)
    assert "独立した敵対的レビュー担当" in scenario_review
    assert "permission_blocker" in scenario_review
    assert "permission_shortcut" in scenario_review
    assert "全親ディレクトリ" in scenario_review
    assert "実効UID" in scenario_review
    assert "benign control" in scenario_review
    assert "時系列の権限表" in scenario_review
    assert "相反する記述" in scenario_review
    assert "任意のコマンド・コード・式" in scenario_review
    assert "操作方法や通信チャネルの変更" in scenario_review
    assert "description_spoiler" in scenario_review
    assert "特定の定型句や表記の完全一致は要求しない" in scenario_review

    sync_prompt = scenario_sync_prompt(machine, scenario, source)
    assert "実装とシナリオを同期" in sync_prompt
    assert "owner、group、mode、ACL、sudoers、capability" in sync_prompt
    assert "実装と異なる古いパス、権限" in sync_prompt
    assert "正解フラグ値そのもの" in sync_prompt
    assert "scenario_description" in sync_prompt
    assert "negative control" in scenario_review
    assert "標準的な構文・設定検査と実行時検査" in scenario_review
    assert "findingsは" in scenario_review
    assert "最大20件" in scenario_review
    assert len(scenario_review) < 4500

    assert "`php -l`" in review_prompt
    assert "`bash -n`" in review_prompt
    assert "`apache2ctl configtest`" in review_prompt
    assert "implementation_mismatch" in review_prompt
    assert "一律に不合格にはせず" in review_prompt


def test_source_prompts_include_persisted_flag_values() -> None:
    machine = MachineInformation(
        name="Flag Test",
        visibility="private",
        theme="Flags",
        difficulty="Easy",
        needs_user_flag=True,
        user_flag_details="/home/student/user.txt",
        needs_system_flag=True,
        system_flag_details="/root/system.txt",
    )
    scenario = ScenarioDraft(
        scenario_id="scenario-flags",
        title="Flag Test",
        definition="# Flag Test",
        user_flag="flag{user_exact_value}",
        system_flag="flag{system_exact_value}",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="flags",
                    title="Read flags",
                    kind="custom",
                    phase="objective",
                    description="Read both flags",
                    implementation_steps=["Place both flags"],
                )
            ]
        ),
    )
    source = GeneratedSource(
        files=[SourceFile(path="contents/scripts/provision.sh", content="#!/bin/bash\n")]
    )

    for prompt in (
        code_prompt(machine, scenario),
        repair_prompt(machine, scenario, source, {"error": "test"}),
        source_review_prompt(machine, scenario, source),
    ):
        assert "flag{user_exact_value}" in prompt
        assert "flag{system_exact_value}" in prompt

    assert "user_flag" not in scenario.model_dump()
    assert "system_flag" not in scenario.model_dump()
