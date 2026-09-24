# SLSG への貢献

SLSG への貢献を歓迎します。以下に記載の方法で、気軽に参加してください。

## 目次

- [Issue を作成する](#issue-を作成する)
- [PR を作成する](#pr-を作成する)
- [開発環境を準備する](#開発環境を準備する)
- [Docker で起動する](#docker-で起動する)
- [停止する](#停止する)
- [開発から PR まで](#開発から-pr-まで)

## Issue を作成する

1. [既存の Issue](https://github.com/Undanomi/SLSG/issues) を検索し、重複がないか確認します。
2. [新しい Issue](https://github.com/Undanomi/SLSG/issues/new/choose) を開き、作業規模に合うテンプレートを選びます。

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
- UIの変更が含まれる場合、変更前後の画像を添付する

## 開発環境を準備する

### 前提

作業するサービスと起動方法に応じて、必要なツールを用意してください。

- **Docker での起動**：Docker、Docker Compose
- **フロントエンドの開発・テスト**：Node.js 24、pnpm 10
- **AI サーバーの開発・テスト**：Python 3.13、uv
- **ビルドサーバーの開発・テスト**：Go 1.25
- **Docker を使わない VM ビルド**：Packer、QEMU、PostgreSQL

### Firebase

1. [Firebase コンソール](https://console.firebase.google.com/)で開発用プロジェクトと Web アプリを作成し、`apiKey`、`authDomain`、`projectId`、`appId` を控えます。
2. Authentication のログイン方法で Google を有効にし、承認済みドメインに `localhost` があることを確認します。新規プロジェクトでは自動登録されない場合があります（[Google ログインの手順](https://firebase.google.com/docs/auth/web/google-signin)）。
3. プロジェクト設定の「サービス アカウント」から Admin SDK 用の秘密鍵を取得し、`project_id`、`client_email`、`private_key` を控えます（[Admin SDK の手順](https://firebase.google.com/docs/admin/setup)）。

### Gemini / OpenAI

実際にシナリオを生成する場合は、**どちらか一方**を設定します。API 接続を使わない確認には `AI_PROVIDER=stub` を使えます。

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
| `.env` | `INTERNAL_API_TOKEN`、`BUILD_SERVER_TOKEN` | 両方に同じ32文字以上のランダム値 |
| `.env` | `NEXT_PUBLIC_FIREBASE_API_KEY`、`NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`、`NEXT_PUBLIC_FIREBASE_PROJECT_ID`、`NEXT_PUBLIC_FIREBASE_APP_ID` | Firebase Web アプリの設定 |
| `.env` | `FIREBASE_ADMIN_PROJECT_ID`、`FIREBASE_ADMIN_CLIENT_EMAIL`、`FIREBASE_ADMIN_PRIVATE_KEY` | Admin SDK のサービスアカウント設定。秘密鍵の改行は `\n` として記載 |
| `.env` | `AI_PROVIDER`、`GEMINI_API_KEY` または `OPENAI_API_KEY` | 利用する AI プロバイダーとその API キー |
| `.env` | `SQLADMIN_USERNAME`、`SQLADMIN_PASSWORD`、`SQLADMIN_SESSION_SECRET`、`SQLADMIN_SECURE_COOKIES` | SQLAdmin の認証情報と Cookie 設定。ルートの `.env.example` にはないため追記 |
| `.env` | `KVM_GID` | `/dev/kvm` のグループ ID。VM ビルド時に設定 |
| `frontend/.env.local` | `NEXT_PUBLIC_FIREBASE_API_KEY`、`NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`、`NEXT_PUBLIC_FIREBASE_PROJECT_ID`、`NEXT_PUBLIC_FIREBASE_APP_ID` | 開発用フロントエンドが読む Firebase Web アプリの設定 |

> [!CAUTION]
> 開発用フロントエンドには `frontend/.env.local` が必要です。ルートの `.env` だけに公開値を書いてもブラウザには反映されません。

### ランダム値の生成

DB パスワードはそれぞれ別に生成します。`INTERNAL_API_TOKEN` と `BUILD_SERVER_TOKEN` には、生成した同じ値を設定してください。

```bash
openssl rand -hex 32
```

### VM ビルド用イメージ

- 起動前に `build_server/builder/base_images/debian-13.7.0-amd64.qcow2` を配置します。イメージはリポジトリに同梱されていません。別バージョンは `debian-<version>-amd64.qcow2` という名前にします。
- イメージ内には SSH 接続可能な `provisioner` ユーザー（パスワード `provisioner`、`sudo` 利用可）が必要です。

> [!CAUTION]
> Debian 13.7.0 以外のベースイメージは動作を検証していません。別バージョンを使う場合は、イメージ名を合わせたうえで VM ビルドを確認してください。

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
> ルートの Compose 構成は Docker Compose v5.5.1 で確認しています。`docker compose version` で確認し、古い版で `include` の衝突が起きる場合は更新してください。

> [!CAUTION]
> ビルドサーバーには x86_64 Linux の `/dev/kvm` が必要です。ARM Mac などで利用できない場合は、フロントエンドと AI サーバーを単体起動し、ビルドサーバーの動作は対応している環境で確認してください。

### （推奨）サービス全体で起動する

リポジトリルートで実行します。AI サーバー、ビルドサーバー、各 DB、開発用フロントエンド、SQLAdmin が起動し、サンプルデータも投入されます。

```bash
docker compose --profile dev --profile seed --profile admin up --build
```

- 環境変数の変更後はフロントエンドを再起動してください。production 用 `frontend` イメージの `NEXT_PUBLIC_*` を変えた場合は再ビルドが必要です。

> [!CAUTION]
> Docker Desktop ではファイル変更の検知に時間がかかり、Next.js の Fast Refresh が遅れる場合があります。

<details>
<summary>--profile seed について</summary>

`--profile seed` を指定すると、フロントエンド DB のマイグレーション後、シードデータが投入されます。

</details>

<details>
<summary>--profile admin について</summary>

`--profile admin` を指定すると、AI サーバーの DB を確認・編集できる SQLAdmin が起動します。起動前にルートの `.env` に次を追記してください。

```dotenv
SQLADMIN_USERNAME=admin
SQLADMIN_PASSWORD=<十分に長いランダムなパスワード>
SQLADMIN_SESSION_SECRET=<32文字以上のランダム値>
SQLADMIN_SECURE_COOKIES=false
```

`ai_server/` から単体起動する場合は、同じ設定を `ai_server/.env` に追加し、起動コマンドに `--profile admin` を付けます。管理画面のポートはローカルホストにだけ公開されます。既存データを編集できるため、実行中の処理に関わる値の変更には注意してください。

</details>

### ページ対応表

フロントエンドのポートを `FRONTEND_PORT` で変更した場合は、URL の `3000` を設定した値に読み替えてください。

| サーバー | 内容 | URL |
| --- | --- | --- |
| フロントエンド | 開発用画面 | [http://localhost:3000](http://localhost:3000) |
| AI サーバー | API ドキュメント | [http://localhost:8000/docs](http://localhost:8000/docs) |
| SQLAdmin | 管理画面 | [http://localhost:8001/admin](http://localhost:8001/admin) |

### サービス単体で起動する

<details>
<summary>フロントエンド</summary>

`frontend/.env` に Firebase の Web アプリ・Admin SDK の値、`FRONTEND_POSTGRES_PASSWORD` を設定します。必要なら `FRONTEND_PORT` も変更します。

```bash
cd frontend
cp .env.example .env
docker compose --profile dev up --build
```

別の AI サーバーと接続する場合、コンテナから到達できる `AI_SERVER_URL` を設定します。既定の `http://host.docker.internal:8000` は Docker Desktop 向けです。AI サーバーがなければ生成機能は使えません。

</details>

<details>
<summary>AI サーバー</summary>

`ai_server/.env` に `AI_POSTGRES_PASSWORD`・`BUILD_SERVER_TOKEN`・`SOURCE_SANDBOX_TOKEN`・`DOWNLOAD_SIGNING_SECRET` を設定します。実際に生成する場合は `AI_PROVIDER` と対応する API キーも必要です。

```bash
cd ai_server
cp .env.example .env
docker compose --env-file .env up --build
```

ビルドサーバーがなければ VM ビルドは完了しません。単体 Compose 同士は別ネットワークで、ビルド API はホストにも公開されません。連携には通信経路、`AI_BUILD_SERVER_URL`、相手の `INTERNAL_API_TOKEN` と一致する `BUILD_SERVER_TOKEN` が必要です。`DATABASE_URL` の `<password>` はホスト上で直接起動する場合の設定です。Compose ではコンテナ用の接続先に上書きされます。

</details>

<details>
<summary>ビルドサーバー</summary>

`build_server/.env` に `BUILD_POSTGRES_PASSWORD`・`INTERNAL_API_TOKEN`・`KVM_GID` を設定します。

```bash
cd build_server
cp .env.example .env
docker compose up --build
```

</details>

## 停止する

起動したディレクトリで、profile を指定して停止してください。以下はリポジトリルートから全体を起動した場合のコマンド例です。

```bash
docker compose --profile dev --profile seed --profile admin down
```

`down -v` は volume と保存データも削除するため、必要な場合だけ使ってください。

## 開発から PR まで

1. **ブランチ作成**：mainブランチから、作業内容に合わせた名前のブランチを作成します。

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

3. **コミット**：[Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/) を参考にコミットを作成してください。

4. **プルリクエスト**：`git push -u origin HEAD` で push し、`main` 向けに作成します。
