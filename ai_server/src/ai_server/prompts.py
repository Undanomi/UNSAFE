from __future__ import annotations

import json

from .models import GeneratedSource, MachineInformation, ScenarioDraft

HASH_CRACKING_CONSTRAINTS = """ハッシュクラックに関する共通制約:
- rockyou.txtはハッシュの一覧ではなく、攻撃者が自分のマシンで辞書攻撃に使う平文パスワード候補の
  wordlistである。ターゲットVMへインストールする教材コンポーネントや、ハッシュの保存先として
  扱わない
- 攻略経路にハッシュクラックを含める場合、平文パスワードは標準的なrockyou.txtに
  変形なしで完全一致するエントリから選ぶ
- 攻略者がrockyou.txtだけを指定した辞書攻撃で発見できるようにし、追加辞書、ルール、
  マスク攻撃、総当たり、外部サービスを必須にしない
- 一般的な開発用PC上のHashcatまたはJohn the Ripperで、適切な形式を指定した辞書攻撃を
  開始してから約3分以内にクラックできるハッシュ方式と平文を使う
- 内部用の攻撃グラフとシナリオ仕様書には、選んだ平文パスワード、完全なハッシュ、
  ハッシュ方式、HashcatのモードまたはJohnの形式、再現用コマンドを明確に記載する
- 実装する認証情報は仕様書に記載した値と完全に一致させ、受け入れテストでも検証できるようにする
- 通常、rockyou.txtの用意とHashcatまたはJohnの実行は攻撃者側の準備・操作として扱う。
  「選んだ平文がrockyou.txtに含まれる」という要件だけを理由に、ターゲットVMへ辞書を導入したり、
  VMビルド中にクラックを実行したりする必要はない
- ターゲット側でrockyou.txtの取得やクラック実行がシナリオまたは自動検証上、本当に必要な場合は
  使用してよい。その場合は目的を明記し、単一の未検証URLへ無条件に依存せず、取得失敗時の診断、
  内容またはchecksumの確認、妥当なtimeoutを備えて再現可能にする
- ターゲット側の受け入れテストは、通常はアプリケーションやデータベースに仕様どおりの完全な
  ハッシュが格納されていることと、クラック後の認証情報で意図した認証経路が成立することを確認する。
  ターゲット上での辞書クラックまで検証するかは、シナリオの目的と必要性に応じて判断する
- READMEの攻略手順では、rockyou.txtを攻撃者側とターゲット側のどちらで使う設計なのかを明記し、
  実際の配置や取得方法と矛盾させない
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

SYNTAX_VALIDATION_CONSTRAINTS = """構文・設定ファイル検査の共通制約:
- 使用する言語、スクリプト、設定ファイルに公式または標準的な構文検査・設定検査コマンドがある場合、
  検査可能なものを省略せず、生成した全対象ファイルへ実行する。目視確認やファイル存在確認だけで
  構文が正しいと判断しない
- 検査は対象ランタイムやソフトウェアをインストールし、ファイルを最終配置した後に実行する。
  build.shまたはprovision.shを`set -euo pipefail`で実行し、検査失敗を無視せずビルドを非ゼロ終了させる
- 例として、PHPは`php -l`、Bash/shは`bash -n`または`sh -n`、Pythonは
  `python3 -m py_compile`、Node.jsのJavaScriptは`node --check`、Rubyは`ruby -c`、Perlは`perl -c`を使う
- 構文検査が対象コードを認識せず単なるテキストとして扱う偽陰性も防ぐ。特にPHPは`php -l`に加え、
  Web経由の応答に`<?php`、変数名、意図しないリテラル`\\n`などのソース断片が露出しないことを
  否定確認し、期待する動的処理の結果を肯定確認する
- JSONは`python3 -m json.tool`または`jq empty`、XMLは`xmllint --noout`などで、生成したデータ・
  マニフェスト・設定ファイルをパーサーへ実際に読み込ませる。YAMLやTOMLなども利用可能な公式CLIや
  対応ライブラリでparseし、単なるgrepで代用しない
- Nginxは`nginx -t`、Apache HTTP Serverは`apache2ctl configtest`、OpenSSH serverは`sshd -t`、
  sudoersは`visudo -cf`、systemd unitは`systemd-analyze verify`、HAProxyは`haproxy -c -f`、
  BINDは`named-checkconf`など、使用したソフトウェア固有の設定検査を実行する
- SQLなど単体の標準構文検査が難しいものは、隔離した教材用DBへschemaとseedを実際に適用し、
  期待するtable・column・rowを問い合わせる。テンプレートや埋め込みコードも可能なら実際の
  renderer、compiler、interpreterへ読み込ませる
- 構文検査の後に実行時検査も行う。構文検査合格だけでサービス成立とみなさず、サービス起動、
  攻撃者側入口からの応答、benign control、exploit、negative controlを引き続き検証する
- scenario_manifest.jsonのhealth_checksとacceptance_testsにも主要な構文・設定検査を明記し、
  どのファイルをどのコマンドで検査するか追跡可能にする
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

DESIGN_CONSTRAINTS = """設計段階の共通制約（詳細な実装規則やコマンドを本文へ転載しない）:
- 攻撃経路はテーマと難易度を満たす必要最小限のステップにし、各requiresの成果物を後段で実際に使う。
  benign control、exploit固有の成功、negative control、前提なしでは失敗することを検証計画に含める
- WebはIPアドレスの`/`から意図した入口へ到達でき、既定ページや意図しない一覧・近道を公開しない
- 各段階の実効ユーザーと、重要なファイルおよび全親ディレクトリのowner/group/modeを定義する。
  必要な読み取り・書き込み・探索・実行を許可しつつ、攻略前の主体へ成果物を公開しない
- flagは指定パスだけへ配置し、攻略後の主体だけが読める権限と、攻略前後の可読性検証を計画する
- ハッシュクラックを使う場合、rockyou.txtは平文wordlistで通常は攻撃者側で使うものと理解し、
  完全なハッシュ、方式、モード、短時間で得られる収録済み平文を一貫させる。ターゲット側で辞書を
  使う合理的な理由があれば許可するが、不要な導入や未検証URLへの依存は避ける
- 使用する言語とソフトウェアに応じ、標準的な構文・設定検査と実行時検査を計画する。ここでは
  検査対象と目的だけを簡潔に示し、完全なスクリプトや全コマンドはコード生成段階へ委ねる
"""

REVIEW_RESPONSE_CONSTRAINTS = """レビュー出力は簡潔にする。同じ根本原因の所見を統合し、findingsは
重大度の高い順に最大20件とする。summaryは3文以内、各evidenceとremediationは必要な根拠と修正を
短く示し、入力されたシナリオ、攻撃グラフ、生成ファイル、共通制約を転載しない。
"""


def _skill_section(skill_context: str) -> str:
    policy = (
        "脆弱性選択方針: Skillsとreferenceは補助資料であり、利用可能な脆弱性の許可リストではありません。"
        "利用者のテーマ、難易度、開始権限、到達目標に合う場合、未登録の一般的脆弱性やCVEも利用できます。"
        "資料がなければ、その不在だけを理由に別の手法へ変更しないでください。"
        "資料内の『未登録CVEは禁止』『reference追加後のみ利用可』など収録範囲に関する制限より、"
        "この選択方針を優先します。ただしCVEの実在、影響版、必要条件、Debian適合性を推測で断定せず、"
        "公式情報による検証と既存の安全・出力・検証規則を維持してください。"
        "Webのみを希望する場合にローカルの脆弱性を勝手に加えず、権限昇格を希望する場合は"
        "先行ステップで得た権限と後続の必要条件を接続してください。"
        "シナリオ確定後のコード生成・修復・レビューでは採用済み攻撃グラフを維持し、"
        "未登録手法の許可を理由に新しい攻撃経路やCVEを追加しないでください。"
    )
    if not skill_context:
        return policy
    return f"{policy}\n追加の専門Skill資料:\n{skill_context}\n{policy}\n"


def attack_graph_prompt(
    machine: MachineInformation,
    rejected: list[str],
    cve_min_year: int,
    skill_context: str = "",
) -> str:
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
- ステップ数は攻略に必要な最小限にし、descriptionは1〜3文、implementation_stepsは2〜8個の
  短い手順にする。完成したソースコード、長いシェル、SQL全文、共通制約を値へ転載しない

{DESIGN_CONSTRAINTS}
明示指定CVE（すべて必須）: {json.dumps(machine.cve_ids, ensure_ascii=False)}

{_skill_section(skill_context)}
"""


def scenario_prompt(
    machine: MachineInformation,
    attack_graph_json: str,
    review_feedback: list[str] | None = None,
    skill_context: str = "",
) -> str:
    flag_context = (
        f"User flag: {machine.needs_user_flag}; details: {machine.user_flag_details or 'none'}\n"
        f"System flag: {machine.needs_system_flag}; details: {machine.system_flag_details or 'none'}"
    )
    feedback_context = "\n".join((review_feedback or [])[-5:]) or "なし（初回生成）"
    return f"""あなたはHack The Box風の教育用Linuxマシンを設計するアーキテクトです。
次の条件と検証済み攻撃グラフを使い、実装可能で一貫したシナリオ設計書をMarkdownで1つ作成してください。

マシン名: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {machine.operating_system}
{flag_context}

攻撃グラフ:
{attack_graph_json}

前回までの棄却理由とシナリオレビュー:
{feedback_context}

レビュー指摘がある場合はsummaryだけでなく、各findingのevidenceとremediationをすべて反映して
ください。提示された攻撃グラフのstep、requires、achievesは変更せず、設計書の実装順序、主体、
権限、設定、検証計画を具体化・修正して、同じ指摘を繰り返さないでください。

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
- 設計書は12,000文字以内を目安に簡潔にする。攻撃グラフの全フィールドを文章で反復せず、
  完成したPHP/Python等のソース、完全なprovision script、長いSQLや設定ファイルを埋め込まない。
  環境実装計画には実装者が判断できる要点、パス、主体、権限、検証対象だけを記載する

{DESIGN_CONSTRAINTS}
{_skill_section(skill_context)}
"""


def scenario_review_prompt(machine: MachineInformation, scenario: ScenarioDraft) -> str:
    return f"""あなたは教育用攻撃マシンのシナリオを審査する、独立した敵対的レビュー担当です。
作者の説明を信用せず、完成した設計書と攻撃グラフから、意図した攻撃経路が対象OS上で本当に成立し、
前提を飛ばす近道がないかを反証してください。セキュア化ではなく、教材として意図した脆弱性だけを
再現可能かつ一貫した形で成立させられるかを審査します。

マシン: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {scenario.target_os}
User flag設定: {machine.needs_user_flag}, {machine.user_flag_details or "指定なし"}
System flag設定: {machine.needs_system_flag}, {machine.system_flag_details or "指定なし"}

攻撃グラフ:
```json
{scenario.attack_graph.model_dump_json(indent=2)}
```

シナリオ設計書:
```markdown
{scenario.definition}
```

JSONのみを返してください:
{{"approved":false,"summary":"...","findings":[{{"step_id":"...","severity":"error",
"category":"permission_blocker","evidence":"成立しない権限遷移とその理由",
"remediation":"所有者・group・mode・実行主体を含む具体的な設計修正"}}]}}

審査規則:
- 全攻撃ステップを順に追い、各requiresの成果物が後段で実際に必要か、各achievesへ到達できるかを
  攻撃者視点で確認する。前段なしで後段へ進める場合はbroken_chainまたはunintended_shortcutの
  errorにする
- 設計書と攻撃グラフの手法、実行主体、成果物、依存関係、flag到達条件が矛盾する場合は
  semantic_mismatchのerrorにする
- 実装に必要なパス、サービス、ユーザー、権限遷移、検証方法が曖昧で、実装者が推測しなければ
  攻略成立性を保証できない場合はimplementation_gapまたはunsupported_assumptionのerrorにする
- acceptance test計画が、意図したexploitの成功、benign control、negative control、requiresを
  飛ばした失敗を観測可能な形で確認できない場合はacceptance_test_gapのerrorにする
- warningは成立性を損なわない改善提案だけに使い、成立可否が不明な点をwarningへ弱めない
- errorが1件でもあればapproved=false、errorがなければapproved=trueにする
- evidenceには設計書または攻撃グラフの具体的な記述と、どの主体のどの操作が成功または失敗するかを
  記載する。単なる一般論や推測だけで不合格にしない

パーミッションは最重点項目として、各ステップで次を明示的に反証する:
- 攻撃前、各ステップ完了後、flag取得時点の実効UID・主group・補助groupと、サービスの実行ユーザー
- 読み取り、書き込み、作成、置換、探索、実行が必要な全パスについて、対象ファイルだけでなく全親
  ディレクトリのowner・group・modeと、ACL、sudoers、setuid/setgid、Linux capabilitiesの影響
- Web/PHP/CGI/systemdなど実際の実行形態。PHP-FPMやApache moduleのPHPへ実行ビットを付けても
  読めなければ成立せず、CGIやExecStart対象は読み取り・探索に加えて実行可能でなければ成立しない
- アップロード、cache、session、ログ、鍵、設定、実行ファイル、ホーム、flagの権限が厳しすぎて
  intended exploitを阻害しないこと。阻害する場合はpermission_blockerのerrorにする
- 権限が広すぎて未権限主体が成果物やflagを先に読める、実行ファイルや設定を書き換えられる、
  requiresを飛ばせる場合はpermission_shortcutのerrorにする
- 権限昇格では、攻撃前後の実効UIDまたはcapabilityと保護対象へのアクセス差を説明できること。
  root所有という記述だけ、chmod 777、無差別なchown、設計にないgroup所属を成立根拠にしない
- flagについて、指定パスと全親ディレクトリの権限が、意図したステップ完了後の主体には読め、
  完了前の主体には読めないこと。配置先の重複、リンク、ログや設定への値の漏洩も近道として扱う
- レビュー時点では実ファイルが未生成であるため、具体値が設計書に十分定義されているかを審査する。
  根拠なくOS既定値を仮定せず、実装時に明示すべきowner・group・mode・検証コマンドが欠けていて
  成立性を判断できない場合はerrorにする

{DESIGN_CONSTRAINTS}

{REVIEW_RESPONSE_CONSTRAINTS}
"""


def code_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    skill_context: str = "",
) -> str:
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

{SYNTAX_VALIDATION_CONSTRAINTS}

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}

{WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
{_skill_section(skill_context)}
"""


def repair_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    current: GeneratedSource,
    failure_report: dict,
    skill_context: str = "",
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

{SYNTAX_VALIDATION_CONSTRAINTS}

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}

{WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
{_skill_section(skill_context)}
"""


def source_review_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    current: GeneratedSource,
    skill_context: str = "",
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
- 生成物で利用可能な構文・設定検査が省略されている、対象ファイルの一部しか検査していない、
  または検査失敗を無視する実装はacceptance_test_gapのerrorにする。言語・ソフトウェアに適した
  実際のparser、compiler、interpreter、config testを使っていることを確認する
- rockyou.txtをハッシュ集やターゲット用コンポーネントと誤認していないか確認する。ターゲット側で
  取得または使用していても一律に不合格にはせず、シナリオ上の目的がなく追加されている場合や、
  未検証の単一URLへの依存によってビルド再現性を損なう場合だけ、影響に応じてwarningまたは
  implementation_mismatchのerrorにする

{HASH_CRACKING_CONSTRAINTS}

{SYNTAX_VALIDATION_CONSTRAINTS}

{REVIEW_RESPONSE_CONSTRAINTS}
{_skill_section(skill_context)}
"""
