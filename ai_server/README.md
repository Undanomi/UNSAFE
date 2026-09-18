# SLSG AI Server

FastAPI で実装した、シナリオ生成・VM ソース生成・build_server 連携サービスです。
セッション、シナリオ、バージョン、生成状態は専用の PostgreSQL に保存します。

## 処理フロー

```text
セッション作成
  -> マシン基本情報を保存
  -> シナリオを生成して SSE 配信
  -> 選択したシナリオでマシン作成を要求
  -> VM ソースを生成・静的検証・ZIP 化
  -> build_server に非同期ビルドを依頼
  -> ai_server が発行した一時的な署名付き URL から成果物をダウンロード
```

生成ソースは PoC と同じ契約を使います。

```text
{SOURCE_ROOT}/{session_id}/{scenario_version_id}/source/
├── contents/
│   ├── README.md
│   ├── scenario_manifest.json
│   ├── build.sh
│   ├── scripts/provision.sh
│   ├── app/                 # シナリオに応じて生成
│   └── config/              # シナリオに応じて生成
├── generation_manifest.json
├── validation_report.json
└── repair_report.json
```

build_server へは、この生成ルートを `source.zip` として送ります。生成コードを
ai_server ホスト上で実行することはありません。

Webサービスを含む生成物は、IPアドレスだけで`/`へアクセスしたときにシナリオ固有の
入口へ到達することを必須とします。Packer中の実検査とmanifestの双方にアプリ固有の肯定検査が
あること、Web実行ユーザーによるファイル読み取り・親ディレクトリ探索と所有者・modeを検査する
ことを静的検証します。ディレクトリリスティングは静的validationで一律禁止せず、攻撃グラフで
意図した攻略要素かどうかを生成・レビュー時に判断します。
シェルとCGIは実行可能modeを必須とし、通常のPHP-FPM用ソースは読み取り権限を検査します。

シナリオは、人間向けの `scenario_definition`（Markdown）と、ビルド・検証用の
`attack_graph`（JSON）を同じバージョンに保存します。攻撃グラフは可変長のステップ、
ステップ間の依存関係、user/system flagの到達目標を持ちます。CVEは攻撃ステップの任意の
種類の1つであり、Web脆弱性、設定不備、認証情報、ロジック不備なども組み合わせられます。
CVEを使うステップだけ、公式レコードと対象OSへの適合性を追加検証します。

## uv で起動

Python 3.13 と uv が必要です。最初に PostgreSQL を起動します。
`.env.example` をコピーした後、空欄の `AI_POSTGRES_PASSWORD` と
`BUILD_SERVER_TOKEN` にランダムな値を設定し、`DATABASE_URL` の
`<password>` も同じDBパスワードで置き換えてください。

```sh
cd ai_server
cp .env.example .env
docker compose up -d ai-postgres
uv sync --dev
AI_PROVIDER=stub uv run uvicorn ai_server.main:app --reload --port 8000
```

実際に Gemini を使う場合は `.env` の `AI_PROVIDER=gemini` と
`GEMINI_API_KEY` を設定します。スタブモードは API と build_server の結合確認用で、
安全な最小ソースを決定的に生成します。

VMコード生成はシナリオ生成より応答が大きくなるため、Gemini用HTTPクライアントには
`AI_TIMEOUT_SECONDS`（既定値600秒）を使用します。出力上限は
`GEMINI_MAX_OUTPUT_TOKENS`（既定値65536）で変更できます。build_serverとの内部通信には
別の `BUILD_TIMEOUT_SECONDS` を使用します。
攻撃グラフの生成失敗またはシナリオの敵対的AIレビュー不合格時の再試行回数は
`SCENARIO_GENERATION_ATTEMPTS`（既定値5）、
CVEステップを使う場合の公開年の下限は `CVE_MIN_YEAR`（既定値2024）で変更できます。
完成したシナリオは保存前に独立したAI呼び出しで意味レビューされます。攻撃グラフとの一貫性、
前提ステップを飛ばす近道、実装可能性、acceptance test計画に加え、実行主体、owner/group/mode、
親ディレクトリの探索権限、ACL・sudo・setuid・capability、flagの攻略前後の可読性を重点確認します。
不合格所見は次の生成試行へ渡され、レビューを通過したシナリオだけが保存されます。
生成ソースは構文・パーミッションなどの決定的validationに加え、攻撃グラフと実コードを比較する
敵対的AIレビューを通過する必要があります。意図した手法を使わない近道、通常機能による成果物の
先出し、単なるエラーや接続成功だけのexploit判定、前提ステップを飛ばせる攻撃経路は修復対象です。
この意味レビューの不合格と再修復はbuild_serverへ投入されないため、`build_repair_attempts`を増やしません。
Packerビルド失敗後の自動差分修正回数は `BUILD_REPAIR_MAX_ATTEMPTS`（既定値3）で変更でき、
`0` を指定すると自動修正を無効化できます。`build_repair_attempts`はbuild_serverへの投入に成功した
修復ビルドの累積実行回数で、静的validationの再試行とbuild_serverへの接続失敗では増えません。
各Build枠では `SOURCE_GENERATION_ATTEMPTS`（既定値3）までvalidationと差分修正を行います。
その回数を使い切っても次のBuild枠が残っていれば自動的に次枠へ進むため、最初のBuildを含む
1サイクルのvalidation上限は
`(1 + BUILD_REPAIR_MAX_ATTEMPTS) * SOURCE_GENERATION_ATTEMPTS`です。
失敗後に`POST /machines`を明示的に再実行すると、その時点の累積回数へ
`BUILD_REPAIR_MAX_ATTEMPTS`を加えた値を新しいサイクルの上限とし、さらに設定回数分を自動修復できます。
投入成功ごとに以前の回数へ1加算し、値を0や上限値へリセットしません。状態確認のGETだけでは
修復サイクルを追加しません。

## Docker で起動

既知の開発用シークレットへのフォールバックはありません。起動前に環境ファイルを作成し、
空欄の値をランダムな値で埋めてください。ルートComposeでは
`INTERNAL_API_TOKEN` と `BUILD_SERVER_TOKEN` に同じ値を設定します。
APIトークンは32文字以上が必須です。DBパスワードとAPIトークンには、
それぞれ `openssl rand -hex 32` などで生成した
別の値を使用してください。

ai_server と専用 PostgreSQL だけを起動する場合:

```sh
cp ai_server/.env.example ai_server/.env
docker compose --env-file ai_server/.env -f ai_server/compose.yml up --build
```

build_server を含む全サービスをリポジトリルートから起動する場合:

```sh
cp .env.example .env
docker compose up --build
```

本番では `.env` を配布せず、デプロイ基盤のSecret Managerから
`AI_POSTGRES_PASSWORD`、`BUILD_POSTGRES_PASSWORD`、`INTERNAL_API_TOKEN`、
`BUILD_SERVER_TOKEN` を注入してください。既存のPostgreSQLボリュームがある場合、
`POSTGRES_PASSWORD` の変更だけではDB内のパスワードは更新されません。先に対象ロールの
パスワードを変更してから接続側の環境変数を切り替える必要があります。

全サービス起動では build worker が `/dev/kvm` とベースイメージを必要とします。
詳細は `build_server/README.md` を参照してください。

Compose内のai_serverは既定で `http://server:8080` へ接続します。build_serverの8080番ポートは
ホストへ公開せず、利用者からの状態取得と成果物ダウンロードはai_serverが中継します。
Composeから別のbuild serverを使う場合は `AI_BUILD_SERVER_URL` で上書きします。ai_serverだけを
ホスト上でuv起動する場合は、build_serverへ到達できる内部URLを `BUILD_SERVER_URL` に指定します。

## API の利用例

署名付きURLからのダウンロードを除く操作では、同じ `X-Authenticated-User-ID` を指定します。
開発時に省略した場合は`local-user`として扱います。

```sh
SESSION_ID=$(curl -s -X POST http://localhost:8000/v1/sessions \
  -H 'X-Authenticated-User-ID: user-123' | jq -r .session_id)

curl -X PUT "http://localhost:8000/v1/sessions/$SESSION_ID/machine-information" \
  -H 'Content-Type: application/json' \
  -H 'X-Authenticated-User-ID: user-123' \
  -d '{
    "name":"Nginx Engine",
    "visibility":"private",
    "theme":"Web security",
    "difficulty":"Easy",
    "operating_system":"Debian 13.7.0",
    "needs_user_flag":true,
    "user_flag_details":"/home/student/user.txt",
    "needs_system_flag":false
  }'

curl -N "http://localhost:8000/v1/sessions/$SESSION_ID/scenarios/events" \
  -H 'X-Authenticated-User-ID: user-123'

curl -X POST "http://localhost:8000/v1/sessions/$SESSION_ID/machines" \
  -H 'Content-Type: application/json' \
  -H 'X-Authenticated-User-ID: user-123' \
  -d '{}'

curl "http://localhost:8000/v1/sessions/$SESSION_ID" \
  -H 'X-Authenticated-User-ID: user-123'
```

build_serverへの接続だけが失敗した場合は、同じ `POST /machines` を再実行できます。生成済みの
`source.zip` が残っていれば、AIコード生成を繰り返さずにビルド依頼から再開します。
Packerビルド自体が失敗またはキャンセルされた場合は、ai_serverがバックグラウンドで失敗を
検知し、ビルドエラーをAIへ渡して、失敗に関係するファイルだけを自動で差分修正します。
新しいビルドも継続して監視するため、クライアントからの状態ポーリングが止まっても次の修正へ
進みます。既定では3回まで行い、上限に達した場合は `failed` になります。修正履歴は
`repair_report.json` で確認できます。
上限到達後に同じ `POST /machines` を明示的に再実行すると、修正回数をリセットして新たな
3回分の自動修正を開始します。ビルドの開始と失敗後の再開を要求できるのは
`POST /machines` だけです。`GET /sessions/{session_id}` と `POST /download-url` は最新状態を
同期するだけで、修復ビルドを開始しません。すでに `POST /machines` から開始済みの
バックグラウンド監視と自動修復は、これらのエンドポイントへのアクセスに関係なく継続します。

状態が `completed` になるとレスポンスの `download_url` が設定されます。この URL は
HMAC署名され、既定では30分だけ有効です。build_server の内部 URL をブラウザへ露出せず、
`image.qcow2`、OS別起動スクリプト、READMEを含む`slsg-machine.tar.zst`をストリーミングします。
Rangeリクエスト、`ETag`（成果物のSHA256）、`If-Range`にも対応するため、中断後に同じ成果物の
ダウンロードを再開できます。期限切れの場合は、認証が必要な
`POST /v1/sessions/{session_id}/download-url` で新しいURLを取得してください。同時に、ランダム化
された `provisioner` ユーザーの認証情報を `machine_access` としてai_serverのセッションへ保存します。
ダウンロード応答には`application/zstd`と配信範囲に対応するサイズを設定します。

署名鍵は本番環境で必ずランダムな32文字以上の`DOWNLOAD_SIGNING_SECRET`へ変更してください。
有効期間は`DOWNLOAD_URL_TTL_SECONDS`で変更でき、既定値は1800秒です。署名付きURLは認証情報と
同様に扱い、ログや第三者へ共有しないでください。

OpenAPI UI は `http://localhost:8000/docs` で確認できます。

## SQLAdmin 管理画面

セッション、シナリオ、シナリオバージョンを確認・編集できる
SQLAdminを `/admin` に用意しています。通常は無効です。有効にする場合は `.env` に
次の値を設定してai_serverを再起動します。

```dotenv
SQLADMIN_ENABLED=true
SQLADMIN_USERNAME=admin
SQLADMIN_PASSWORD=<十分に長いランダムなパスワード>
SQLADMIN_SESSION_SECRET=<32文字以上のランダム値>
SQLADMIN_SECURE_COOKIES=false
```

起動後は `http://localhost:8000/admin` からログインできます。本番環境ではHTTPSを使用し、
`SQLADMIN_SECURE_COOKIES=true` にしてください。認証値が不足している場合やセッション秘密鍵が
32文字未満の場合、ai_serverは設定エラーで起動しません。管理画面から既存レコードを編集できますが、
主キーと作成日時の変更、およびレコードの作成・削除は無効化しています。ステータスや外部IDの
編集は実行中のワークフローへ影響するため、運用上必要な場合に限って変更してください。

各エンドポイントの役割、入出力、SSEイベント、状態遷移、エラー条件は
[`docs/endpoints.md`](docs/endpoints.md) にまとめています。

## テスト

```sh
cd ai_server
uv run ruff check .
uv run pytest
```
