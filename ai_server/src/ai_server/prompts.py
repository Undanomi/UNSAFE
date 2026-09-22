from __future__ import annotations

import json

from .models import AttackGraph, GeneratedSource, MachineInformation, ScenarioDraft

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

INSTALLATION_PREFERENCE_CONSTRAINTS = """ソフトウェア取得方法の共通制約:
- ソースコードからのコンパイルを既定にしない。必要な厳密バージョンについて、対象Debianの通常または
  snapshot APTリポジトリ、ベンダー公式APTリポジトリ、ベンダー公式releaseのビルド済みバイナリ、
  信頼できる既存のビルド済み成果物の順に調査し、利用可能なものを優先する
- パッケージ名が存在するだけでなく、対象アーキテクチャ、対象OSで解決可能な依存関係、必要な脆弱版、
  配布元の信頼性を確認する。導入後は実際のバージョンをコマンドで検証し、最新版への暗黙更新を防ぐ
- 外部成果物はHTTPSの公式配布元を優先し、可能ならリポジトリ署名、ベンダー署名、公開checksumの
  いずれかを検証する。未固定のlatest URLや、出所不明の第三者バイナリへ置き換えない
- ソースビルドは、上記のビルド済み経路を調査しても対象OS・アーキテクチャ・厳密バージョンに適合する
  成果物がない場合だけ使う。その場合は、調査した各配布元と利用できない理由、固定したソース版、
  checksum、ビルド依存、ビルド結果のバージョン確認をシナリオ、manifest、実装で追跡可能にする
- 修復時にパッケージ取得や依存関係で失敗しても、直ちにソースビルドへ切り替えない。失敗した取得元と
  コマンドをレポートから確認し、別の公式なビルド済み配布経路を先に検討する
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
  `test -x`を実行する。`namei -l`または`stat`でも所有者・mode・親ディレクトリを検査する。
  `stat`だけでは実効アクセスの検証にならない。例えばWebユーザーが`www-data`で公開ファイルが
  `/var/www/html/index.php`なら、`namei -l /var/www/html/index.php`と
  `runuser -u www-data -- test -r /var/www/html/index.php`の両方を、build.shから実行されるシェルと
  scenario_manifest.jsonのhealth_checksまたはacceptance_testsへそれぞれ入れる
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
- acceptance test専用のmarker、payload、header、query等をアプリ側で特別扱いし、脆弱性を経由せず
  成功時のファイル作成や応答を直接発生させる分岐を実装しない
- sudo、runuser、su等で攻略後のユーザーへ直接切り替えてflagを読む操作をexploitの証明に使わない。
  攻撃者入口から実際のpayloadを送り、その結果として得た能力または出力でflag到達を証明する
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
      "cve_title": null,
      "cve_description": null,
      "cwe_ids": [],
      "installation_artifact": null,
      "artifact_source": null,
      "source_build_reason": null,
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
- 非CVEステップではcve_id、cve_title、cve_description、installation_artifact、
  artifact_source、source_build_reasonをnull、cwe_idsを空配列にする。脆弱版ソフトウェアの導入情報は
  対応するkind=cveのステップへ記載し、reconnaissanceやセットアップ用ステップへ重複させない
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
    previous_scenario: ScenarioDraft | None = None,
) -> str:
    flag_context = (
        "detailsはflag正解値でもCVE指定でもありません。CVEはcve_idsだけを正とします。\n"
        f"User flag required: {machine.needs_user_flag}; acquisition details: "
        f"{machine.user_flag_details or 'none'}\n"
        f"System flag required: {machine.needs_system_flag}; acquisition details: "
        f"{machine.system_flag_details or 'none'}"
    )
    feedback_context = "\n".join((review_feedback or [])[-5:]) or "なし（初回生成）"
    previous_context = ""
    if previous_scenario is not None:
        previous_context = f"""
前回保存されたドラフトを破棄せず、次の文章を直接修正してください。レビュー指摘と検証済み攻撃
グラフに関係しない部分は維持し、全文を別案として作り直さないでください。

前回のプレイヤー向け紹介文:
```text
{previous_scenario.scenario_description}
```

前回のシナリオ設計書:
```markdown
{previous_scenario.definition}
```
"""
    return f"""あなたはHack The Box風の教育用Linuxマシンを設計するアーキテクトです。
次の条件と検証済み攻撃グラフを使い、プレイヤー向けの紹介文と、実装者向けの一貫した
シナリオ設計書を作成してください。

マシン名: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {machine.operating_system}
{flag_context}

攻撃グラフ:
{attack_graph_json}

前回までの棄却理由とシナリオレビュー:
{feedback_context}
{previous_context}

レビュー指摘がある場合はsummaryだけでなく、各findingのevidenceとremediationをすべて反映して
ください。提示された攻撃グラフのstep、requires、achievesは変更せず、設計書の実装順序、主体、
権限、設定、検証計画を具体化・修正して、同じ指摘を繰り返さないでください。

JSONのみを返してください:
{{"scenario_description":"プレイヤー向け紹介文","definition":"Markdown形式のシナリオ設計書"}}

scenario_descriptionは、シナリオの背景や雰囲気、調査する動機、学習テーマなどから適切な要素を選び、
プレイヤーが挑戦したくなる自然な日本語で自由に記述してください。特定の役割設定、文体、文章構成、
定型的な書き出しは要求しません。最後は「対象マシンを調査すること」と「フラグを獲得すること」の
両方が具体的に伝わる指示文で、直前までの背景説明から自然につなげてください。例えば、侵害が疑われる
サーバーという背景なら「サーバー内部を詳しく調べ、攻撃の証拠とともにフラグを見つけ出して下さい」、
設定不備を扱う演習なら「マシンの構成を調査し、隠されたフラグを取得してください」のような流れです。
例文を定型句として逐語的に使う必要はありません。「ください／下さい」「獲得／取得／発見」などの
表記や語彙は、文章全体として自然で意味が明確なら自由に選んでください。
テーマまたは脆弱性の大分類には触れて構いませんが、具体的な攻撃手順、侵入口、URLやパス、ポート、
製品バージョン、認証情報、コマンド、権限昇格経路、フラグの場所や値、攻撃連鎖の順序は明かさないで
ください。Markdownは使わず、設計書と矛盾する説明にしないでください。

definitionには必ず次の章をこの順で含めてください。
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
- CVEステップのcve_title、cve_description、cwe_idsは公式レコード由来の不変な事実です。
  別の脆弱性メカニズムや一般的な設定不備へ読み替えず、「仮想」「模擬」「simulated」として扱わず、
  公式の発火条件、影響、前提条件をそのまま設計の根拠にしてください。再現不能なら成立可能と捏造せず、
  レビューで不合格になる具体的な不足として残してください
- 設計書は12,000文字以内を目安に簡潔にする。攻撃グラフの全フィールドを文章で反復せず、
  完成したPHP/Python等のソース、完全なprovision script、長いSQLや設定ファイルを埋め込まない。
  環境実装計画には実装者が判断できる要点、パス、主体、権限、検証対象だけを記載する

{DESIGN_CONSTRAINTS}
{_skill_section(skill_context)}
"""


def attack_graph_revision_prompt(
    machine: MachineInformation,
    attack_graph: AttackGraph,
    review_feedback: dict,
) -> str:
    return f"""あなたは検証済み攻撃グラフの限定修正担当です。
シナリオレビューが攻撃グラフ自体に指摘した矛盾だけを修正し、完全なAttackGraph JSONを返してください。

マシン: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {machine.operating_system}

現在の攻撃グラフ:
```json
{attack_graph.model_dump_json(indent=2)}
```

レビュー指摘:
```json
{json.dumps(review_feedback, ensure_ascii=False, indent=2)}
```

JSON以外は返さないでください。

制約:
- objectivesおよび各stepのstep_id、kind、phase、requires、achieves、cve_idは変更しない
- cve_title、cve_description、cwe_ids、software、vulnerable_version、os_compatible、
  compatibility_reason、installation_artifact、artifact_source、source_build_reason、
  installation_method、referencesは公式検証済み情報なので変更しない
- レビューが指摘したstepのtitle、description、implementation_stepsだけを必要最小限修正する
- レビュー指示がAttackGraphのモデル制約または上記の変更禁止フィールドと衝突する場合は、その指示に
  従って禁止フィールドを変更せず、現在の攻撃グラフをそのまま返す
- Markdown側だけの問題を攻撃グラフへ持ち込まず、新しいstep、CVE、攻撃経路、到達目標を追加しない
- remediationをコピーするだけでなく、矛盾する旧バージョン、旧設定例、曖昧な表現を実際に置換する
"""


def scenario_correction_prompt(
    machine: MachineInformation,
    attack_graph: AttackGraph,
    previous_scenario: ScenarioDraft,
    review_feedback: list[str],
    skill_context: str = "",
) -> str:
    return f"""あなたは既存シナリオ文書の限定修正担当です。
シナリオレビューのerror指摘だけを直す、完全一致の文字列置換パッチをJSONで返してください。
文書全体を生成し直してはいけません。

マシン: {machine.name}
難易度: {machine.difficulty}
対象OS: {machine.operating_system}

現在の攻撃グラフ:
```json
{attack_graph.model_dump_json(indent=2)}
```

現在のプレイヤー向け紹介文:
```text
{previous_scenario.scenario_description}
```

現在のシナリオ設計書:
```markdown
{previous_scenario.definition}
```

レビュー指摘:
{chr(10).join(review_feedback[-5:])}

JSONのみを返してください:
{{
  "scenario_description": null,
  "definition_replacements": [
    {{"old": "現在の文書に1回だけ現れる原文", "new": "指摘を反映した置換後の文章"}}
  ]
}}

規則:
- oldは現在のシナリオ設計書から一字一句そのまま抜き出し、必ず1回だけ現れる範囲にする
- 指摘箇所ごとに必要最小限の置換を作り、definition全体や章全体をoldに入れない
- 指摘と無関係な背景、攻撃経路、手順、数値、パス、章構成、文体を変更しない
- 内容の追加は、既存の一文をoldとし、その一文と追記をnewに含める
- 内容の削除はnewを空文字列にしてよい
- プレイヤー向け紹介文の修正が不要ならscenario_descriptionはnullにする
- 修正後の設計書は12,000文字を超えない。現在長い場合は、指摘箇所周辺の重複説明も同時に簡潔化する
{_skill_section(skill_context)}
"""


def scenario_compaction_prompt(
    machine: MachineInformation,
    scenario_description: str,
    definition: str,
) -> str:
    return f"""次のシナリオ設計書は12,000文字制限を超えています。
新しい案へ作り直さず、内容を10,500文字以内へ圧縮した完全な文書をJSONで返してください。

マシン: {machine.name}
対象OS: {machine.operating_system}

プレイヤー向け紹介文:
```text
{scenario_description}
```

シナリオ設計書:
```markdown
{definition}
```

JSONのみを返してください:
{{"scenario_description":"既存の紹介文","definition":"圧縮後の完全なMarkdown"}}

規則:
- 必須の章見出し、攻撃グラフの各step、requires、achieves、CVE公式情報、厳密バージョン、パス、
  権限、実行主体、検証条件、フラグ到達条件は削除・変更しない
- 重複説明、同じフィールドの逐語的な反復、冗長な背景、完成コード、長いコマンド例を優先して短縮する
- 新しい攻撃経路、設定、前提、URLを追加しない
- definitionは余裕を持って10,500文字以内にする
"""


def scenario_review_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    review_context: str = "generation",
    reconsideration: dict | None = None,
) -> str:
    reconsideration_section = ""
    if reconsideration is not None:
        reconsideration_section = f"""
前回レビューの再検討資料:
```json
{json.dumps(reconsideration, ensure_ascii=False, indent=2)}
```
生成物の修正案がサーバー検証に失敗しました。修正案だけでなく、前回レビューの前提や修正先が
誤っていた可能性も検討してください。修正案だけが誤りなら指摘を維持し、検証可能な修正内容へ具体化
してください。検証エラーを回避する内容を捏造せず、指摘が誤りなら撤回し、
限定修正で扱えない構造問題ならattack_graph_regeneration、入力条件の問題ならuser_inputへ変更して
シナリオ全体を改めて判定してください。同じ根拠のない修正要求を繰り返さないでください。
"""
    return f"""あなたは教育用攻撃マシンのシナリオを審査する、独立した敵対的レビュー担当です。
作者の説明を信用せず、完成した設計書と攻撃グラフから、意図した攻撃経路が対象OS上で本当に成立し、
前提を飛ばす近道がないかを反証してください。セキュア化ではなく、教材として意図した脆弱性だけを
再現可能かつ一貫した形で成立させられるかを審査します。

マシン: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {scenario.target_os}
レビュー対象工程: {review_context}
User flag取得要件（正解値ではない）: {machine.needs_user_flag}, {machine.user_flag_details or "指定なし"}
System flag取得要件（正解値ではない）: {machine.needs_system_flag}, {machine.system_flag_details or "指定なし"}
明示指定CVE（この一覧だけをCVE要件として扱う）: {json.dumps(machine.cve_ids, ensure_ascii=False)}

プレイヤー向け紹介文:
```text
{scenario.scenario_description}
```

攻撃グラフ:
```json
{scenario.attack_graph.model_dump_json(indent=2)}
```

シナリオ設計書:
```markdown
{scenario.definition}
```
{reconsideration_section}

JSONのみを返してください:
{{"approved":false,"summary":"...","findings":[{{"step_id":"...","severity":"error",
"category":"permission_blocker","repair_target":"scenario_text","repair_fields":[],
"evidence":"成立しない権限遷移とその理由",
"remediation":"所有者・group・mode・実行主体を含む具体的な設計修正"}}]}}

審査規則:
- プレイヤー向け紹介文の締めから、対象マシンを調査することとフラグを獲得することの両方が明確に
  読み取れない場合はsemantic_mismatchのerrorにする。特定の定型句や表記の完全一致は要求しない
- プレイヤー向け紹介文が設計書と矛盾する、または具体的な侵入口、URLやパス、ポート、製品バージョン、
  認証情報、コマンド、権限昇格経路、フラグの場所や値、攻撃連鎖の順序を漏らす場合は
  description_spoilerのerrorにする。役割、状況、目的、脆弱性の大分類だけなら許容する
- 全攻撃ステップを順に追い、各requiresの成果物が後段で実際に必要か、各achievesへ到達できるかを
  攻撃者視点で確認する。前段なしで後段へ進める場合はbroken_chainまたはunintended_shortcutの
  errorにする
- 設計書と攻撃グラフの手法、実行主体、成果物、依存関係、flag到達条件が矛盾する場合は
  semantic_mismatchのerrorにする
- CVEステップのcve_title、cve_description、cwe_idsは公式事実。設計書が別の脆弱性、設定不備、
  模擬実装へ置き換えていればsemantic_mismatchのerrorにする
- installation_artifactとartifact_sourceが示すビルド済み配布経路を設計書が維持しているか確認する。
  source_buildの場合はsource_build_reasonに、先行するパッケージ・公式バイナリ経路を利用できない
  具体的根拠がなければunsupported_assumptionのerrorにする
- 実装に必要なパス、サービス、ユーザー、権限遷移、検証方法が曖昧で、実装者が推測しなければ
  攻略成立性を保証できない場合はimplementation_gapまたはunsupported_assumptionのerrorにする
- acceptance test計画が、意図したexploitの成功、benign control、negative control、requiresを
  飛ばした失敗を観測可能な形で確認できない場合はacceptance_test_gapのerrorにする
- warningは成立性を損なわない改善提案だけに使い、成立可否が不明な点をwarningへ弱めない
- errorが1件でもあればapproved=false、errorがなければapproved=trueにする
- evidenceには設計書または攻撃グラフの具体的な記述と、どの主体のどの操作が成功または失敗するかを
  記載する。単なる一般論や推測だけで不合格にしない
- repair_target: scenario_text=本文、attack_graph=限定修正、attack_graph_regeneration=再作成、
  source_code=実装(source_sync時のみ)、user_input=入力
- attack_graphはtitle、description、implementation_stepsのみ。repair_fieldsに列挙し、他は再作成とする

パーミッションは最重点項目として、各ステップで次を明示的に反証する:
- 重要パスのowner・group・mode・ACL・sudoers・capabilityと各主体の可否を時系列の権限表で検証する
- 同じ時点・同じパスに対して「読める／読めない」、異なるowner・group・modeなど相反する記述が
  1つでもあればsemantic_mismatchのerrorにする。negative controlの条件を完成構成へ混入させない
- 攻撃前、各ステップ完了後、flag取得時点の実効UID・主group・補助groupと、サービスの実行ユーザー
- 必要な全パスと親ディレクトリのowner・group・mode、ACL、sudoers、setuid/setgid、capability
- Web/PHP/CGI/systemdなど実際の実行形態。PHP-FPMやApache moduleのPHPへ実行ビットを付けても
  読めなければ成立せず、CGIやExecStart対象は読み取り・探索に加えて実行可能でなければ成立しない
- アップロード、cache、session、ログ、鍵、設定、実行ファイル、ホーム、flagの権限が厳しすぎて
  intended exploitを阻害しないこと。阻害する場合はpermission_blockerのerrorにする
- 権限が広すぎて未権限主体が成果物やflagを先に読める、実行ファイルや設定を書き換えられる、
  requiresを飛ばせる場合はpermission_shortcutのerrorにする
- 権限昇格では、攻撃前後の実効UIDまたはcapabilityと保護対象へのアクセス差を説明できること。
  root所有という記述だけ、chmod 777、無差別なchown、設計にないgroup所属を成立根拠にしない
- 任意のコマンド・コード・式を実行できる段階へ到達した主体は、その時点のUIDで利用可能な
  ファイル操作、資格情報、sudo、setuid、capability、インタープリタ、ローカルサービスをすべて
  利用できるものとして扱う。「対話シェルをまだ得ていない」など実行経路の名前の違いだけを、
  後続ステップの前提が必要である根拠にしない
- 各requiresは、前段完了前には存在せず完了後に初めて得られる権限・秘密・到達性・実効IDなどの
  能力差を生むこと。単なる操作方法や通信チャネルの変更で同じ操作が既に可能ならbroken_chainにする
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

配置する正解フラグ（未設定は配置しない）:
- User flag: {scenario.user_flag or "未設定"}
- System flag: {scenario.system_flag or "未設定"}

JSON以外は返さないでください。形式:
{{"files":[{{"path":"contents/build.sh","content":"#!/bin/bash\\nset -euo pipefail\\n...","mode":"0755"}}]}}

制約:
- Packerは生成ルートを /tmp/scenario にコピーし、rootで contents/build.sh を実行する
- contents/README.md、contents/scenario_manifest.json、contents/build.sh、
  contents/scripts/provision.sh を必ず生成する
- scenario_manifest.json は required_files、services、acceptance_tests、
  expected_vulnerabilities、health_checks、attack_steps、objectivesを配列として持ち、target_osを
  `{scenario.target_os}` とする
- CVEステップごとにexpected_vulnerabilitiesへcve_id、公式cve_titleと完全一致するofficial_title、
  公式メカニズムのdescription、references、installation_artifact、artifact_source、
  source_build_reasonを記載する。CVEと無関係な別の弱点を同じCVEとして記載しない
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
- User flag取得要件（正解値ではない）: {machine.needs_user_flag}, {machine.user_flag_details or "指定なし"}
- System flag取得要件（正解値ではない）: {machine.needs_system_flag}, {machine.system_flag_details or "指定なし"}
- CVE要件はmachine.cve_idsだけを正とし、flag取得要件内の文字列をCVE指定として扱わない
- 攻撃グラフのcve_title、cve_description、cwe_idsは公式情報から固定済みである。実装ではその
  メカニズムと前提条件を再現し、別の設定不備、模擬ハンドラ、同じ製品の別脆弱性へ置き換えない。
  再現できない場合はCVE名だけを付けた代替実装を作らない
- 設定された正解フラグは1文字も変更せず、指定された配置先へそのまま保存する

{HASH_CRACKING_CONSTRAINTS}

{INSTALLATION_PREFERENCE_CONSTRAINTS}

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
User flag正解値: {scenario.user_flag or "未設定"}
System flag正解値: {scenario.system_flag or "未設定"}
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
checks内にrequired_commandsがある場合は、表示用の説明へ写すだけでなく、適切な実行ユーザーと
実在パスへ具体化した同等のコマンドを生成物とmanifestへ追加し、失敗時に非ゼロ終了させてください。
failed_commandsまたはfailure_log_contextがある場合は、そのコマンドと前後のエラーを根本原因として
扱い、末尾の後処理メッセージだけを修正しないでください。

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
- 設定された正解フラグは1文字も変更せず、修復後も同じ値を維持する
- contents/scenario_manifest.jsonを変更する場合、そのcontentはMarkdownやコメントを含まない
  厳密なJSON objectとし、単独でPythonのjson.loadsに成功させる。command文字列内の
  バックスラッシュもJSON規則で必ずエスケープし、セミコロンやドル記号の直前に未定義の
  JSONエスケープを作らない
- Markdownと攻撃グラフに矛盾がある場合は攻撃グラフを正とする
- 攻撃グラフのCVE公式事実と異なる脆弱性へ変更しない。CVE名や説明だけを合わせた模擬実装も禁止する

{HASH_CRACKING_CONSTRAINTS}

{INSTALLATION_PREFERENCE_CONSTRAINTS}

{DEPLOYMENT_VERIFICATION_CONSTRAINTS}

{SYNTAX_VALIDATION_CONSTRAINTS}

{EXPLOITABILITY_VERIFICATION_CONSTRAINTS}

{WEB_EXPERIENCE_AND_PERMISSION_CONSTRAINTS}

{FLAG_PLACEMENT_CONSTRAINTS}
{_skill_section(skill_context)}
"""


def scenario_sync_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    current: GeneratedSource,
    review_feedback: dict | None = None,
) -> str:
    feedback_section = ""
    if review_feedback:
        feedback_section = (
            "\n直前のシナリオレビューで次の不整合が指摘されました。実装ファイルを変更したことにせず、"
            "攻撃グラフの意図を保ったまま指摘をシナリオ本文へ反映してください。\n```json\n"
            + json.dumps(review_feedback, ensure_ascii=False, indent=2)
            + "\n```\n"
        )
    return f"""あなたは教育用攻撃マシンの実装とシナリオを同期する設計担当です。
検証済み攻撃グラフを不変のセキュリティ要件、意味レビュー済みの修復後ファイルを実装事実として、
シナリオ本文のパス、サービス、実行主体、owner、group、mode、ACL、sudoers、capability、検証方法を
同期してください。変更が不要な箇所は維持してください。

マシン: {machine.name}
テーマ: {machine.theme}
難易度: {machine.difficulty}
対象OS: {scenario.target_os}

修復前のプレイヤー向け紹介文:
```text
{scenario.scenario_description}
```

修復前の攻撃グラフ:
```json
{scenario.attack_graph.model_dump_json(indent=2)}
```

修復前のシナリオ:
```markdown
{scenario.definition}
```

修復後の実装ファイル:
```json
{current.model_dump_json(indent=2)}
```
{feedback_section}

JSONのみを返してください:
{{"scenario_description":"改訂後のプレイヤー向け紹介文","definition":"改訂後のMarkdown",
"attack_graph":{{"objectives":[],"steps":[]}},
"summary":"同期した事実の要約"}}

制約:
- 実装に存在しない挙動を追加せず、実装と異なる古いパス、権限、資格情報、手順、検証を残さない
- 攻撃グラフのstep_id、kind、requires、achieves、CVE-ID、cve_title、cve_description、cwe_ids、
  installation_artifact、artifact_source、source_build_reason、脆弱性メカニズムは不変であり、実装に
  合わせて変更しない。実装がこれらと異なる場合は、設計を誤実装へ合わせずsummaryで不一致を明示する
- 攻撃グラフのrequiresとachievesを維持し、前提を飛ばせる状態を正当化しない
- User/System flagの配置要件は維持するが、正解フラグ値そのものをdefinitionやattack_graphへ記載しない
- scenario_id、scenario_version_id、タイトル、対象OSは変更対象にしない
- owner・group・mode等を変えた場合、本文の実装計画、攻略手順、肯定・否定テストをすべて同期する
- scenario_descriptionも実装と本文に合わせて更新する。ただし、具体的な侵入口、URLやパス、ポート、
  製品バージョン、認証情報、コマンド、権限昇格経路、フラグの場所や値、攻撃連鎖の順序を明かさず、
  特定の役割設定や定型的な構成を強制しない、プレイヤー向けの自然な日本語を維持する。最後は
  シナリオ固有の背景から自然につながる表現で、対象マシンの調査とフラグ獲得の両方を明確に指示する。
  語彙や表記の完全一致は要求せず、同じ定型句を繰り返さない

{DESIGN_CONSTRAINTS}
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
User flag正解値: {scenario.user_flag or "未設定"}
System flag正解値: {scenario.system_flag or "未設定"}
攻撃グラフ:
```json
{scenario.attack_graph.model_dump_json(indent=2)}
```

シナリオ設計書:
```markdown
{scenario.definition}
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
- 設定された正解フラグが指定先へ正確に配置され、別の値へ変更されていないことを確認する
- シナリオ本文に記載されたパス、サービス、実行主体、owner、group、mode、ACL、sudoers、capability、
  脆弱性と検証条件を実装と1項目ずつ照合し、不一致はimplementation_mismatchのerrorにする
- intended techniqueを使わず同じ成果物を得られる場合はunintended_shortcutのerrorにする
- 攻撃固有の効果を証明せず、通常入力、エラー、接続成功だけを確認するテストはunproven_exploitまたは
  acceptance_test_gapのerrorにする
- 実装された主脆弱性が攻撃グラフの種類と異なる場合はwrong_techniqueのerrorにする
- CVEステップではcve_title、cve_description、cwe_idsを公式事実として、実装コードと設定が同じ
  発火条件と影響を実現しているか確認する。同製品の別脆弱性、一般的な設定不備、模擬エンドポイント、
  READMEやmanifestだけのCVE表記はwrong_techniqueのerrorにする
- attack_graphとmanifestのinstallation_artifact、artifact_source、source_build_reasonを実装と照合する。
  ビルド済み成果物を選択済みなのにソースをコンパイルしている、またはパッケージ・公式バイナリを
  調査した根拠なしにsource_buildへ変更している場合はimplementation_mismatchのerrorにする
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

{INSTALLATION_PREFERENCE_CONSTRAINTS}

{SYNTAX_VALIDATION_CONSTRAINTS}

{REVIEW_RESPONSE_CONSTRAINTS}
{_skill_section(skill_context)}
"""
