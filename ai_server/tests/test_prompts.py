from __future__ import annotations

from ai_server.models import (
    ROCKYOU_PASSWORD_PLACEHOLDER,
    AttackGraph,
    AttackStep,
    GeneratedSource,
    MachineInformation,
    PasswordCrackingSpec,
    ScenarioDraft,
    SourceFile,
)
from ai_server.prompts import (
    attack_graph_prompt,
    code_prompt,
    guidance_prompt,
    repair_prompt,
    scenario_prompt,
    scenario_review_prompt,
    scenario_sync_prompt,
    source_review_prompt,
)


def test_guidance_prompt_uses_scenario_source_and_acquired_flags() -> None:
    machine = MachineInformation(
        name="Guided Machine",
        visibility="public",
        theme="Web",
        difficulty="Medium",
    )
    scenario = ScenarioDraft(
        scenario_id="scenario-guidance",
        title="Guided Machine",
        definition="# Confirmed scenario\nInspect the web service.",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="inspect-web",
                    title="Inspect web",
                    kind="reconnaissance",
                    phase="reconnaissance",
                    description="Inspect port 8080.",
                    implementation_steps=["Provision the web service"],
                )
            ]
        ),
        user_flag="flag{user_0123456789abcdef0123456789abcdef}",
    )
    source = GeneratedSource(
        files=[
            SourceFile(
                path="contents/scripts/provision.sh",
                content=(
                    "#!/bin/bash\nprintf 'configured-service'\n"
                    "printf 'flag{user_0123456789abcdef0123456789abcdef}'\n"
                ),
            )
        ]
    )

    prompt = guidance_prompt(machine, scenario, source, ["user"])

    assert "取得済みフラグ: user" in prompt
    assert "inspect-web" in prompt
    assert "contents/scripts/provision.sh" in prompt
    assert "configured-service" in prompt
    assert "flag{user_0123456789abcdef0123456789abcdef}" not in prompt
    assert "[REDACTED FLAG]" in prompt
    assert "正解フラグ値" in prompt
    assert "GitHub Flavored Markdown" in prompt
    assert "後続項目は画面上で順番に開示" in prompt
    assert "生のHTMLは使用しない" in prompt


def test_ai_prompts_redact_late_bound_rockyou_password() -> None:
    password = "password123"
    machine = MachineInformation(
        name="Hash target",
        visibility="private",
        theme="Password cracking",
        difficulty="Easy",
    )
    scenario = ScenarioDraft(
        scenario_id="scenario-hash",
        title="Hash target",
        definition=f"Provision the credential for {password}.",
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="crack-password",
                    title="Crack password",
                    kind="password_cracking",
                    phase="initial_access",
                    description="Crack the stored credential.",
                    implementation_steps=["Hash the late-bound password"],
                    password_cracking=PasswordCrackingSpec(
                        wordlist="rockyou.txt",
                        password=password,
                        line_number=1,
                        search_space_lines=1,
                        hash_algorithm="bcrypt",
                        hash_runtime="php",
                        hash_api="password_hash",
                        hashcat_mode=3200,
                        target_crack_seconds=150,
                    ),
                )
            ]
        ),
    )
    source = GeneratedSource(
        files=[
            SourceFile(
                path="contents/scripts/provision.sh",
                content=f"php -r 'password_hash(\"{password}\", PASSWORD_DEFAULT);'",
            )
        ]
    )

    prompts = (
        code_prompt(machine, scenario),
        repair_prompt(machine, scenario, source, {"build_log": password}),
        source_review_prompt(
            machine, scenario, source, reconsideration={"evidence": password}
        ),
        scenario_sync_prompt(
            machine, scenario, source, review_feedback={"evidence": password}
        ),
        guidance_prompt(machine, scenario, source, []),
    )
    for prompt in prompts:
        assert password not in prompt
        assert ROCKYOU_PASSWORD_PLACEHOLDER in prompt


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
        assert "ソース生成後のサーバー選択" in prompt
        assert "`password_cracking`" in prompt
        assert "password_cracking" in prompt
        assert "対象アプリと同じ" in prompt
        assert "固定ハッシュは設計書へ書かず" in prompt

    assert "対象マシンを調査すること" in design_prompts[1]
    assert "フラグを獲得すること" in design_prompts[1]
    assert "表記や語彙は、文章全体として自然で意味が明確なら自由" in design_prompts[1]
    assert "正確なstep_idとtitle" in design_prompts[1]
    assert "複数stepへ分割・統合" in design_prompts[1]

    assert len(design_prompts[0]) < 3200
    assert len(design_prompts[1]) < 3800

    for prompt in implementation_prompts:
        assert "rockyou.txt" in prompt
        assert "約2〜3分" in prompt
        assert "平文パスワード" in prompt
        assert "Hashcat modeまたはJohn format" in prompt
        assert "ハッシュクラックを攻略の必須ステップにしない" in prompt
        assert "rockyou.txtはハッシュの一覧ではなく" in prompt
        assert "ターゲットVMへ辞書を導入" in prompt
        assert "使用してよい" in prompt
        assert "単一の未検証URLへ無条件に依存せず" in prompt
        assert "contents/scripts/provision.shの実行中" in prompt
        assert "`password_hash`" in prompt
        assert "AIが予測したダイジェストを埋め込まない" in prompt
        assert "固定ダイジェストを設計書" in prompt
        assert "__SLSG_ROCKYOU_PASSWORD__" in prompt
        assert "hash_runtime" in prompt
        assert "hash_api" in prompt
        assert "誤った平文が失敗" in prompt
        assert "ソースコードからのコンパイルを既定にしない" in prompt
        assert "snapshot APTリポジトリ" in prompt
        assert "ベンダー公式releaseのビルド済みバイナリ" in prompt
        assert "ソースビルドは" in prompt
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
        assert "scripts/verify.sh" in prompt
        assert "サーバー生成のscripts/verify.sh" in prompt
        assert "scenario_manifest.jsonのJSON Schema" in prompt
        assert '"ManifestService"' in prompt
        assert '"protocol"' in prompt
        assert '"http"' in prompt
        assert '"expected_vulnerabilities"' in prompt
        assert '"minItems": 1' in prompt
        assert '"additionalProperties": false' in prompt
        assert "実装した脆弱性を最低1件" in prompt
        assert '`"training-only"`のような文字列だけの要素は禁止' in prompt


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
    assert "ビルド済み成果物を選択済みなのにソースをコンパイル" in review_prompt
    assert "ソースコードからのコンパイルを既定にしない" in review_prompt

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
    assert "source_build_reason" in scenario_review
    assert "implementation_stepsはその攻撃を成立させるVM側" in scenario_review
    assert "自作PHP等の非CVE step" in scenario_review
    assert "本文へ合わせるために" in scenario_review

    sync_prompt = scenario_sync_prompt(machine, scenario, source)
    assert "実装とシナリオを同期" in sync_prompt
    assert "owner、group、mode、ACL、sudoers、capability" in sync_prompt
    assert "実装と異なる古いパス、権限" in sync_prompt
    assert "正解フラグ値そのもの" in sync_prompt
    assert "scenario_description" in sync_prompt
    feedback_sync_prompt = scenario_sync_prompt(
        machine,
        scenario,
        source,
        {"kind": "scenario_sync_review", "summary": "negative control is missing"},
    )
    assert "negative control is missing" in feedback_sync_prompt
    assert "攻撃グラフの意図を保ったまま" in feedback_sync_prompt
    assert "negative control" in scenario_review
    assert "標準的な構文・設定検査と実行時検査" in scenario_review
    assert "findingsは" in scenario_review
    assert "最大20件" in scenario_review
    assert len(scenario_review) < 5000

    assert "`php -l`" in review_prompt
    assert "`bash -n`" in review_prompt
    assert "`apache2ctl configtest`" in review_prompt
    assert "implementation_mismatch" in review_prompt
    assert "一律に不合格にはせず" in review_prompt
    assert '"repair_target":"source_code"' in review_prompt
    assert "source_code、実装が正しく本文だけが古い場合はscenario_text" in review_prompt
    assert "存在しないフィールドの" in review_prompt


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
