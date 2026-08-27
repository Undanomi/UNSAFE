from __future__ import annotations

import json

from .models import GeneratedSource, MachineInformation, ScenarioDraft


def scenario_prompt(machine: MachineInformation, cve_context: str) -> str:
    flag_context = (
        f"User flag: {machine.needs_user_flag}; details: {machine.user_flag_details or 'none'}\n"
        f"System flag: {machine.needs_system_flag}; details: {machine.system_flag_details or 'none'}"
    )
    return f"""あなたはHack The Box風の教育用Linuxマシンを設計するアーキテクトです。
次の条件と検証済みCVE情報を使い、実装可能で一貫したシナリオ設計書をMarkdownで1つ作成してください。

マシン名: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {machine.operating_system}
{flag_context}

{cve_context}

必ず次の章をこの順で含めてください。
# [マシン名] シナリオ設計書
## 1. 基本情報 (Metadata)
## 2. 背景ストーリー & コンテキスト
## 3. 初期潜入フェーズ
## 4. 権限昇格フェーズ (Privilege Escalation)
## 5. 教育的価値

各脆弱性にはCVE-ID、対象コンポーネント、脆弱な厳密バージョン、対象OSとの適合根拠、
CWE、公式解説、偵察、攻撃の概要、脆弱版の入手元とインストール手順、PoCリファレンスを
記載してください。与えられた検証済み導入情報を省略せず、URLを捏造しないでください。
"""


def code_prompt(machine: MachineInformation, scenario: ScenarioDraft) -> str:
    return f"""あなたは隔離された教育用Linux VMのプロビジョニングコードを作る専門家です。
次のシナリオを{scenario.target_os}ベースのPacker VM内へ導入するファイル群を生成してください。

{scenario.definition}

検証済みのCVE導入計画:
{json.dumps([item.model_dump(mode="json") for item in scenario.cve_installation], ensure_ascii=False, indent=2)}

JSON以外は返さないでください。形式:
{{"files":[{{"path":"contents/build.sh","content":"#!/bin/bash\\nset -euo pipefail\\n...","mode":"0755"}}]}}

制約:
- Packerは生成ルートを /tmp/scenario にコピーし、rootで contents/build.sh を実行する
- contents/README.md、contents/scenario_manifest.json、contents/build.sh、
  contents/scripts/provision.sh を必ず生成する
- scenario_manifest.json は required_files、services、acceptance_tests、
  expected_vulnerabilities、health_checks を空でない配列として持ち、target_osを
  `{scenario.target_os}` とする
- required_files は contents/ 基準で、生成する全必須ファイルと一致させる
- build.sh は #!/bin/bash と set -euo pipefail を使い、
  /tmp/scenario/contents がカレントディレクトリである前提で bash ./scripts/provision.sh を呼ぶ
- アプリは contents/app/、設定は contents/config/ に置く
- OSパッケージ付属のsystemd unitを優先し、ビルド中の対話入力と再起動を避ける
- {scenario.target_os}の標準パッケージリポジトリに存在することを確認できないパッケージ名を使わない
- 対象OSがUbuntu 26.04の場合は `apt install tomcat9` を使わない
- `apt upgrade`、`apt-get upgrade`、カーネル更新を行わない。必要なパッケージだけを導入する
- ベースOS自体を古い脆弱カーネルへ変更せず、再現対象はアプリケーションや隔離した教材として実装する
- READMEにはPackerビルド、ヘルスチェック、脆弱性再現・flag確認を記載する
- 絶対パス、..、シンボリックリンクは使わない
- XML/JSONとアプリコードはそのまま静的解析・ビルドできる構文にする
- 何度実行しても壊れにくい処理にする
- User flag設定: {machine.needs_user_flag}, {machine.user_flag_details or "指定なし"}
- System flag設定: {machine.needs_system_flag}, {machine.system_flag_details or "指定なし"}
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

失敗内容:
```json
{report_json}
```

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
- パスはcontents/以下の相対パスに限定し、絶対パスと..を使わない
- 対象OSのリポジトリにないパッケージとフルOSアップグレードを使わない
- 対象OSがUbuntu 26.04の場合は `apt install tomcat9` を使わない
- 既存のシナリオ意図、flag、manifestの整合性を維持する
"""
