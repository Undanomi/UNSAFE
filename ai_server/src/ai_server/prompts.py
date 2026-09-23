from __future__ import annotations

import json

from .models import (
    ROCKYOU_PASSWORD_PLACEHOLDER,
    AttackGraph,
    GeneratedSource,
    MachineInformation,
    ScenarioDraft,
)
from .scenario_manifest import scenario_manifest_json_schema

GUIDANCE_SOURCE_MAX_CHARS = 40_000

SCENARIO_MANIFEST_CONSTRAINTS = f"""scenario_manifest.jsonのJSON Schema:
```json
{scenario_manifest_json_schema()}
```
- 上記JSON Schemaを厳密に満たし、定義されていないプロパティを追加しない
- `objectives`は攻撃グラフに目標がない場合だけ空配列にする。それ以外の配列は空にしない
- `services`は外部またはローカルで待受するネットワークサービスだけを記載する。各要素の`name`は
  空でない文字列、`port`は1〜65535の整数、`protocol`は`http`、`https`、`tcp`、`udp`のいずれかにする
- `required_files`の各要素は`contents/`から始まる生成ファイルのパス文字列にする
- `acceptance_tests`と`health_checks`の各要素は、空でない`command`を持つobjectにする
- `expected_vulnerabilities`には実装した脆弱性を最低1件記載する。CVEでない脆弱性は空でない
  `name`と`description`を持つobjectにする。`"training-only"`のような文字列だけの要素は禁止する
- CVEの要素は上記の`name`形式ではなく、`cve_id`、`official_title`、`description`、`references`、
  `installation_artifact`、`artifact_source`、`source_build_reason`を持つobjectにする
- `attack_steps`と`objectives`は検証済み攻撃グラフから値を変更せず転記する
"""


def attack_graph_json_for_ai(
    graph: AttackGraph,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a design graph without revealing late-bound password material."""
    value = graph.model_dump(mode="json")
    for step in value["steps"]:
        spec = step.get("password_cracking")
        if spec is None:
            continue
        spec["password"] = None
        spec["line_number"] = None
        spec["search_space_lines"] = None
    return json.dumps(value, ensure_ascii=False, indent=indent)


def _redact_passwords(text: str, graph: AttackGraph) -> str:
    for step in graph.steps:
        spec = step.password_cracking
        if spec is not None and spec.password is not None:
            text = text.replace(spec.password, ROCKYOU_PASSWORD_PLACEHOLDER)
    return text


def source_json_for_ai(current: GeneratedSource, scenario: ScenarioDraft) -> str:
    """Redact a materialized password before review, repair, or synchronization."""
    value = current.model_dump(mode="json")
    for source_file in value["files"]:
        source_file["content"] = _redact_passwords(
            source_file["content"], scenario.attack_graph
        )
    return json.dumps(value, ensure_ascii=False, indent=2)


def _scenario_secrets(scenario: ScenarioDraft) -> tuple[str | None, ...]:
    passwords = tuple(
        spec.password
        for step in scenario.attack_graph.steps
        if (spec := step.password_cracking) is not None
    )
    return (scenario.user_flag, scenario.system_flag, *passwords)


def _guidance_source(current: GeneratedSource, secrets: tuple[str | None, ...]) -> str:
    priorities = (
        "scenario_manifest.json",
        "README",
        "provision",
        "verify",
        "build.sh",
        "sudoers",
        "systemd",
    )
    ordered = sorted(
        current.files,
        key=lambda item: (
            min(
                (index for index, marker in enumerate(priorities) if marker in item.path),
                default=len(priorities),
            ),
            item.path,
        ),
    )
    sections: list[str] = []
    used = 0
    for source_file in ordered:
        header = f"\n--- {source_file.path} ---\n"
        remaining = GUIDANCE_SOURCE_MAX_CHARS - used - len(header)
        if remaining <= 0:
            break
        content = source_file.content
        for secret in secrets:
            if secret:
                content = content.replace(secret, "[REDACTED FLAG]")
        content = content[:remaining]
        sections.append(header + content)
        used += len(header) + len(content)
    return "".join(sections)


def guidance_prompt(
    machine: MachineInformation,
    scenario: ScenarioDraft,
    current: GeneratedSource,
    acquired_flags: list[str],
) -> str:
    acquired = "、".join(acquired_flags) if acquired_flags else "なし"
    return f"""あなたはCTF学習者を支援するメンターです。以下の確定済みシナリオと、実際にVMへ
投入されたプロビジョニング用コードを照合し、攻略を段階的に進める日本語の誘導問題を作成してください。

マシン名: {machine.name}
難易度: {machine.difficulty}
取得済みフラグ: {acquired}

攻撃グラフ:
```json
{attack_graph_json_for_ai(scenario.attack_graph)}
```

シナリオ設計書:
```markdown
{_redact_passwords(scenario.definition, scenario.attack_graph)}
```

生成コード（関連度順、最大{GUIDANCE_SOURCE_MAX_CHARS}文字）:
```
{_guidance_source(current, _scenario_secrets(scenario))}
```

JSONだけを返してください。形式:
{{"introduction":"...","items":[{{"target_flag":"user","title":"...","question":"...","hint":"..."}}]}}

規則:
- シナリオの説明だけを要約せず、生成コードで実装を確認できる事実に基づく
- 攻撃グラフの順番に沿った1〜8個の項目にする。ただし取得済みフラグそのものを目標とする項目は省き、
  後続攻略に必要な既取得の足場として扱う
- 全フラグを取得済みならitemsを空配列にする
- 各項目のtarget_flagは、その調査過程の直後に到達するフラグを指定する。User flag取得までの列挙・
  初期侵入はuser、User flag取得後からSystem flag取得までの権限昇格はsystemにする
- User flagが存在しない場合は、System flag取得までの全項目をsystemにする
- questionは次に観察・調査すべきことを問いかけ、hintは行き詰まった時に試す方向性を1〜3文で示す
- introduction、title、question、hintではGitHub Flavored Markdownを使用できる。コマンド、パス、
  オプション、コードはバッククォートまたはコードブロックで表し、生のHTMLは使用しない
- 後続項目は画面上で順番に開示される。後続項目のtitleやquestionが、先行項目の直接的な答えに
  ならないようにし、具体性は段階的に上げる
- ツール名や一般的な調査コマンドは提示してよいが、完成したexploit payloadやフラグ取得コマンドを
  そのまま答えとして渡さない
- 正解フラグ値、秘密鍵、生成時だけの認証情報、プロビジョニング内部の絶対的な答えを開示しない
- 実装に存在しないポート、パス、脆弱性、認証情報を推測で追加しない
- introductionで、自動正誤判定ではなく各項目を確認しながら進める形式だと短く説明する
"""


HASH_CRACKING_CONSTRAINTS = """ハッシュクラックに関する共通制約:
- rockyou.txtはハッシュの一覧ではなく、攻撃者が自分のマシンで辞書攻撃に使う平文パスワード候補の
  wordlistである。ターゲットVMへインストールする教材コンポーネントや、ハッシュの保存先として
  扱わない
- 攻略経路にハッシュクラックを含める場合、AIは実際の平文パスワードを選択・推測しない。
  password、line_number、search_space_linesはnullのまま設計し、最初のソース生成が終わった後に
  サーバーがrockyou.txtから選択して構造化フィールドへ確定する
- rockyou.txtの実体、取得元、配置先、checksum、選択処理への受け渡し、候補が辞書に含まれること、
  line_number、search_space_lines、および選択時の速度測定はサーバー基盤の責務であり、この生成・レビュー
  工程では利用可能かつ検証済みとして扱う。これらをシナリオ本文、ターゲットVM、provision、manifest、
  acceptance testへ重複実装・記載させず、不足事項として指摘しない
- 該当ステップはkindを`password_cracking`にし、password_cracking objectへハッシュ方式、実装の
  hash_runtimeとhash_api、Hashcat modeまたはJohn format、120〜180秒のtarget_crack_secondsを
  構造化して記録する
- 攻略者がrockyou.txtだけを指定した辞書攻撃で発見できるようにし、追加辞書、ルール、
  マスク攻撃、総当たり、外部サービスを必須にしない
- サーバーが後から確定するline_numberとsearch_space_linesを探索量の根拠にできるよう、一般的な
  開発用PC上のHashcatまたはJohn the Ripperで約2〜3分となる現実的なハッシュ方式とwork factorを
  選ぶ。極端に高速または低速な方式を選ばない。この選択条件のハードウェア、実行環境、ベンチマークを
  シナリオ設計へ記載させたり、シナリオレビューで再検証させたりしない
- ソース内で平文が必要な箇所には必ずリテラル`__SLSG_ROCKYOU_PASSWORD__`だけを使用する。
  別の平文を推測・創作せず、この値を最終ダイジェスト、seed済みハッシュ、期待ハッシュとして扱わない
- SQLへ格納する値は、プロビジョニング時に`__SLSG_ROCKYOU_PASSWORD__`を入力として対象
  アプリのハッシュ生成APIを実行した結果にする。固定ダイジェストを設計書、README、manifest、SQL、
  アプリ設定、provision scriptへ例示・seed・期待値として埋め込まない
- 実際に格納するハッシュ値は、原則としてcontents/scripts/provision.shの実行中に、対象実装と
  同じランタイムおよび同じハッシュAPIから生成する。PHPアプリならそのPHP実装の`password_hash`等、
  PythonアプリならそのPython実装が検証に使うライブラリまたはヘルパーを実行し、別言語の近似実装、
  shell上の別アルゴリズム、AIが予測したダイジェストを埋め込まない
- DB等へ保存したハッシュは説明用の飾りにせず、攻略者が実際に利用する主認証入口で必ず消費する。
  決定的ハッシュなら送信された平文へ同じhash_apiを適用して保存値と比較し、`password_hash`系なら
  対応する`password_verify`等で検証する。送信された平文を保存ハッシュへ直接比較してはならない
- HTML formのmethod/action/field名から実際に到達するHTTP branch、認証関数、DB columnまで追跡し、
  その経路全体で同じ方式を使う。formがGETなのにGET branchは生値比較、未使用のPOST branchだけ
  ハッシュ化する、といった経路別の不一致を作らない。不要な別methodの認証経路は削除または拒否する
- クラックで得た平文を使わず、保存されたダイジェスト自体をpassword欄へ入力して通るpass-the-hashや、
  生パスワードとの直接比較で通る別経路を作らない。ハッシュクラック後の平文が後続ステップの認証で
  必須となるようにし、保存ハッシュが攻略経路と無関係な状態を完成扱いにしない
- saltを使う方式ではプロビジョニング時に正規APIへsalt生成も任せる。受け入れテストは固定ハッシュの
  文字列一致ではなく、対象アプリと同じ検証APIで選択済み平文が成功し、誤った平文が失敗すること、
  さらに実際の認証入口で選択済み平文だけが通ることを確認する
- 受け入れテストはDBやhash helperの直接呼出しだけで済ませず、実際のform/APIと同じmethod、path、
  field名で、選択済み平文は認証成功、誤った平文は失敗、保存ダイジェストをpasswordとして送った場合も
  失敗することを、それぞれ認証成功時だけ現れる応答またはセッション状態で確認する
- 実装する認証情報はサーバーが後から確定する値と一致させ、受け入れテストでも検証できるようにする
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
- 肯定確認と否定確認を、失敗時に非ゼロ終了する独立したコマンドとしてscenario_manifest.jsonの
  health_checksとacceptance_testsへ記載する。サーバーが全コマンドからscripts/verify.shを生成する
"""

SYNTAX_VALIDATION_CONSTRAINTS = """構文・設定ファイル検査の共通制約:
- 使用する言語、スクリプト、設定ファイルに公式または標準的な構文検査・設定検査コマンドがある場合、
  検査可能なものを省略せず、生成した全対象ファイルへ実行する。目視確認やファイル存在確認だけで
  構文が正しいと判断しない
- 検査は対象ランタイムやソフトウェアをインストールし、ファイルを最終配置した後に実行できる
  独立したコマンドとしてmanifestへ記載する。サーバー生成のscripts/verify.shが各コマンドを
  `bash -o pipefail -c`で実行し、失敗を無視せずビルドを非ゼロ終了させる
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
- manifestのhealth_checks/acceptance_testsで、Hostを
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
  `runuser -u www-data -- test -r /var/www/html/index.php`の両方を、scenario_manifest.jsonの
  health_checksまたはacceptance_testsへそれぞれ入れる
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
- ここでいう「意図しない近道」は、生成物が保護対象そのものを攻略前に直接開示する実装欠陥に限定する。
  例はflagや次工程の秘密を通常レスポンス、初期画面、公開ファイル、バナー、コメント、ログ、過剰な
  permission、テスト専用分岐からそのまま取得できる場合である
- 別の攻撃手法、オンライン認証試行、より短い攻略経路が理論上存在することだけを「近道」としない。
  意図した経路が成立して各成果物を後段で利用できるなら、経路の一意性や最短性を要求しない
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
- 実装または修復の完了前に、保護対象の直接的な情報漏えい、攻略前に読める権限、検証用backdoorが
  ないか攻撃者視点で反証し、見つかった場合は完成扱いにしない
"""

DESIGN_CONSTRAINTS = """設計段階の共通制約:
- 攻撃経路はテーマと難易度を満たす必要最小限のステップにし、各requiresの成果物を後段で実際に使う。
  benign control、exploit固有の成功、negative control、前提なしでは失敗することを検証計画に含める
- WebはIPアドレスの`/`から意図した入口へ到達でき、既定ページや意図しない一覧・近道を公開しない
- 各段階の実効ユーザー、重要ファイルと全親ディレクトリのowner/group/modeを定義し、
  攻略前の主体へ成果物を公開しない
- flagは指定パスだけへ配置し、攻略後の主体だけが読める権限と、攻略前後の可読性検証を計画する
- ハッシュクラック: rockyou.txtは平文wordlistで通常は攻撃者側で使う。kindは
  `password_cracking`とし、password、line_number、search_space_linesはソース生成後のサーバー選択
  までnullにする。方式・mode/format・120〜180秒を記録し、固定ハッシュは設計書へ書かず、
  provision時に対象アプリと同じAPIで生成する。rockyou.txtの実体、取得元、配置先、checksum、
  選択処理への受け渡しと速度測定はサーバー基盤で保証し、設計の不足事項として指摘しない
- 使用する言語とソフトウェアに応じ、標準的な構文・設定検査と実行時検査を計画する。ここでは
  検査対象と目的だけを簡潔に示し、完全なスクリプトや全コマンドはコード生成段階へ委ねる
"""

REVIEW_RESPONSE_CONSTRAINTS = """レビュー出力は簡潔にする。同じ根本原因の所見を統合し、findingsは
重大度の高い順に最大20件とする。summaryは3文以内、各evidenceとremediationは必要な根拠と修正を
短く示し、入力されたシナリオ、攻撃グラフ、生成ファイル、共通制約を転載しない。
"""


def _skill_section(skill_context: str) -> str:
    policy = (
        "脆弱性選択方針: Skills/referenceは補助であり許可リストではありません。要件に合う未登録手法や"
        "CVEも利用でき、資料内の登録限定より本方針を優先します。CVEの実在、影響版、条件、Debian適合性は"
        "公式情報による検証を行います。Web限定ならローカル脆弱性を加えず、権限昇格は先行成果へ接続します。"
        "シナリオ確定後は攻撃グラフを維持し、新しい経路やCVEを追加しません。"
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
      "references": [],
      "password_cracking": null
    }}
  ]
}}

規則:
- stepsは1〜30件で、step_idは英小文字から始まる英数字・ハイフン・アンダースコアだけを使う
- kindはreconnaissance、cve、web_vulnerability、misconfiguration、credential、
  password_cracking、logic_flaw、weak_cryptography、custom等を使う。rockyou.txtによる
  パスワードハッシュ辞書攻撃はpassword_crackingに限定する
- phaseの推奨値はreconnaissance、initial_access、post_exploitation、lateral_movement、
  privilege_escalation、objective
- requiresには前提となるstep_idを指定し、循環参照を作らない
- achievesには到達したobjective_idを指定し、すべての到達目標をいずれかのステップで達成する
- 非CVEステップではcve_id、cve_title、cve_description、installation_artifact、
  artifact_source、source_build_reasonをnull、cwe_idsを空配列にする。脆弱版ソフトウェアの導入情報は
  対応するkind=cveのステップへ記載し、reconnaissanceやセットアップ用ステップへ重複させない
- password_crackingは同名kindだけに設定する。wordlistはrockyou.txt、password、line_number、
  search_space_linesはnullとし、残りはhash_algorithm、hashcat_modeまたはjohn_format、hash_runtime、
  hash_api、target_crack_seconds（120〜180）とする。秘密値はソース生成後にサーバーが設定する
- 各ステップのdescriptionには攻撃者の操作と得られる成果物を記載し、implementation_stepsには
  その攻撃を可能にするVM側のプロビジョニング手順だけを記載する。Nmap、curl、SSH、exploit
  payload、flag読取りなど攻撃者が実行する操作をimplementation_stepsへ入れない
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
{_redact_passwords(previous_scenario.definition, previous_scenario.attack_graph)}
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
- `## 4. 攻撃グラフ`では、攻撃グラフの各stepを同じ順序でちょうど1回ずつ扱い、見出しまたは表に
  正確なstep_idとtitleをそのまま記載する。stepを別IDへ改名したり、複数stepへ分割・統合したり、
  設計書だけの追加stepを作らない。細かな調査操作は同じstep内の箇条書きとして扱う
- password_crackingのhash_algorithm、hash_runtime、hash_api、hashcat_mode、john_format、
  target_crack_secondsは攻撃グラフの値をそのまま使い、別方式へ読み替えない。password、line_number、
  search_space_linesが未確定なら、設計書でもサーバーによるソース生成後の確定として扱う
- installation_artifact、artifact_source、source_build_reasonはkind=cveの配布物追跡用フィールドであり、
  自作するシナリオ用PHP等を「source_build」と呼ばない。自作アプリはcontents/appへ生成する実装として
  記載し、非CVE stepへCVE専用フィールドを要求しない
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
{attack_graph_json_for_ai(attack_graph)}
```

レビュー指摘:
```json
{_redact_passwords(json.dumps(review_feedback, ensure_ascii=False, indent=2), attack_graph)}
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
{attack_graph_json_for_ai(attack_graph)}
```

現在のプレイヤー向け紹介文:
```text
{previous_scenario.scenario_description}
```

現在のシナリオ設計書:
```markdown
{_redact_passwords(previous_scenario.definition, previous_scenario.attack_graph)}
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
    source_sync_scope = ""
    if review_context == "source_sync":
        source_sync_scope = """
同期レビュー固有の責務:
- この工程は、ソース修正後のシナリオ本文を攻撃グラフと実装へ同期できたかだけを確認する。
  独立した2回目のソース監査ではない。新しい実装要件、追加テスト、別の修正方針を持ち込まない
- errorにできるのは、提示された本文と攻撃グラフまたは生成物の間に、引用可能な直接の矛盾が残る場合だけ。
  repair_targetはscenario_textに限定し、source_code、attack_graph、attack_graph_regeneration、user_inputを
  返さない。実装への懸念はソースレビューまたは実ビルドの責務であり、この工程から差し戻さない
- パッケージ、サービス、DB、権限等の実環境での挙動を実行せずに推測した懸念や、より網羅的な
  acceptance testの提案はビルド阻止理由にしない。同期で変更した箇所と、その直接の波及だけを見る
"""
    reconsideration_section = ""
    if reconsideration is not None:
        reconsideration_section = f"""
前回レビューの再検討資料:
```json
{_redact_passwords(json.dumps(reconsideration, ensure_ascii=False, indent=2), scenario.attack_graph)}
```
生成物の修正案がサーバー検証に失敗しました。修正案だけでなく、前回レビューの前提や修正先が
誤っていた可能性も検討してください。修正案だけが誤りなら指摘を維持し、検証可能な修正内容へ具体化
してください。検証エラーを回避する内容を捏造せず、指摘が誤りなら撤回し、
限定修正で扱えない構造問題ならattack_graph_regeneration、明示された入力条件同士が論理的に
両立不能な場合だけuser_inputへ変更して
シナリオ全体を改めて判定してください。ただし、スキーマで禁止されたフィールドを許可するために
attack_graph_regenerationへ逃がさず、その要求自体を撤回してください。同じ根拠のない修正要求を
繰り返さないでください。
"""
    return f"""あなたは教育用攻撃マシンのシナリオを審査する、独立した敵対的レビュー担当です。
作者の説明を信用せず、完成した設計書と攻撃グラフから、意図した攻撃経路が対象OS上で本当に成立し、
保護対象を直接漏らす実装計画がないかを反証してください。セキュア化ではなく、教材として意図した脆弱性だけを
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
{attack_graph_json_for_ai(scenario.attack_graph)}
```

シナリオ設計書:
```markdown
{_redact_passwords(scenario.definition, scenario.attack_graph)}
```
{source_sync_scope}
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
- 全攻撃ステップを順に追い、意図した経路の中で各requiresの成果物が後段に実際に渡され、各achievesへ
  到達できるかを確認する。記述された経路自体が前段の成果物を使用しない場合はbroken_chainにする。
  別手法やオンライン認証試行で到達し得るという理由だけではbroken_chainにもunintended_shortcutにも
  しない。unintended_shortcutはflag、秘密、次工程の成果物が通常表示、公開ファイル、過剰permission、
  検証用backdoor等から攻略前に直接取得できる場合に限定する
- 設計書と攻撃グラフの手法、実行主体、成果物、依存関係、flag到達条件が矛盾する場合は
  semantic_mismatchのerrorにする。検証済み攻撃グラフを正とし、設計書側の改名、step分割・統合、
  ハッシュ方式の読み替えが原因ならrepair_targetはscenario_textにする。本文へ合わせるために
  step_idやpassword_cracking等の不変フィールドを変更・再生成しない
- attack graphのdescriptionは攻撃者の操作、implementation_stepsはその攻撃を成立させるVM側の
  プロビジョニング手順である。implementation_stepsにユーザー作成、アプリ配置、権限設定、脆弱な
  状態の構築があることを理由に、攻撃者コマンドへ書き換える指摘をしない
- CVEステップのcve_title、cve_description、cwe_idsは公式事実。設計書が別の脆弱性、設定不備、
  模擬実装へ置き換えていればsemantic_mismatchのerrorにする
- kind=cveのstepだけについてinstallation_artifactとartifact_sourceが示すビルド済み配布経路を
  設計書が維持しているか確認する。自作PHP等の非CVE stepにはこれらのフィールドを要求しない。
  source_buildの場合はsource_build_reasonに、先行するパッケージ・公式バイナリ経路を利用できない
  具体的根拠がなければunsupported_assumptionのerrorにする
- 実装に必要なパス、サービス、ユーザー、権限遷移、検証方法が曖昧で、実装者が推測しなければ
  攻略成立性を保証できない場合はimplementation_gapまたはunsupported_assumptionのerrorにする
- acceptance test計画が、意図したexploitの成功、benign control、negative control、requiresを
  飛ばした失敗を全く観測できない場合はacceptance_test_gapのerrorにする。ただし、同じ性質の追加ケースや
  網羅性向上だけを要求せず、実ビルドで判定する環境依存の懸念はwarningにする
- warningは成立性を損なわない改善提案だけに使い、成立可否が不明な点をwarningへ弱めない
- errorが1件でもあればapproved=false、errorがなければapproved=trueにする
- evidenceには設計書または攻撃グラフの具体的な記述と、どの主体のどの操作が成功または失敗するかを
  記載する。単なる一般論や推測だけで不合格にしない
- repair_target: scenario_text=本文、attack_graph=限定修正、attack_graph_regeneration=再作成、
  source_code=実装(source_sync時のみ)、user_input=相互矛盾した明示入力だけ
- attack_graphの限定修正はtitle、description、implementation_stepsのみで、repair_fieldsへ列挙する。
  それ以外のフィールドが本文と違うだけならscenario_textを修正する
- attack_graph_regenerationは、設計書との表現差ではなく、攻撃グラフ単体のrequires/achievesが
  破綻しているbroken_chain、またはグラフ単体の前提が成立不能なunsupported_assumptionに限定する。
  必ず該当する既存step_idと構造フィールドをrepair_fieldsへ入れる
- user_inputは、ユーザーが明示した2つ以上の条件が論理的に同時成立しない場合だけ使用する。categoryは
  input_contradiction、step_idはnull、repair_fieldsには矛盾する入力フィールド名を入れる。例えば
  system_flag_detailsで「vimをsudoersへ入れない」と「sudo vimで取得する」を同時に要求する場合である。
  攻撃グラフ、設計書、生成コードの欠陥、AIの選択、難易度への合わせ方、実装方式、password_crackingの
  構造化値は生成側の責務であり、user_inputへ転嫁しない。難易度を上げる・要件を緩和するという提案を
  user_inputとして返さず、指定難易度の範囲で生成物を修正または再生成する

権限レビューでは、時系列の権限表として攻撃前後の実効UID、重要パスと全親ディレクトリ、
owner/group/mode、sudoers、capabilityを追う。同じ状態に相反する記述がある、意図した主体が読めず
permission_blockerになる、未権限主体が先に読めてpermission_shortcutになる場合だけerrorにする。
レビュー時点では実ファイルが未生成なので、一般的なアプリファイルやDB接続設定の全permissionを
網羅していないことだけでerrorにせず、コード生成で安全に具体化できない攻撃連鎖上の曖昧さを示す。
任意のコマンド・コード・式を実行可能な主体の能力を過小評価せず、操作方法や通信チャネルの変更だけを
requiresの根拠にしない。flagは攻略後の主体だけが読めることを確認する。

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

{_redact_passwords(scenario.definition, scenario.attack_graph)}

検証済みの攻撃グラフ:
{attack_graph_json_for_ai(scenario.attack_graph)}

配置する正解フラグ（未設定は配置しない）:
- User flag: {scenario.user_flag or "未設定"}
- System flag: {scenario.system_flag or "未設定"}

JSON以外は返さないでください。形式:
{{"files":[{{"path":"contents/build.sh","content":"#!/bin/bash\\nset -euo pipefail\\n...","mode":"0755"}}]}}

制約:
- Packerは生成ルートを /tmp/scenario にコピーし、rootでcontents/build.sh、続いて
  サーバーがmanifestから生成したcontents/scripts/verify.shを必ず実行する
- contents/README.md、contents/scenario_manifest.json、contents/build.sh、
  contents/scripts/provision.shを必ず生成する。contents/scripts/verify.shはfilesへ返さず、
  scenario_manifest.jsonのrequired_filesには記載する
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
- manifestのhealth_checksとacceptance_testsの各commandは他のentryの変数や状態へ依存させず、
  プロビジョニング完了後の実環境に対して単独で実行可能にする
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

{SCENARIO_MANIFEST_CONSTRAINTS}

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
    current_json = source_json_for_ai(current, scenario)
    report_json = _redact_passwords(
        json.dumps(failure_report, ensure_ascii=False, indent=2), scenario.attack_graph
    )
    return f"""あなたは生成済みの教育用VMソースを差分修正するエージェントです。
新規生成はせず、検査またはPackerビルドで失敗した箇所だけを修正してください。

マシン: {machine.name}
シナリオID: {scenario.scenario_id}
対象OS: {scenario.target_os}
User flag正解値: {scenario.user_flag or "未設定"}
System flag正解値: {scenario.system_flag or "未設定"}
攻撃グラフ:
```json
{attack_graph_json_for_ai(scenario.attack_graph)}
```

失敗内容:
```json
{report_json}
```

失敗内容にrepair_historyが含まれる場合、そこに記録された過去の失敗と変更をすべて考慮してください。
known_failed_resourcesに列挙された要素は、現在の失敗内容に現れなくても再利用してはいけません。
original_triggerとrejected_patchが含まれる場合、元の修正目的を維持しつつ、拒否された同じパッチを
繰り返さないでください。元レビューのremediationと決定的検証が衝突する場合は検証制約を破らず、
別の有効な修正方法を選んでください。レビュー自体の再判定は呼び出し側が行います。
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
- contents/scripts/verify.shはサーバー生成物なので直接修正・削除せず、検査の変更は
  contents/scenario_manifest.jsonのhealth_checksまたはacceptance_testsへ行う
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

{SCENARIO_MANIFEST_CONSTRAINTS}

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
            "\n直前のレビューで次のシナリオ本文の不整合が指摘されました。実装ファイルを変更したことにせず、"
            "攻撃グラフの意図を保ったまま指摘をシナリオ本文へ反映してください。\n```json\n"
            + _redact_passwords(
                json.dumps(review_feedback, ensure_ascii=False, indent=2),
                scenario.attack_graph,
            )
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
{attack_graph_json_for_ai(scenario.attack_graph)}
```

修復前のシナリオ:
```markdown
{_redact_passwords(scenario.definition, scenario.attack_graph)}
```

修復後の実装ファイル:
```json
{source_json_for_ai(current, scenario)}
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
    reconsideration: dict | None = None,
) -> str:
    reconsideration_section = ""
    if reconsideration is not None:
        if reconsideration.get("kind") == "source_repair_verification":
            reconsideration_section = f"""
修正後レビューの固定スコープ:
```json
{_redact_passwords(json.dumps(reconsideration, ensure_ascii=False, indent=2), scenario.attack_graph)}
```
これは新しいフル監査ではない。blocking_reviewに列挙された各errorが解消したかを確認し、加えて
changed_filesの変更が直接引き起こした回帰だけを探す。以前のerrorを再掲する場合は同じstep_id、category、
repair_targetを使う。新しいerrorはaffected_filesにchanged_filesとの共通パスを必ず含め、変更との因果を
evidenceで説明する。変更されていない箇所の新規指摘、追加の改善案、前回見落としただけの指摘はwarningに
留める。修正候補が不合格でも、その候補へさらに修正を積み重ねず、呼び出し側が修正前ソースへ戻して
置換パッチを作り直す。repair_originがbuild_failureの場合、元の候補は既に意味レビュー済みであり、
ビルド失敗そのものの解消は次の実ビルドが判定する。このレビューでは変更箇所からの回帰だけを判定する。
"""
        elif reconsideration.get("kind") == "source_full_reaudit":
            reconsideration_section = f"""
修正によるレビュー契約の変更:
```json
{_redact_passwords(json.dumps(reconsideration, ensure_ascii=False, indent=2), scenario.attack_graph)}
```
manifestが表す攻撃ステップ・サービス・脆弱性・目的の契約、実装ファイル構成、または初回レビューが
宣言した修正範囲が変わったため、固定スコープを破棄して現在の候補を最初からフル監査する。以前の指摘
だけに限定せず、ビルドを止めるfindingを今回の応答へ一度に全件列挙する。ただし、レビュー契約が変化
したという事実だけをerrorにせず、現在の生成物に残る具体的な不整合を根拠に判定する。
"""
        else:
            reconsideration_section = f"""
前回レビューの再検討資料:
```json
{_redact_passwords(json.dumps(reconsideration, ensure_ascii=False, indent=2), scenario.attack_graph)}
```
前回レビューに従った修正が決定的検証に失敗したか、修正後レビューで同じ指摘が残る・指摘が増える
など意味的な改善が確認できませんでした。修正案だけでなく、前回レビューの前提、repair_target、
remediationが生成物のスキーマや不変条件と衝突していないかも検討してください。修正案だけが誤りなら
指摘を維持し、正しいrepair_targetと検証可能な修正内容へ具体化してください。検証エラーを回避する
事実を捏造せず、元の指摘が誤りなら撤回してください。同じ失敗を起こす修正要求をそのまま繰り返さず、
再検討資料に含まれる現在のソースを対象としてレビュー全体を改めて判定してください。
"""
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
{attack_graph_json_for_ai(scenario.attack_graph)}
```

シナリオ設計書:
```markdown
{_redact_passwords(scenario.definition, scenario.attack_graph)}
```

生成ファイル:
```json
{source_json_for_ai(current, scenario)}
```
{reconsideration_section}

JSONのみを返してください:
{{"approved":false,"summary":"...","findings":[{{"step_id":"...","severity":"error",
"repair_target":"source_code","category":"unintended_shortcut",
"affected_files":["contents/app/index.php"],
"evidence":"ファイルと具体的挙動","remediation":"必要な修正"}}]}}

審査規則:
- 全攻撃ステップを順に追い、実装コード、provision、manifest、acceptance_testsの整合性を確認する
- 固定スコープが提示されていない最初のレビューでは、ビルドを止めるfindingを一度に全件列挙する。
  修正を1件ずつ小出しにしたり、次回レビューのために既知の指摘を保留したりしない
- このレビューはビルド前ゲートである。errorは、提示されたファイルから直接証明でき、修正しなければ
  意図した経路が成立しない、別手法になる、または保護対象が直接漏れる致命的不整合だけに限定する。
  パッケージ、デーモン、DB、権限、ネットワーク等の実環境での挙動を実行しないと確定できない懸念は
  warningとし、Packerビルドとacceptance testへ委ねる。「失敗する可能性がある」だけでerrorにしない
- 既存テストが中核の攻撃成功と必要な前提を検査しているなら、追加の境界値、重複するnegative control、
  実装詳細の再証明を要求しない。改善用の追加テストはwarningとし、テストが皆無・実行不能・常に成功・
  攻撃を迂回していることをファイルから直接証明できる場合だけacceptance_test_gapのerrorにする
- サーバー制約に「サーバーが選択・検証・生成する」と明記された値やファイルは信頼境界の外側で保証済み
  として扱い、生成ソースに同じ検証や生成を重複実装させない。モデルへ渡されていない外部データの内容を
  推測して、その確認テストを要求しない。特にrockyou.txtからの選択範囲・所属・行番号・探索時間は基盤側、
  contents/scripts/verify.shはmanifestからのサーバー生成であり、filesに無いことを欠陥にしない
- 再検討資料がある場合は、前回指摘と変更ファイルの直接の回帰を優先する。無関係な箇所を新規に精査して
  細粒度のブロッカーを後出しせず、新しいerrorは明白な致命的不整合を変更箇所から直接証明できる場合に限る
- 設定された正解フラグが指定先へ正確に配置され、別の値へ変更されていないことを確認する
- シナリオ本文に記載されたパス、サービス、実行主体、owner、group、mode、ACL、sudoers、capability、
  脆弱性と検証条件を実装と1項目ずつ照合し、不一致はimplementation_mismatchのerrorにする
- flag、秘密、次工程の成果物が通常レスポンス、公開ファイル、過剰permission、検証用backdoor等から
  攻略前に直接取得できる場合だけunintended_shortcutのerrorにする。別の攻撃手法、オンライン認証試行、
  より短い攻略経路が存在することだけではerrorにせず、意図した経路の一意性や最短性を要求しない
- 中核の攻撃について、攻撃固有の効果を全く証明せず、通常入力、エラー、接続成功だけを確認するテストは
  unproven_exploitまたはacceptance_test_gapのerrorにする
- 実装された主脆弱性が攻撃グラフの種類と異なる場合はwrong_techniqueのerrorにする
- CVEステップではcve_title、cve_description、cwe_idsを公式事実として、実装コードと設定が同じ
  発火条件と影響を実現しているか確認する。同製品の別脆弱性、一般的な設定不備、模擬エンドポイント、
  READMEやmanifestだけのCVE表記はwrong_techniqueのerrorにする
- attack_graphとmanifestのinstallation_artifact、artifact_source、source_build_reasonを実装と照合する。
  ビルド済み成果物を選択済みなのにソースをコンパイルしている、またはパッケージ・公式バイナリを
  調査した根拠なしにsource_buildへ変更している場合はimplementation_mismatchのerrorにする
- 記述された意図的経路の実装が前段の成果物を後段で実際に使わない場合はbroken_chainにする。
  独立した別手法でも到達可能という理由だけでbroken_chainにしない
- password_cracking stepでは、provisionが生成してDB等へ保存する値から、ユーザーが操作するform/APIの
  method・action・field、到達するhandler branch、hash/verify API、比較対象column、認証成功後の成果物まで
  データフローを追跡する。実際の入口が生パスワードを保存値へ直接比較する、保存ハッシュ自体で通る、
  または正しいハッシュ処理が未使用の別branchにしかない場合はimplementation_mismatchかbroken_chainの
  errorにする。別ファイルや別methodにhash_apiの呼出しが存在するだけでは合格にしない
- コメントや名前にSQLi等と書いてあること、expected_vulnerabilitiesの宣言、READMEの攻略説明だけを
  実装証拠として認めない。実際のデータフローと外部からの観測結果を根拠にする
- errorが1件でもあればapproved=false、errorがなければapproved=trueにする
- evidenceには判断に使ったファイルパス、変数、通常経路と攻撃経路の差を具体的に記載する
- affected_filesにはfindingの根拠となる生成ファイルだけを列挙する。一般論だけのfindingや、実際には
  変更されていないファイルを回帰の根拠にするため列挙したfindingをerrorにしない
- 各findingのrepair_targetを必ず指定する。実装ファイル、provision、manifest、acceptance_testsの
  修正はsource_code、実装が正しく本文だけが古い場合はscenario_textにする。このレビュー工程では
  検証済み攻撃グラフを不変の入力として扱い、attack_graphやuser_inputをrepair_targetに返さない
- 実装を攻撃グラフへ合わせられる不一致を別の生成物へ転嫁しない。特にinstallation_method、
  installation_artifact、artifact_source、source_build_reasonの値を取り違えず、存在しないフィールドの
  追加を要求しない。攻撃グラフの不変条件と衝突する修正要求をsource_code向けに出さない
- 必須の構文・設定検査が全く無い、または検査失敗を意図的に無視することが直接確認できる場合は
  acceptance_test_gapのerrorにする。一部ファイルの追加検査や別ツールによる重複検査はwarningに留める
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
