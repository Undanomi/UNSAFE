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

WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS = """Web公開品質とパーミッションの共通制約:
- HTTP/HTTPSサービスを作る場合、攻撃者がDNS名、Hostヘッダー、隠しパスを知らなくても、
  ブラウザへターゲットのIPアドレスだけを入力すれば意図した入口へ到達できるようにする
- アプリを`/`で直接提供するか、`/`から正しいランディングページへリダイレクトする。名前ベースの
  VirtualHostを使う場合も、IP宛て要求を受けるdefault_serverまたはcatch-allを必ず構成する
- 通常は`/`にシナリオ固有のタイトル、デザイン、自然な導線を備えた完成済みページを用意し、
  Webサーバー既定ページ、素の404、意図しないファイル一覧を利用者へ見せない
- 攻撃グラフがディレクトリリスティングを攻略要素として明示している場合に限り、Apacheの
  `Options Indexes`やNginxの`autoindex on`などを必要なパスへ限定して構成する。公開する項目と
  そこから得られる成果物をシナリオに一致させ、別パスや不要なファイルまで露出させない
- build.shから実行されるシェルとmanifestのhealth_checks/acceptance_testsの両方で、Hostを
  上書きせず`curl -fsSL http://127.0.0.1/`相当を実行し、アプリ固有マーカーを肯定確認する。
  ディレクトリリスティングを意図する場合は必要なパスと項目を肯定確認し、意図しない場合は
  `Index of`やWebサーバー既定ページが含まれないことを否定確認する
- 配置時は所有者、group、modeを偶然の既定値に任せず、`install -d -m`、`install -m`、
  `chown`、限定的な`chmod`で明示する。ディレクトリは通常0755/0750、静的ファイルと通常の
  PHPソースは0644/0640、秘密情報は0600/0640、実行スクリプトは0755/0750を基準にする
- PHP-FPMやApache moduleで読むPHPは実行ビットではなくWeb実行ユーザーの読み取り権限と全親
  ディレクトリの探索権限を保証する。CGIとして直接実行するPHPはshebangと実行ビットを必須にする
- `.sh`、CGI、サービスのExecStart対象など実行される生成ファイルはJSONのmodeを0755にし、
  最終配置後のモードも明示する。設定・ソース・秘密情報へ理由なく実行ビットを付けない
- Web実行ユーザーを実際のunit/FPM pool/Apache設定から確認し、そのユーザーで`test -r`、必要なら
  `test -x`を実行する。`namei -l`または`stat`でも所有者・mode・親ディレクトリを検査する
- アップロード、cache、sessionなど攻略上必要な場所だけを書き込み可能にし、DocumentRoot全体への
  `chmod -R 777`、無差別な所有者変更、world-writable化で権限問題を回避しない
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

EXPLOITABILITY_VERIFICATION_CONSTRAINTS = """攻略成立性と意図しない近道の共通制約:
- 各攻撃ステップについて、前提状態、攻撃者が外部から行う具体的操作、成功時だけ得られる観測可能な
  証拠、次ステップへ渡す成果物を明確にし、単なるサービス起動やエラー発生を攻略成功とみなさない
- 意図した脆弱性が「存在する」だけでなく「攻略に必要」であることを保証する。通常入力、通常機能、
  初期画面、公開ファイル、バナー、コメント、既定認証情報から同じ成果物を先に取得できる近道を作らない
- 正常系のbenign controlでは秘密・認証情報・flag・次工程の成果物を取得できず、意図したexploitでは
  それを取得でき、似ているが成立しないnegative controlでは取得できないことを対にして検証する
- exploitの検証は脆弱性種別に固有の効果を証明する。SQLiなら通常検索や単なるSQLエラーではなく、
  攻撃用入力による本来取得不能な行の抽出、パストラバーサルなら通常の公開ファイルではなく許可範囲外
  ファイルの取得、権限昇格なら実効UIDや保護対象へのアクセス変化などを確認する
- 攻撃グラフの各requiresについて、前段の成果物なしでは後段が成功せず、前段で得た実値を使うと
  成功することを検証する。構築用スクリプトが成果物を知っていることを攻略可能性の証明に使わない
- acceptance_testsには、攻撃者が利用する入口から実行するbenign control、exploit、negative controlを
  ステップIDと対応付けて記載し、期待文字列をechoするだけ、ソースをgrepするだけ、DBを直接読むだけの
  自己充足的なテストにしない
- 実装または修復の完了前に、より短い別経路、情報の先出し、意図しない別種の脆弱性、前提を飛ばせる
  権限や認証情報がないか攻撃者視点で反証し、見つかった場合は完成扱いにしない
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

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}

{WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS}

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

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}

{WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS}

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
- JSONのfiles[].pathはVM内の最終配置先ではなく生成ZIP内のパスであり、必ずcontents/から始める。
  `/var/www`、`/etc`、`/opt`などの最終配置先をfiles[].pathへ返さず、contents/app/や
  contents/config/のファイルをcontents/scripts/provision.sh内のinstall/cpで最終配置する
- 同じpathをfilesへ複数回含めない。特にcontents/scenario_manifest.jsonは必ず1ファイルだけにする
- scenario_manifest.jsonのcontentはMarkdownやコメントを含まない厳密なJSON objectにし、単独で
  Pythonのjson.loadsに成功する形式にする。command文字列内のバックスラッシュもJSON規則で
  必ずエスケープし、セミコロンやドル記号の直前に未定義のJSONエスケープを作らない
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

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}

{WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS}

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
- 同じpathをfilesへ複数回含めない
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
- files[].pathは生成ソース内の既存パスまたは追加パスであり、VM内の最終配置先ではない。
  `/var/www`、`/etc`、`/opt`などを直接files[].pathへ返さず、contents/app/、contents/config/、
  contents/scripts/以下を修正し、VMへの配置変更はprovision.shのinstall/cp/chownで行う
- 対象OSのリポジトリにないパッケージとフルOSアップグレードを使わない
- 既存のシナリオ意図、flag、manifestの整合性を維持する
- contents/scenario_manifest.jsonを変更する場合、そのcontentはMarkdownやコメントを含まない
  厳密なJSON objectとし、単独でPythonのjson.loadsに成功させる。command文字列内の
  バックスラッシュもJSON規則で必ずエスケープし、セミコロンやドル記号の直前に未定義の
  JSONエスケープを作らない
- Markdownと攻撃グラフに矛盾がある場合は攻撃グラフを正とする

{HASH_CRACKING_CONSTRAINTS}

{DEPLOYMENT_VERIFICATION_CONSTRAINTS}

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}

{WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
"""


def source_review_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    current: GeneratedSource,
) -> str:
    return f"""あなたは教育用攻撃マシンの独立した敵対的レビュー担当です。
作者の説明やmanifestの自己申告を信用せず、攻撃グラフと実装ファイルを突き合わせてください。
セキュアに修正するレビューではなく、意図した脆弱性だけが指定経路で攻略可能かを審査します。

マシン: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {scenario.target_os}
攻撃グラフ:
```json
{scenario.attack_graph.model_dump_json(indent=2)}
```

生成ファイル:
```json
{current.model_dump_json(indent=2)}
```

JSONのみを返してください:
{{"approved":false,"summary":"...","findings":[{{"step_id":"...","severity":"error",
"category":"unintended_shortcut","evidence":"ファイルと具体的挙動","remediation":"必要な修正"}}]}}

審査規則:
- 全攻撃ステップを順に追い、実装コード、provision、manifest、acceptance_testsの整合性を確認する
- intended techniqueを使わず同じ成果物を得られる場合はunintended_shortcutのerrorにする
- 攻撃固有の効果を証明せず、通常入力、エラー、接続成功だけを確認するテストはunproven_exploitまたは
  acceptance_test_gapのerrorにする
- 実装された主脆弱性が攻撃グラフの種類と異なる場合はwrong_techniqueのerrorにする
- requiresを飛ばせる、または前段の成果物が後段で実際に使われない場合はbroken_chainのerrorにする
- コメントや名前にSQLi等と書いてあること、expected_vulnerabilitiesの宣言、READMEの攻略説明だけを
  実装証拠として認めない。実際のデータフローと外部からの観測結果を根拠にする
- errorが1件でもあればapproved=false、errorがなければapproved=trueにする
- evidenceには判断に使ったファイルパス、変数、通常経路と攻撃経路の差を具体的に記載する

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}
"""
