# ai_server エンドポイント仕様

## 概要

ai_server の API は、1台の学習用マシンを作成する処理を `session_id` 単位で管理します。
基本的な呼び出し順は次のとおりです。

```text
POST /v1/sessions
  ↓
PUT /v1/sessions/{session_id}/machine-information
  ↓
GET /v1/sessions/{session_id}/scenarios/events
  ↓
POST /v1/sessions/{session_id}/machines
  ↓
GET /v1/sessions/{session_id} で状態確認
  ↓
GET /v1/sessions/{session_id}/download
```

| メソッド | パス | 役割 |
| --- | --- | --- |
| `POST` | `/v1/sessions` | 新しいマシン作成セッションを作る |
| `GET` | `/v1/sessions/{session_id}` | セッション、生成、ビルドの最新状態を取得する |
| `PUT` | `/v1/sessions/{session_id}/machine-information` | マシン名や難易度などの生成条件を保存する |
| `GET` | `/v1/sessions/{session_id}/scenarios/events` | シナリオを生成し、結果をSSEで受信する |
| `POST` | `/v1/sessions/{session_id}/machines` | VMコード生成とbuild_serverへのビルド依頼を開始する |
| `GET` | `/v1/sessions/{session_id}/download` | 完成したマシンイメージをダウンロードする |
| `GET` | `/v1/health/live` | ai_serverプロセスの生存を確認する |
| `GET` | `/v1/health/ready` | PostgreSQLを含めてリクエスト処理可能か確認する |

## 共通事項

### ユーザー識別ヘッダー

```http
X-Authenticated-User-ID: user-123
```

作成時に指定したユーザーIDがセッション所有者として保存されます。同じセッションを操作する
リクエストでは、同じ値を指定してください。異なる値を指定した場合は、セッションの存在を
外部へ開示しないため `404` を返します。

現在の開発用設定ではこのヘッダーは省略可能です。セッション作成時に省略すると所有者は
`local-user` になります。本番環境ではBFFが認証済みユーザーIDを必ず設定する想定です。

### 共通セッションレスポンス

セッション関連APIは、原則として次の形式を返します。

```json
{
  "session_id": "a8ae1bc0-1d92-423a-a328-eb57df3f2a51",
  "owner_user_id": "user-123",
  "status": "scenario_ready",
  "machine_information": {},
  "scenario": {},
  "source_path": null,
  "source_checksum": null,
  "build_id": null,
  "build_status": null,
  "build_progress": 0,
  "build_repair_attempts": 0,
  "machine_access": null,
  "artifact": null,
  "error_message": null,
  "created_at": "2026-08-27T11:26:46.058333Z",
  "updated_at": "2026-08-27T11:27:10.000000Z",
  "scenario_events_url": "http://localhost:8000/v1/sessions/.../scenarios/events",
  "download_url": null
}
```

`download_url` は、ビルドが完了して成果物が確定した場合だけ設定されます。新しく完了した
ビルドでは `machine_access` に `{"username":"ubuntu","password":"..."}` が設定され、
ai_serverのPostgreSQLへ保存されます。パスワードは秘密情報として扱ってください。

### セッション状態

| 状態 | 意味 |
| --- | --- |
| `created` | セッション作成直後。マシン情報は未登録 |
| `ready` | マシン基本情報が登録され、シナリオ生成が可能 |
| `generating_scenario` | AIがシナリオを生成中 |
| `scenario_ready` | シナリオ生成が完了 |
| `generating_code` | AIがVM構築コードを生成・検証中 |
| `build_queued` | build_serverがビルドを受理、または開始待ち |
| `building` | build_serverがビルドまたは成果物登録を実行中 |
| `completed` | ビルドと成果物登録が完了し、ダウンロード可能 |
| `failed` | シナリオ生成、コード生成、検証、ビルドのいずれかが失敗 |

## セッションを作成する

### `POST /v1/sessions`

新しいマシン作成処理の管理単位を作成します。リクエストボディはありません。

```sh
curl -X POST http://localhost:8000/v1/sessions \
  -H 'X-Authenticated-User-ID: user-123'
```

成功時は `201 Created` と、状態が `created` のセッションを返します。以降の操作では、
レスポンスの `session_id` を使用します。

## マシン基本情報を登録する

### `PUT /v1/sessions/{session_id}/machine-information`

AIがシナリオとVMコードを生成するための条件を保存します。同じエンドポイントを再度呼ぶと
内容を更新し、以前に生成したシナリオを破棄して状態を `ready` に戻します。ただし、すでに
build_serverへ依頼済みの場合は変更できません。

```json
{
  "name": "Nginx Engine",
  "visibility": "private",
  "theme": "Web security",
  "difficulty": "Easy",
  "operating_system": "Ubuntu 26.04",
  "needs_user_flag": true,
  "user_flag_details": "/home/student/user.txtをサービス調査後に取得する",
  "needs_system_flag": false,
  "system_flag_details": ""
}
```

| フィールド | 必須 | 制約・意味 |
| --- | --- | --- |
| `name` | 必須 | マシン名。1〜40文字 |
| `visibility` | 必須 | `private`、`public`、`非公開`、`公開` |
| `theme` | 必須 | 学習テーマ。1〜500文字 |
| `difficulty` | 必須 | `Very Easy`、`Easy`、`Medium`、`High` |
| `operating_system` | 任意 | 対象OS。省略時は `Ubuntu 26.04` |
| `needs_user_flag` | 任意 | ユーザーフラグを用意するか |
| `user_flag_details` | 条件付き | `needs_user_flag=true` の場合は空にできない。最大4000文字 |
| `needs_system_flag` | 任意 | システムフラグを用意するか |
| `system_flag_details` | 条件付き | `needs_system_flag=true` の場合は空にできない。最大4000文字 |

成功時は `200 OK` と、状態が `ready` のセッションを返します。

## シナリオをSSEで生成・受信する

### `GET /v1/sessions/{session_id}/scenarios/events`

登録済みのマシン情報を使ってシナリオ生成を開始し、`text/event-stream` で進行と結果を
送信します。GETである理由は、ブラウザの `EventSource` やSSEプロキシから扱いやすくする
ためです。生成条件は先に `machine-information` へ保存します。

最初に、可変長の攻撃ステップ、依存関係、user/system flagの到達目標を持つ `attack_graph` を
生成します。攻撃ステップはCVEに限定せず、Web脆弱性、設定不備、認証情報、ロジック不備などを
組み合わせられます。循環依存、存在しない前提ステップ、到達不能なflag目標はサーバ側で拒否します。

`kind=cve` のステップが含まれる場合だけ、公式MITREレコードを取得します。Ubuntuの場合はさらに
CanonicalのOSVデータを対象リリースで絞り込み、OS・脆弱バージョンの適合性を確認します。
対象OSへ脆弱版を固定導入できないCVEが含まれる案は破棄し、攻撃グラフ全体を生成し直します。
既定では2024年以降のCVEだけを候補にし、`CVE_MIN_YEAR` で下限年を変更できます。
攻撃グラフの生成・検証に失敗した場合は既定で最大5回まで別案を作ります
（`SCENARIO_GENERATION_ATTEMPTS` で変更できます）。

完成した `scenario` には、対象OS、人間向けMarkdown、構造化された `attack_graph` が含まれます。
VMコード生成と修復はMarkdownだけを再解釈せず、検証済み攻撃グラフも入力として使用します。

```sh
curl -N http://localhost:8000/v1/sessions/{session_id}/scenarios/events \
  -H 'X-Authenticated-User-ID: user-123'
```

配信されるイベントは次のとおりです。

| SSEイベント | 意味 | `data` の主な内容 |
| --- | --- | --- |
| `scenario.started` | シナリオ生成を開始した | `session_id` |
| `scenario.delta` | Markdown本文の一部分を生成した | `content` |
| `scenario.completed` | シナリオを保存し、生成が完了した | `scenario` |
| `scenario.error` | AI呼び出しや検証に失敗した | `detail` |

```text
event: scenario.delta
data: {"content":"# Nginx Engine シナリオ設計書\n..."}

event: scenario.completed
data: {"scenario":{"scenario_id":"scenario-...","scenario_version_id":"v1",...}}
```

生成済みのセッションへ再接続した場合は再生成せず、`scenario.completed` だけを返します。
ストリーム開始後の失敗はHTTPエラーではなく `scenario.error` として通知され、セッションの
状態は `failed` になります。

## VMコード生成とビルドを開始する

### `POST /v1/sessions/{session_id}/machines`

生成済みシナリオからVM構築コードを作り、PoC準拠の静的検証とZIP作成を行った後、
build_serverの `POST /v1/builds` へビルドを依頼します。時間のかかる処理はバックグラウンドで
進むため、このエンドポイントは完了を待ちません。

```json
{
  "scenario_id": "scenario-1634ec4df6e846759cf51a8044a1401d"
}
```

`scenario_id` は任意です。省略した場合はセッションに保存されたシナリオを使用します。
指定した場合は、別セッションのシナリオを誤ってビルドしないよう所属を検証します。

成功時は `202 Accepted` と、通常は状態が `generating_code` のセッションを返します。同じ
セッションですでにコード生成中またはビルド依頼済みの場合は、重複依頼せず現在状態を返します。

バックグラウンド処理の流れ:

1. シナリオから `contents/` 以下のVMソースを生成
2. 必須ファイル、manifest、Bash、XMLなどを静的検証
3. 検証失敗時は既存ファイルと検証レポートをAIへ渡し、問題ファイルだけを差分修正
4. `source.zip` を作成
5. build_serverへ認証ヘッダーとZIPを送信
6. `build_id` をセッションへ保存

コード生成後にbuild_serverへの接続だけが失敗したセッションは、同じエンドポイントで再試行できます。
保存済みの `source.zip` とチェックサムが有効な場合、AIによるコード生成は繰り返さず、そのZIPを
build_serverへ再送します。

一方、build_serverがPackerビルドを `failed` または `cancelled` で終了した場合は、
ai_serverのバックグラウンド監視が失敗を検知し、保存済みソースとビルドエラーをAIへ渡します。
AIは失敗に関係するファイルだけを差分修正し、再検証後に異なる冪等性キーで新しいビルドとして
自動依頼します。新しいビルドも継続監視するため、クライアントの状態ポーリングには依存しません。
既定では3回まで行い、`BUILD_REPAIR_MAX_ATTEMPTS` で上限を変更できます（`0` で無効）。
実行済み回数は `build_repair_attempts`、差分履歴は生成ソース内の `repair_report.json` で
確認できます。
上限到達後に同じ `POST /machines` を明示的に再実行した場合は、`build_repair_attempts` を
リセットして新たな上限まで自動修正します。`GET /sessions/{session_id}` による状態確認だけでは
再開しないため、ポーリングによって無限に修正されることはありません。

## セッションとビルド状態を取得する

### `GET /v1/sessions/{session_id}`

画面の再読み込み、進捗ポーリング、エラー表示に使う状態取得エンドポイントです。
セッションに `build_id` がある場合は、呼び出し時にbuild_serverへ最新状態を問い合わせ、
`build_status`、`build_progress`、成果物情報を更新してから返します。

```sh
curl http://localhost:8000/v1/sessions/{session_id} \
  -H 'X-Authenticated-User-ID: user-123'
```

build_serverの状態が `completed` になると、ai_serverは成果物一覧を取得し、qcow2を優先して
ダウンロード対象に選びます。その後、セッション状態が `completed` となり、`download_url`
が設定されます。build_serverが返したランダムなマシンパスワードも `machine_access` として
同じセッションへ保存されます。変更前に完了したビルドなど、パスワード情報がない場合は
`machine_access` は `null` のままです。

## 完成したマシンをダウンロードする

### `GET /v1/sessions/{session_id}/download`

build_serverの内部URLを利用者へ公開せず、選択済み成果物をai_server経由でストリーミング
します。build_serverのポートはホストへ公開しないため、利用者はこのエンドポイントを使用します。
レスポンスは `application/octet-stream` で、ファイル名は
`Content-Disposition` ヘッダーに設定されます。成果物メタデータにファイルサイズがある場合は
`Content-Length` も返すため、curlなどのクライアントが進捗率と残り時間を表示できます。

```sh
curl -L -o image.qcow2 \
  http://localhost:8000/v1/sessions/{session_id}/download \
  -H 'X-Authenticated-User-ID: user-123'
```

ダウンロード要求時にもbuild_serverの状態を同期します。まだ成果物が完成していない場合は
`409 Conflict` を返します。

## ヘルスチェック

### `GET /v1/health/live`

FastAPIプロセスが起動し、HTTPリクエストへ応答できるか確認します。PostgreSQLや
build_serverにはアクセスしません。

```json
{"status":"ok"}
```

### `GET /v1/health/ready`

PostgreSQLへ `SELECT 1` を実行し、セッションを扱える状態か確認します。コンテナの
readiness checkや内部ロードバランサーからの確認に使用します。build_serverやGeminiの
可用性までは確認しません。

## 主なエラー

| HTTP状態 | 発生例 |
| --- | --- |
| `404 Not Found` | セッションが存在しない、または別ユーザーのセッションを指定した |
| `409 Conflict` | 基本情報登録前にシナリオ生成を要求した、シナリオ完成前にマシン作成を要求した、ビルド完了前にダウンロードした |
| `422 Unprocessable Entity` | 基本情報の必須項目、文字数、選択肢、フラグ詳細の検証に失敗した |
| `502 Bad Gateway` | 状態取得時にbuild_serverとの通信または応答処理に失敗した |

コード生成やbuild_serverへの依頼は非同期です。そのため `POST /machines` が `202` を返した
後に失敗する場合があります。Packerビルド失敗時は設定回数まで自動差分修正され、上限到達後は
`GET /sessions/{session_id}` の `status=failed` と `error_message` で確認できます。

## OpenAPI

サーバー起動中は次のURLから自動生成された仕様も参照できます。

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
