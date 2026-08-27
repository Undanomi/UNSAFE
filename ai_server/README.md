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
  -> ai_server の固定 URL から成果物をダウンロード
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

## uv で起動

Python 3.13 と uv が必要です。最初に PostgreSQL を起動します。

```sh
docker compose -f ai_server/compose.yml up -d ai-postgres
cd ai_server
cp .env.example .env
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

## Docker で起動

ai_server と専用 PostgreSQL だけを起動する場合:

```sh
docker compose -f ai_server/compose.yml up --build
```

build_server を含む全サービスをリポジトリルートから起動する場合:

```sh
docker compose up --build
```

全サービス起動では build worker が `/dev/kvm` とベースイメージを必要とします。
詳細は `build_server/README.md` を参照してください。

Compose内のai_serverは既定で `http://server:8080` へ接続します。ホスト上でuv起動するための
`BUILD_SERVER_URL=http://localhost:8080` がシェルや `.env` に設定されていても、Composeには
引き継ぎません。Composeから別のbuild serverを使う場合は `AI_BUILD_SERVER_URL` で上書きします。

## API の利用例

すべての操作で同じ `X-Authenticated-User-ID` を指定します。開発時に省略した場合は
`local-user` として扱います。

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
    "operating_system":"Ubuntu 26.04",
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
Packerビルド自体が失敗またはキャンセルされた場合は、同じ操作でビルドエラーをAIへ渡し、
失敗に関係するファイルだけを差分修正して新しいビルドを作成します。修正履歴は
`repair_report.json` で確認できます。

状態が `completed` になるとレスポンスの `download_url` が設定されます。この URL は
build_server の内部 URL をブラウザへ露出せず、成果物をストリーミングします。

OpenAPI UI は `http://localhost:8000/docs` で確認できます。

各エンドポイントの役割、入出力、SSEイベント、状態遷移、エラー条件は
[`docs/endpoints.md`](docs/endpoints.md) にまとめています。

## テスト

```sh
cd ai_server
uv run ruff check .
uv run pytest
```
