# SLSG への貢献

SLSG への貢献を歓迎します。Issue や PR の出し方と、開発環境の準備を案内します。

## 目次

- [Issue を作成する](#issue-を作成する)
- [PR を作成する](#pr-を作成する)
- [開発環境を準備する](#開発環境を準備する)
- [Docker で起動する](#docker-で起動する)
- [停止する](#停止する)
- [開発から PR まで](#開発から-pr-まで)

## Issue を作成する

1. [既存の Issue](https://github.com/Undanomi/SLSG/issues) を検索し、重複がないか確認します。
2. [新しい Issue](https://github.com/Undanomi/SLSG/issues/new/choose) を開き、内容に合うテンプレートを選びます。

| テンプレート | 使う場面 |
| --- | --- |
| 通常 Issue | 単独の報告・提案 |
| 親 Issue | 複数の子 Issue に分ける大きな作業 |
| 子 Issue | 親 Issue に紐付く個別作業。親の番号か URL を記載 |

どの Issue も、選択したテンプレートの見出しやチェックリストに従って記入してください。

**記載する内容**

- 不具合：再現手順、実際の結果、期待する結果、利用環境
- 提案：背景、想定する変更、完了条件

## PR を作成する

| 変更内容 | 事前の Issue |
| --- | --- |
| 誤字・リンク切れなど小さな文書修正 | 不要 |
| 機能追加、動作変更、不具合修正 | 必要。着手前に背景と方針を共有 |

**記載する内容**

- 変更目的、変更内容、関連 Issue
- UI を変更した場合は、変更前後の画像を添付

## 開発環境を準備する

### 前提

作業するサービスと起動方法に応じて、必要なツールを用意してください。

- **Docker での起動**：Docker、Docker Compose
- **フロントエンドの開発・テスト**：Node.js 24、pnpm 10
- **AI サーバーの開発・テスト**：Python 3.13、uv
- **ビルドサーバーの開発・テスト**：Go 1.25

### Firebase

1. [Firebase コンソール](https://console.firebase.google.com/)で開発用プロジェクトと Web アプリを作成します。Web アプリの `apiKey`、`authDomain`、`projectId`、`appId` を控えてください。
2. Authentication で Google ログインを有効にし、承認済みドメインに `localhost` があるか確認します。新規プロジェクトでは自動登録されない場合があります（[Google ログインの手順](https://firebase.google.com/docs/auth/web/google-signin)）。
3. プロジェクト設定の「サービス アカウント」で Admin SDK 用の秘密鍵を取得します。必要な値は `project_id`、`client_email`、`private_key` です（[Admin SDK の手順](https://firebase.google.com/docs/admin/setup)）。

### Gemini / OpenAI

シナリオを生成する場合は、Gemini か OpenAI のどちらかを設定します。外部 API を使わずに動作確認する場合は `AI_PROVIDER=stub` を指定します。

| 選択 | AI サーバー側の設定 | キーの取得 |
| --- | --- | --- |
| Gemini | `AI_PROVIDER=gemini`、`GEMINI_API_KEY` | [Google AI Studio](https://ai.google.dev/gemini-api/docs/get-started) |
| OpenAI | `AI_PROVIDER=openai`、`OPENAI_API_KEY` | [OpenAI API](https://platform.openai.com/docs/quickstart/make-your-first-api-request) |

### 環境変数

ルートから全体を起動する場合、次のファイルを作成します。

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

| ファイルパス | 環境変数名 | 説明 |
| --- | --- | --- |
| `.env` | `AI_POSTGRES_PASSWORD`、`BUILD_POSTGRES_PASSWORD`、`FRONTEND_POSTGRES_PASSWORD` | DB ごとに異なるランダム値 |
| `.env` | `INTERNAL_API_TOKEN`、`BUILD_SERVER_TOKEN` | 同じ32文字以上のランダム値を両方に設定 |
| `.env` | `FIREBASE_ADMIN_PROJECT_ID`、`FIREBASE_ADMIN_CLIENT_EMAIL`、`FIREBASE_ADMIN_PRIVATE_KEY` | Admin SDK のサービスアカウント設定。秘密鍵の改行は `\n` として記載 |
| `.env` | `AI_PROVIDER`、`GEMINI_API_KEY` または `OPENAI_API_KEY` | 利用する AI プロバイダーとその API キー |
| `.env` | `SQLADMIN_USERNAME`、`SQLADMIN_PASSWORD`、`SQLADMIN_SESSION_SECRET`、`SQLADMIN_SECURE_COOKIES` | SQLAdmin の認証情報と Cookie 設定。ルートの `.env.example` にはないため追記 |
| `.env` | `KVM_GID` | `/dev/kvm` のグループ ID。VM ビルド時に設定 |
| `frontend/.env.local` | `NEXT_PUBLIC_FIREBASE_API_KEY`、`NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`、`NEXT_PUBLIC_FIREBASE_PROJECT_ID`、`NEXT_PUBLIC_FIREBASE_APP_ID` | 開発用フロントエンドが読む Firebase Web アプリの設定 |

> [!CAUTION]
> 開発用フロントエンドの `NEXT_PUBLIC_*` は `frontend/.env.local` に設定してください。ルートの `.env` だけではブラウザに反映されません。

### ランダム値の生成

DB パスワードはそれぞれ別に生成します。`INTERNAL_API_TOKEN` と `BUILD_SERVER_TOKEN` には、生成した同じ値を設定してください。

```bash
openssl rand -hex 32
```

### VM ビルド用イメージ

- 起動前に `build_server/builder/base_images/debian-13.7.0-amd64.qcow2` を配置します。イメージはリポジトリに含まれていません。別のバージョンを使う場合、ファイル名は `debian-<version>-amd64.qcow2` とします。
- イメージ内には SSH 接続可能な `provisioner` ユーザー（パスワード `provisioner`、`sudo` 利用可）が必要です。

> [!CAUTION]
> Debian 13.7.0 以外のベースイメージでは動作を検証していません。別のバージョンを使う場合は、ファイル名を合わせたうえで VM ビルドを確認してください。

<details>
<summary>ベースイメージを新しく作る場合</summary>

x86_64 Linux に `qemu-img` と `qemu-system-x86_64` を入れ、[Debian netinst](https://www.debian.org/CD/netinst/) の ISO を `build_server/builder/iso/debian-13.7.0-amd64-netinst.iso` に配置します。

```bash
cd build_server/builder/scripts
bash 01_disk_create.sh
bash 02_install.sh
```

インストーラーで上記の `provisioner` ユーザー、SSH、`sudo` を設定してください。スクリプト内の ISO 名とゲスト OS のバージョンを一致させます。

</details>

## Docker で起動する

> [!CAUTION]
> ルートの Compose 構成は Docker Compose v5.5.1 で確認しています。`docker compose version` でバージョンを確認し、古い版で `include` のエラーが出る場合は更新してください。

> [!CAUTION]
> ビルドサーバーには x86_64 Linux の `/dev/kvm` が必要です。ARM Mac などではフロントエンドと AI サーバーを単体で起動し、ビルドサーバーの動作は x86_64 Linux で確認してください。

### （推奨）サービス全体で起動する

リポジトリルートで実行します。AI サーバー、ビルドサーバー、各 DB、開発用フロントエンド、SQLAdmin が起動し、サンプルデータも投入されます。フロントエンドの環境変数を変更したら、フロントエンドを再起動してください。

```bash
docker compose --profile dev --profile seed --profile admin up --build
```

### ページ対応表

`FRONTEND_PORT` を変更した場合は、URL の `3000` をその値に読み替えてください。

| サーバー | 内容 | URL |
| --- | --- | --- |
| フロントエンド | 開発用画面 | [http://localhost:3000](http://localhost:3000) |
| AI サーバー | API ドキュメント | [http://localhost:8000/docs](http://localhost:8000/docs) |
| SQLAdmin | 管理画面 | [http://localhost:8001/admin](http://localhost:8001/admin) |

### サービス単体で起動する

<details>
<summary>フロントエンド</summary>

```bash
cd frontend
cp .env.example .env
cp -n .env.example .env.local
```

`.env` に `FRONTEND_POSTGRES_PASSWORD` と Firebase Admin SDK の認証情報、`.env.local` に `NEXT_PUBLIC_*` を設定します。既存の `.env.local` は上書きされず、同じ変数が `.env` にもある場合は `.env.local` が優先されます。

```bash
docker compose --profile dev up --build
```

AI サーバーに接続する場合は、`.env` の `AI_SERVER_URL` を設定します。既定値は Docker Desktop 向けです。AI サーバーを起動しない場合、生成機能は使えません。

</details>

<details>
<summary>AI サーバー</summary>

```bash
cd ai_server
cp .env.example .env
```

`.env` に `AI_POSTGRES_PASSWORD` と、32文字以上の `BUILD_SERVER_TOKEN`・`SOURCE_SANDBOX_TOKEN`・`DOWNLOAD_SIGNING_SECRET` を設定します。シナリオ生成には `AI_PROVIDER` と API キーも必要です。外部 API を使わずに確認する場合は `AI_PROVIDER=stub` を指定します。

```bash
docker compose --env-file .env up --build
```

VM ビルドには、ビルドサーバーへ到達できる通信経路と `AI_BUILD_SERVER_URL` が必要です。`BUILD_SERVER_TOKEN` には、ビルドサーバーの `INTERNAL_API_TOKEN` と同じ値を設定します。ビルド API はホストに公開されません。

</details>

<details>
<summary>ビルドサーバー</summary>

```bash
cd build_server
cp .env.example .env
```

`.env` に `BUILD_POSTGRES_PASSWORD`、32文字以上の `INTERNAL_API_TOKEN`、`stat -c '%g' /dev/kvm` で確認した `KVM_GID` を設定します。[VM ビルド用イメージ](#vm-ビルド用イメージ)も配置してください。

```bash
docker compose up --build
```

ビルド API はホストに公開されません。

</details>

## 停止する

起動したディレクトリで、該当するコマンドを実行します。

| 起動元 | 停止コマンド |
| --- | --- |
| リポジトリルート | `docker compose --profile dev --profile seed --profile admin down` |
| `frontend/` | `docker compose --profile dev down` |
| `ai_server/` | `docker compose --env-file .env down` |
| `build_server/` | `docker compose down` |

`down -v` はボリュームと保存データも削除します。必要な場合だけ使ってください。

## 開発から PR まで

1. **ブランチ作成**：`main` を更新し、作業内容が分かる名前でブランチを作ります。

   ```bash
   git switch main
   git pull --ff-only origin main
   git switch -c 123-short-description
   ```

2. **Test & Lint**：エラーがないことを確認します。

   | 対象 | コマンド |
   | --- | --- |
   | フロントエンド | `cd frontend && pnpm lint` |
   | AI サーバー | `cd ai_server && uv run ruff check . && uv run pytest` |
   | ビルドサーバー | `cd build_server && go test ./...` |

3. **コミット**：[Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/) を参考に、変更内容が分かるメッセージを付けてください。

4. **プルリクエスト**：`git push -u origin HEAD` でブランチを送信し、`main` 向けの PR を作成します。
