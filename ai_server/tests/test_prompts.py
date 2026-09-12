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
    prompts = [
        attack_graph_prompt(machine, [], 2024),
        scenario_prompt(machine, scenario.attack_graph.model_dump_json()),
        code_prompt(machine, scenario),
        repair_prompt(machine, scenario, source, {"error": "test"}),
    ]

    for prompt in prompts:
        assert "rockyou.txt" in prompt
        assert "約3分以内" in prompt
        assert "平文パスワード" in prompt
        assert "HashcatのモードまたはJohnの形式" in prompt
        assert "ハッシュクラックを攻略の必須ステップにしない" in prompt
        assert "既定ページ、サンプルアプリ、既定VirtualHost" in prompt
        assert "入口の選択と優先順位" in prompt
        assert "肯定確認と否定確認" in prompt
        assert "IPアドレスだけを入力" in prompt
        assert "`Index of`" in prompt
        assert "PHP-FPMやApache module" in prompt
        assert "CGIとして直接実行するPHP" in prompt
        assert "chmod -R 777" in prompt
        assert "Web実行ユーザー" in prompt
        if "files[].path" in prompt:
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

    generation_prompts = [
        attack_graph_prompt(machine, [], 2024),
        scenario_prompt(machine, scenario.attack_graph.model_dump_json()),
        code_prompt(machine, scenario),
        repair_prompt(machine, scenario, source, {"error": "test"}),
    ]
    for prompt in generation_prompts:
        assert "benign control" in prompt
        assert "negative control" in prompt
        assert "意図した脆弱性が「存在する」だけでなく「攻略に必要」" in prompt
        assert "より短い別経路" in prompt

    review_prompt = source_review_prompt(machine, scenario, source)
    assert "独立した敵対的レビュー担当" in review_prompt
    assert "作者の説明やmanifestの自己申告を信用せず" in review_prompt
    assert "unintended_shortcut" in review_prompt
    assert "実際のデータフロー" in review_prompt

    scenario_review = scenario_review_prompt(machine, scenario)
    assert "独立した敵対的レビュー担当" in scenario_review
    assert "permission_blocker" in scenario_review
    assert "permission_shortcut" in scenario_review
    assert "全親ディレクトリ" in scenario_review
    assert "実効UID" in scenario_review
    assert "benign control" in scenario_review
    assert "negative control" in scenario_review
