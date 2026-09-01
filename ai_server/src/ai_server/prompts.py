from __future__ import annotations

import json

from .models import GeneratedSource, MachineInformation, ScenarioDraft

HASH_CRACKING_CONSTRAINTS = """ハッシュクラックに関する共通制約:
- 攻略経路にハッシュクラックを含める場合、平文パスワードは標準的なrockyou.txtに
  変形なしで完全一致するエントリから選ぶ
- 攻略者がrockyou.txtだけを指定した辞書攻撃で発見できるようにし、追加辞書、ルール、
  マスク攻撃、総当たり、外部サービスを必須にしない
- 一般的な開発用PC上のHashcatまたはJohn the Ripperで、適切な形式を指定した辞書攻撃を
  開始してから約3分以内にクラックできるハッシュ方式と平文を使う
- 内部用の攻撃グラフとシナリオ仕様書には、選んだ平文パスワード、完全なハッシュ、
  ハッシュ方式、HashcatのモードまたはJohnの形式、再現用コマンドを明確に記載する
- 実装する認証情報は仕様書に記載した値と完全に一致させ、受け入れテストでも検証できるようにする
- この条件を確実に満たせない場合は、ハッシュクラックを攻略の必須ステップにしない
"""

DEPLOYMENT_VERIFICATION_CONSTRAINTS = """デプロイ結果の共通検証制約:
- パッケージ、ファイル、プロセス、待受ポートの存在だけで完成と判断せず、プロビジョニング後に
  攻撃者が利用するプロトコルと入口から意図した機能を実際に呼び出して応答を検証する
- OSやパッケージが配置する既定ページ、サンプルアプリ、既定VirtualHost、初期設定などが
  意図したアプリより優先されないよう、不要なものを削除または無効化する
- WebのDirectoryIndex、VirtualHost、リバースプロキシのルート順序、名前ベースのHost、
  リダイレクト先、サービスのポート・socket競合など、入口の選択と優先順位を明示的に確認する
- HTTPでは正しいscheme、Host、port、pathを使って必要ならリダイレクトを追跡し、期待する
  statusとアプリ固有の本文または挙動を肯定確認する。同時に既定ページ、サンプル、プレースホルダー、
  別サービスの応答ではないことを否定確認する
- HTTP以外でも単なる接続成功ではなく、対象プロトコルの応答、バナー、認証、データ取得など
  攻略経路に必要な観測可能な挙動を検証する
- 肯定確認と否定確認を、失敗時に非ゼロ終了するコマンドとしてbuild.shおよび
  scenario_manifest.jsonのhealth_checksとacceptance_testsへ記載する
"""

FLAG_PLACEMENT_CONSTRAINTS = """フラグ配置と到達性の共通制約:
- User flagまたはSystem flagの詳細で配置パスが指定されている場合、そのパスを変更、短縮、
  読み替えせず、最終VM内の正規の配置先として厳密に使用する
- 同じフラグ内容を指定パス以外の永続ファイル、別名ファイル、バックアップ、データベース、
  環境変数、ログ、サービス応答、バナーへ複製しない
- 指定パスへの別経路を作るシンボリックリンク、ハードリンク、bind mountを使用せず、
  一時ファイル、生成元、シェル履歴、プロビジョニング用コピーを最終VMに残さない
- 内部用のシナリオ仕様書とビルド入力にフラグ値を記載することは許可するが、最終VMでは
  指定パス以外から同じ値を取得できない状態にする
- 指定パスの所有者、group、modeと全親ディレクトリの探索権限を、対応する攻撃グラフの
  ステップを完了した主体だけが読み取れるように設計する。意図した攻略前に読める権限にしない
- User flagとSystem flagを同じ内容や同じファイルにせず、それぞれ指定された場所と権限境界を守る
- 受け入れテストでは、指定パス、通常ファイルであること、リンク数、所有者、group、mode、
  正しい内容、想定主体からの可読性、未権限主体からの非可読性を検証する
- さらに疑似ファイルシステムとビルド時だけの領域を除く最終VMの永続領域を検索し、
  同じフラグ内容を取得できる場所が指定パスの1か所だけであることを検証する
- 指定パス以外に同じ内容があることを理由に要件を満たしたと判断してはいけない
"""


def attack_graph_prompt(machine: MachineInformation, rejected: list[str], cve_min_year: int) -> str:
    objectives = []
    if machine.needs_user_flag:
        objectives.append(
            {
                "objective_id": "user-flag",
                "objective_type": "user_flag",
                "description": machine.user_flag_details,
            }
        )
    if machine.needs_system_flag:
        objectives.append(
            {
                "objective_id": "system-flag",
                "objective_type": "system_flag",
                "description": machine.system_flag_details,
            }
        )
    rejection_context = "\n".join(rejected[-5:]) or "なし"
    return f"""あなたは隔離された教育用Linuxマシンの攻撃経路を設計するアーキテクトです。
次の条件を満たす、実装可能な攻撃グラフをJSONで設計してください。

マシン名: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {machine.operating_system}
到達目標（この配列を変更しない）:
{json.dumps(objectives, ensure_ascii=False, indent=2)}

攻撃はCVEに限定しません。Web脆弱性、設定不備、認証情報、ロジック不備、複数手法の連鎖を
テーマと難易度に応じて選択してください。CVEが最適なステップだけkindをcveにしてください。
CVEを使う場合は{cve_min_year}年以降の実在するIDだけを候補にしてください。

これまで棄却された案:
{rejection_context}

JSONのみを返してください:
{{
  "objectives": {json.dumps(objectives, ensure_ascii=False)},
  "steps": [
    {{
      "step_id": "recon-web",
      "title": "公開Webサービスの列挙",
      "kind": "reconnaissance",
      "phase": "reconnaissance",
      "description": "攻撃者が行う操作と得られる情報",
      "requires": [],
      "achieves": [],
      "cve_id": null,
      "software": null,
      "vulnerable_version": null,
      "os_compatible": null,
      "compatibility_reason": null,
      "installation_method": "provisioning script",
      "implementation_steps": ["教材環境へ再現可能な状態を実装する具体的手順"],
      "references": []
    }}
  ]
}}

規則:
- stepsは1〜30件で、step_idは英小文字から始まる英数字・ハイフン・アンダースコアだけを使う
- kindの推奨値はreconnaissance、cve、web_vulnerability、misconfiguration、credential、
  logic_flaw、weak_cryptography、custom。必要なら新しい値も使用できる
- phaseの推奨値はreconnaissance、initial_access、post_exploitation、lateral_movement、
  privilege_escalation、objective
- requiresには前提となるstep_idを指定し、循環参照を作らない
- achievesには到達したobjective_idを指定し、すべての到達目標をいずれかのステップで達成する
- 非CVEステップではcve_idをnullにする
- 各ステップのimplementation_stepsに、VMへ意図的な教材状態を構築する具体的手順を含める
- 実環境を攻撃する手順ではなく、隔離された演習VMで再現できる構成にする

{HASH_CRACKING_CONSTRAINTS}

{DEPLOYMENT_VERIFICATION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
"""


def scenario_prompt(machine: MachineInformation, attack_graph_json: str) -> str:
    flag_context = (
        f"User flag: {machine.needs_user_flag}; details: {machine.user_flag_details or 'none'}\n"
        f"System flag: {machine.needs_system_flag}; details: {machine.system_flag_details or 'none'}"
    )
    return f"""あなたはHack The Box風の教育用Linuxマシンを設計するアーキテクトです。
次の条件と検証済み攻撃グラフを使い、実装可能で一貫したシナリオ設計書をMarkdownで1つ作成してください。

マシン名: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {machine.operating_system}
{flag_context}

攻撃グラフ:
{attack_graph_json}

必ず次の章をこの順で含めてください。
# [マシン名] シナリオ設計書
## 1. 基本情報 (Metadata)
## 2. 背景ストーリー & コンテキスト
## 3. 到達目標
## 4. 攻撃グラフ
## 5. 環境実装計画
## 6. 教育的価値

各ステップの種類、前提ステップ、攻撃者の操作、得られる状態、到達目標、環境への実装方法を
記載してください。CVEステップではCVE-ID、対象コンポーネント、脆弱な厳密バージョン、
対象OSとの適合根拠、入手元とリファレンスも記載してください。攻撃グラフの情報を省略せず、
存在しないURLを追加しないでください。

{HASH_CRACKING_CONSTRAINTS}

{DEPLOYMENT_VERIFICATION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
"""


def code_prompt(machine: MachineInformation, scenario: ScenarioDraft) -> str:
    return f"""あなたは隔離された教育用Linux VMのプロビジョニングコードを作る専門家です。
次のシナリオを{scenario.target_os}ベースのPacker VM内へ導入するファイル群を生成してください。

{scenario.definition}

検証済みの攻撃グラフ:
{scenario.attack_graph.model_dump_json(indent=2)}

JSON以外は返さないでください。形式:
{{"files":[{{"path":"contents/build.sh","content":"#!/bin/bash\\nset -euo pipefail\\n...","mode":"0755"}}]}}

制約:
- Packerは生成ルートを /tmp/scenario にコピーし、rootで contents/build.sh を実行する
- contents/README.md、contents/scenario_manifest.json、contents/build.sh、
  contents/scripts/provision.sh を必ず生成する
- scenario_manifest.json は required_files、services、acceptance_tests、
  expected_vulnerabilities、health_checks、attack_steps、objectivesを配列として持ち、target_osを
  `{scenario.target_os}` とする
- attack_stepsは攻撃グラフのstep_id、kind、requires、achievesを、objectivesは
  objective_idとobjective_typeを過不足なく反映する
- Markdownと攻撃グラフに矛盾がある場合は、攻撃グラフのステップ、依存関係、到達目標を正とする
- required_files は contents/ 基準で、生成する全必須ファイルと一致させる
- build.sh は #!/bin/bash と set -euo pipefail を使い、
  /tmp/scenario/contents がカレントディレクトリである前提で bash ./scripts/provision.sh を呼ぶ
- アプリは contents/app/、設定は contents/config/ に置く
- OSパッケージ付属のsystemd unitを優先し、ビルド中の対話入力と再起動を避ける
- {scenario.target_os}の標準パッケージリポジトリに存在することを確認できないパッケージ名を使わない
- シナリオ上の要件で厳密なバージョンが必要な場合を除き、言語ランタイムやサービスは
  バージョン番号を推測して固定せず、対象OSが提供する標準のメタパッケージを優先する
- パッケージ名からsystemd unit、ソケット、設定パスを推測しない。導入後に実在する名前を
  パッケージ情報またはsystemdから確認し、その名前でサービス設定を一貫させる
- `apt upgrade`、`apt-get upgrade`、カーネル更新を行わない。必要なパッケージだけを導入する
- ベースOS自体を古い脆弱カーネルへ変更せず、再現対象はアプリケーションや隔離した教材として実装する
- READMEにはPackerビルド、ヘルスチェック、脆弱性再現・flag確認を記載する
- 絶対パス、..、シンボリックリンクは使わない
- XML/JSONとアプリコードはそのまま静的解析・ビルドできる構文にする
- 何度実行しても壊れにくい処理にする
- User flag設定: {machine.needs_user_flag}, {machine.user_flag_details or "指定なし"}
- System flag設定: {machine.needs_system_flag}, {machine.system_flag_details or "指定なし"}

{HASH_CRACKING_CONSTRAINTS}

{DEPLOYMENT_VERIFICATION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
"""


def repair_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    current: GeneratedSource,
    failure_report: dict,
) -> str:
    current_json = current.model_dump_json(indent=2)
    report_json = json.dumps(failure_report, ensure_ascii=False, indent=2)
    return f"""あなたは生成済みの教育用VMソースを差分修正するエージェントです。
新規生成はせず、検査またはPackerビルドで失敗した箇所だけを修正してください。

マシン: {machine.name}
シナリオID: {scenario.scenario_id}
対象OS: {scenario.target_os}
攻撃グラフ:
```json
{scenario.attack_graph.model_dump_json(indent=2)}
```

失敗内容:
```json
{report_json}
```

失敗内容にrepair_historyが含まれる場合、そこに記録された過去の失敗と変更をすべて考慮してください。
known_failed_resourcesに列挙された要素は、現在の失敗内容に現れなくても再利用してはいけません。

現在のファイル:
```json
{current_json}
```

JSON以外は返さないでください。形式:
{{"files":[{{"path":"contents/scripts/provision.sh","content":"...","mode":"0755"}}],"delete_paths":[]}}

制約:
- filesには追加・変更が必要なファイルだけを含め、変更不要なファイルを返さない
- delete_pathsには削除が必要な既存ファイルだけを含める
- 失敗原因とその依存箇所を調べ、必要最小限の一貫した差分にする
- 複数行のビルドログがある場合は最終行だけで判断せず、失敗したコマンドと前後の文脈から
  根本原因を特定する。後処理や終了時のメッセージを原因と取り違えない
- 利用できないパッケージを隣接バージョンへ推測で置き換えない。厳密なバージョン要件がなければ、
  対象OSの標準メタパッケージまたはバージョン非依存の導入方法を優先する
- 過去の失敗で利用不可・不存在と判明したパッケージ、systemd unit、パスを再利用しない
- パッケージを変更する場合は、その名前からsystemd unit、ソケット、設定パスを推測せず、
  導入後に実在する名前をパッケージ情報またはsystemdから確認して関連設定を一貫して更新する
- パスはcontents/以下の相対パスに限定し、絶対パスと..を使わない
- 対象OSのリポジトリにないパッケージとフルOSアップグレードを使わない
- 既存のシナリオ意図、flag、manifestの整合性を維持する
- Markdownと攻撃グラフに矛盾がある場合は攻撃グラフを正とする

{HASH_CRACKING_CONSTRAINTS}

{DEPLOYMENT_VERIFICATION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
"""
