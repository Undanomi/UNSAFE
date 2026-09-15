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
POST /v1/sessions/{session_id}/download-url（必要に応じて再発行）
  ↓
GET /v1/sessions/{session_id}/download?expires=...&signature=...
```

| メソッド | パス | 役割 |
| --- | --- | --- |
| `POST` | `/v1/sessions` | 新しいマシン作成セッションを作る |
| `GET` | `/v1/sessions/{session_id}` | セッション、生成、ビルドの最新状態を取得する |
| `PUT` | `/v1/sessions/{session_id}/machine-information` | マシン名や難易度などの生成条件を保存する |
| `GET` | `/v1/sessions/{session_id}/scenarios/events` | シナリオを生成し、結果をSSEで受信する |
| `POST` | `/v1/sessions/{session_id}/machines` | VMコード生成とbuild_serverへのビルド依頼を開始する |
| `POST` | `/v1/sessions/{session_id}/download-url` | 一時的な署名付きダウンロードURLを発行する |
| `GET` | `/v1/sessions/{session_id}/download?expires=...&signature=...` | 完成したマシンイメージをダウンロードする |
| `GET` | `/v1/health/live` | ai_serverプロセスの生存を確認する |
| `GET` | `/v1/health/ready` | PostgreSQLを含めてリクエスト処理可能か確認する |

## 共通事項

### ユーザー識別ヘッダー

```http
X-Authenticated-User-ID: user-123
```

作成時に指定したユーザーIDがセッション所有者として保存されます。同じセッションを操作する
リクエストでは、同じ値を指定してください。異なる値を指定した場合は、セッションの存在を
外部へ開示しないため `404` を返します。例外として、発行済みの署名付きURLからファイル本体を
取得するGETにはこのヘッダーは不要です。

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

`download_url` は、ビルドが完了して成果物が確定した場合だけ設定されます。値はAIサーバを
指す一時的な署名付きURLで、既定では発行から30分間有効です。新しく完了した
ビルドでは `machine_access` に `{"username":"provisioner","password":"..."}` が設定され、
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
  "operating_system": "Debian 13.7.0",
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
| `operating_system` | 任意 | 対象OS。省略時は `Debian 13.7.0` |
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

`kind=cve` のステップが含まれる場合だけ、公式MITREレコードを取得します。Debianの場合はさらに
DebianのOSVデータを対象リリースで絞り込み、OS・脆弱バージョンの適合性を確認します。
対象OSへ脆弱版を固定導入できないCVEが含まれる案は破棄し、攻撃グラフ全体を生成し直します。
既定では2024年以降のCVEだけを候補にし、`CVE_MIN_YEAR` で下限年を変更できます。
攻撃グラフの生成・検証に失敗した場合は既定で最大5回まで別案を作ります
（`SCENARIO_GENERATION_ATTEMPTS` で変更できます）。

Markdownを含む完成シナリオは、保存前に別のステートレスなAI呼び出しで敵対的・意味的レビューを
行います。攻撃グラフとの整合、攻略経路の成立性、前提を飛ばす近道、検証計画を確認し、特に各段階の
実効ユーザー、owner/group/mode、親ディレクトリの探索権限、ACL、sudoers、setuid/capability、
flagの攻略前後の可読性を重点的に反証します。成立を妨げる権限は`permission_blocker`、広すぎる
権限による近道は`permission_shortcut`として不合格にします。不合格所見のsummary、evidence、
remediationは次の設計書生成へ直接渡され、通常は同じ攻撃グラフを維持したまま設計書を修正します。
`broken_chain`の場合だけ攻撃グラフも再生成します。`SCENARIO_GENERATION_ATTEMPTS`の範囲で再試行し、
レビューを通過したシナリオだけが保存されます。

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
2. 必須ファイル、manifest、Bash、XML、実行ファイルmodeなどを静的検証
   - WebサービスではIP直アクセスの`/`とアプリ固有マーカーの検査を必須化
   - ディレクトリリスティングは一律禁止せず、攻撃グラフで意図した場合だけ限定的に構成するよう指示
   - Web実行ユーザーでの読み取り・探索権限と、`namei`/`stat`による配置mode検査を必須化
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
build_serverへ依頼する前に、決定的validationと敵対的AIレビューの両方を実行します。AIレビューは
攻撃グラフの手法と実コードの一致、通常操作で成果物が漏れないこと、exploit固有の効果、negative
control、requiresで指定された前提を飛ばせないことを確認します。不合格所見は構造化された
`source_semantic_review`として同じ差分修正ループへ渡されます。
既定では3回まで行い、`BUILD_REPAIR_MAX_ATTEMPTS` で上限を変更できます（`0` で無効）。
`build_repair_attempts`はbuild_serverへの投入に成功した修復ビルドの累積実行回数です。差分履歴は
生成ソース内の`repair_report.json`で確認できます。生成ソースのvalidation失敗とその差分修正、
build_serverへの接続失敗では`build_repair_attempts`は増えません。
各Build枠では`SOURCE_GENERATION_ATTEMPTS`（既定値3）までvalidationと差分修正を試します。
validationを使い切っても次のBuild枠が残っていれば停止せず次枠へ進みます。したがって初回Buildと
修復Buildを合わせた1サイクルのvalidation上限は
`(1 + BUILD_REPAIR_MAX_ATTEMPTS) * SOURCE_GENERATION_ATTEMPTS`です。
失敗状態のセッションへ同じ`POST /machines`を明示的に再実行した場合は、その時点の累積回数へ
`BUILD_REPAIR_MAX_ATTEMPTS`を加えた値を新しいサイクルの上限として保存し、さらに設定回数分を
自動修復できます。投入に成功するたび以前の`build_repair_attempts`へ1加算するため、明示的な
再リクエストを繰り返すと`BUILD_REPAIR_MAX_ATTEMPTS`を超えます。ai_server再起動などで
保存状態が古い場合は、build_serverの最新状態を同期してから判定します。
ビルドの開始と失敗・キャンセル後の再開を要求できるのは`POST /machines`だけです。
`GET /sessions/{session_id}`と`POST /download-url`はカウンターをリセットせず、修復ビルドも
開始しません。すでに`POST /machines`から開始済みのバックグラウンド監視と自動修復は、これらの
エンドポイントへのアクセスに関係なく継続します。

## セッションとビルド状態を取得する

### `GET /v1/sessions/{session_id}`

画面の再読み込み、進捗ポーリング、エラー表示に使う状態取得エンドポイントです。
セッションに `build_id` がある場合は、呼び出し時にbuild_serverへ最新状態を問い合わせ、
`build_status`、`build_progress`、成果物情報を更新してから返します。この同期から失敗ビルドの
修復を開始することはありません。再開するには`POST /machines`を使用します。

```sh
curl http://localhost:8000/v1/sessions/{session_id} \
  -H 'X-Authenticated-User-ID: user-123'
```

build_serverの状態が `completed` になると、ai_serverは成果物一覧から`tar.zst`形式の配布物を
ダウンロード対象に選びます。`tar.zst`がなければ旧形式へフォールバックせずエラーになります。
選択後、セッション状態が `completed` となり、一時的な署名付き`download_url`
が設定されます。build_serverが返したランダムなマシンパスワードも `machine_access` として
同じセッションへ保存されます。変更前に完了したビルドなど、パスワード情報がない場合は
`machine_access` は `null` のままです。

## 完成したマシンをダウンロードする

### `POST /v1/sessions/{session_id}/download-url`

ログイン状態を確認できる通常のAPI経路から、完成済み成果物用の新しい署名付きURLを発行します。
所有者以外には`404 Not Found`、未完成の場合は`409 Conflict`を返します。未完成状態の確認時に
ビルドや修復を開始することはありません。

```sh
curl -X POST http://localhost:8000/v1/sessions/{session_id}/download-url \
  -H 'X-Authenticated-User-ID: user-123'
```

```json
{
  "download_url": "http://localhost:8000/v1/sessions/.../download?expires=...&signature=...",
  "expires_at": "2026-08-27T12:00:00Z"
}
```

有効期間は既定で30分であり、`DOWNLOAD_URL_TTL_SECONDS`で60秒〜24時間の範囲に変更できます。
本番環境では32文字以上のランダムな`DOWNLOAD_SIGNING_SECRET`を設定してください。

### `GET /v1/sessions/{session_id}/download?expires=...&signature=...`

build_serverの内部URLを利用者へ公開せず、選択済み成果物をai_server経由でストリーミング
します。このリクエスト自体にはユーザー識別ヘッダーは不要ですが、有効な署名と失効時刻が必須です。
署名はsession ID、build ID、artifact ID、失効時刻に結び付いており、改変または期限切れの場合は
`403 Forbidden`を返します。build_serverのポートはホストへ公開しないため、利用者はこの
AIサーバのエンドポイントを使用します。
レスポンスは `application/zstd` で、ファイル名は
`Content-Disposition` ヘッダーに設定されます。成果物メタデータにファイルサイズがある場合は
`Content-Length` も返します。`Range`を指定すると`206 Partial Content`と`Content-Range`を返し、
範囲外の場合は`416 Range Not Satisfiable`を返します。SHA256チェックサムを`ETag`として返し、
`If-Range`が一致する場合だけ部分配信を継続します。

```sh
DOWNLOAD_URL=$(curl -s -X POST \
  http://localhost:8000/v1/sessions/{session_id}/download-url \
  -H 'X-Authenticated-User-ID: user-123' | jq -r .download_url)
curl -L -C - -o slsg-machine.tar.zst "$DOWNLOAD_URL"
```

配布物には`image.qcow2`、Windows/macOS/Linux用起動スクリプト、各OS用READMEが含まれます。
Linuxでは次のように展開できます。

```sh
tar --zstd -xf slsg-machine.tar.zst
cd slsg-machine
```

URL発行時にbuild_serverの状態を同期します。URLが失効した後も開始済みのレスポンスは中断せず、
切断後の再開時には新しいURLを発行します。まだ成果物が完成していない場合は`409 Conflict`を返します。

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
