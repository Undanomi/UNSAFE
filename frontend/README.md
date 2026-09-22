# SLSG フロントエンド

フロントエンドアプリケーションに関するドキュメントです。

## ドキュメント一覧

| ドキュメント | 内容 |
| --- | --- |
| [アーキテクチャ](docs/architecture.md) | フロントエンドの設計と構成 |
| [認証仕様](docs/auth-spec.md) | 認証・認可の仕様 |
| [画面仕様](docs/pages/README.md) | 各画面の仕様 |

## 技術スタック

| 項目 | 内容 |
|------|------|
| フレームワーク | Next.js 16（App Router） |
| UI ライブラリ | React 19 |
| 言語 | TypeScript（strict） |
| スタイリング | Tailwind CSS 4 |
| データベース | PostgreSQL 17 |
| 認証 | Firebase Authentication |
| Linter / Formatter | Biome |
| パッケージマネージャー | pnpm |

## ディレクトリ構成

```text
frontend/
├── app/
│   ├── (public)/           # 未認証でアクセス可能な画面
│   ├── (private)/          # 認証済みユーザー向け画面
│   ├── actions/            # Server Actions
│   ├── api/                # Route Handlers
├── components/             # 再利用可能な UI コンポーネント
├── db/                     # PostgreSQL マイグレーション
├── docs/                   # アーキテクチャ、認証、各画面の仕様書
├── lib/                    # 外部サービス連携・ビジネスロジック
│   ├── ai/                 # AI サーバーとの連携
│   ├── auth/               # 認証・認可の共通処理
│   ├── database/           # DB クライアント
│   ├── firebase/           # Firebase Client / Admin SDK の初期化
│   ├── machines/           # マシン情報の取得・更新処理
│   ├── chat/               # チャットセッションの処理
│   └── users/              # ユーザー情報の処理
├── types/                  # 型定義
├── compose.yml             # Docker Compose
├── Dockerfile              # フロントエンドのコンテナイメージ
├── public/
├── stores/
├── next.config.ts
└── package.json
```

## 起動前の準備

Docker と Docker Compose を使用します。Node.js 24 と pnpm 10 はコンテナ内に用意されるため、Docker での起動にはホスト側の `pnpm install` は不要です。

全体構成のルート Compose は Docker Compose v5.5.1 で検証されています。`include` 済みサービスへの設定追加を扱えないバージョンでは `conflicts with imported resource` が発生するため、その場合は Docker Compose を更新してください。

全体構成ではビルドワーカーも起動するため、Docker の実行環境で `/dev/kvm` をコンテナに渡せる必要があります。ホストで `stat -c '%g' /dev/kvm` を実行し、得られたグループ ID をルートの `.env` の `KVM_GID` に設定してください。KVM を利用できない環境で画面を開発する場合は、フロントエンド単体の構成を選択してください。

### 起動対象と実行ディレクトリ

開発用・Production 用のどちらも、最初に次のいずれかを選びます。

| 実行場所 | 起動対象 | 設定ファイル |
| --- | --- | --- |
| リポジトリルート | フロントエンド、AI サーバー、ビルドサーバーと各 PostgreSQL | `./.env` |
| `frontend/` | フロントエンドと PostgreSQL | `frontend/.env` |

選択したディレクトリに `.env` がまだない場合は、テンプレートから作成します。

```bash
cp .env.example .env
```

以下の Firebase 設定と環境変数を入力してから起動してください。

### Firebase Authentication

Firebase プロジェクトとウェブアプリの作成、Firebase Authentication の有効化は、[Firebase 公式ドキュメント](https://firebase.google.com/docs/auth/web/start?hl=ja) に従ってください。本アプリでは、Firebase Web App の設定値と Firebase Admin SDK 用サービスアカウントの認証情報が必要です。

本アプリは Google ログインを使用します。Authentication のログインプロバイダーで Google を有効化し、開発・公開環境のホスト名（ローカル開発では `localhost`）を承認済みドメインに登録してください。詳細は[認証仕様](docs/auth-spec.md)と [Google 認証の公式手順](https://firebase.google.com/docs/auth/web/google-signin?hl=ja)を参照してください。

Firebase Console の「プロジェクトの設定」で、ウェブアプリの「SDK の設定と構成」からクライアント用の設定値を取得します。Admin SDK 用には「サービス アカウント」から秘密鍵 JSON を取得し、`project_id`、`client_email`、`private_key` を対応する `FIREBASE_ADMIN_*` に設定してください。

### 環境変数

選択した実行ディレクトリの `.env` に設定します。ルートから実行する場合は、ルートの `.env` の値がフロントエンドにも使われます。

| 環境変数 | 必須 | 用途 |
| --- | --- | --- |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Yes | FirebaseクライアントSDK |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Yes | Firebase Authenticationのドメイン |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Yes | FirebaseプロジェクトID |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Yes | Firebase Web App ID |
| `FIREBASE_ADMIN_PROJECT_ID` | No | Admin SDK用プロジェクトID。未設定時は `NEXT_PUBLIC_FIREBASE_PROJECT_ID` を使用する |
| `FIREBASE_ADMIN_CLIENT_EMAIL` | Yes | Firebase Admin SDKのサービスアカウント |
| `FIREBASE_ADMIN_PRIVATE_KEY` | Yes | Firebase Admin SDKの秘密鍵。改行は `\n`（バックスラッシュ1文字と n）で記述する |
| `FRONTEND_POSTGRES_PASSWORD` | Yes | Compose内のPostgreSQLに使用するパスワード |
| `FRONTEND_PORT` | No | フロントエンドを公開するホスト側ポート。既定値は`3000` |
| `AI_SERVER_URL` | No | フロントエンド単独起動時のAIサーバー接続先 |

```env
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<PROJECT_ID>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<PROJECT_ID>
NEXT_PUBLIC_FIREBASE_APP_ID=...

FIREBASE_ADMIN_PROJECT_ID=<PROJECT_ID>
FIREBASE_ADMIN_CLIENT_EMAIL=...
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"

FRONTEND_POSTGRES_PASSWORD=change-me
FRONTEND_PORT=3000
# フロントエンド単体で、ホスト上の AI サーバーに接続する場合
# AI_SERVER_URL=http://host.docker.internal:8000
```

ルートでは `.env` に次の値も設定してください。

| 環境変数 | 用途 |
| --- | --- |
| `AI_POSTGRES_PASSWORD` | AI サーバー用 PostgreSQL のパスワード |
| `BUILD_POSTGRES_PASSWORD` | ビルドサーバー用 PostgreSQL のパスワード |
| `INTERNAL_API_TOKEN` / `BUILD_SERVER_TOKEN` | 両方に同一の32文字以上のランダムな値を設定 |
| `KVM_GID` | Linux ホストの `stat -c '%g' /dev/kvm` で得られるグループ ID |

フロントエンド単体の構成には AI サーバーが含まれません。AI 機能を使う場合は別途起動し、コンテナから到達可能な URL を `AI_SERVER_URL` に設定してください。Docker Desktop でホスト上の AI サーバーを利用する例は `http://host.docker.internal:8000` です。全体構成では既定の `http://ai-server:8000` を使用するため、この上書きは不要です。

`NEXT_PUBLIC_*` はブラウザへ公開されます。`FIREBASE_ADMIN_*`、`*_POSTGRES_PASSWORD`、API トークン・キーには秘密情報が含まれるため、リポジトリへコミットしないでください。

### 開発サーバー用の Firebase 設定

`docker compose --profile dev` は `frontend-dev` コンテナで `pnpm dev` を実行します。このサービスには `NEXT_PUBLIC_FIREBASE_*` をコンテナ環境変数として渡していないため、Next.js がソースとともにマウントされる `frontend/.env.local` から読み込む必要があります。

Compose 用の `.env` はコンテナへ自動的にすべて渡されるわけではありません。したがって、Compose 用 `.env` に設定した値と同じ `NEXT_PUBLIC_FIREBASE_*` を `frontend/.env.local` にも設定してください。

```env
# frontend/.env.local
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<PROJECT_ID>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<PROJECT_ID>
NEXT_PUBLIC_FIREBASE_APP_ID=...
```

`frontend/.env.local` は Git 管理対象外です。Firebase の Admin SDK 用設定は Compose が `frontend-dev` へ渡すため、このファイルに追加する必要はありません。

## 起動方法

[起動前の準備](#起動前の準備)で選択したディレクトリから実行します。フロントエンド用 PostgreSQL は Docker 内部ネットワークに閉じ、マイグレーションは起動時に自動適用されます。ルートから実行する場合は、どちらの profile でもバックエンド一式が起動します。

### 開発用（dev profile）

開発用の `frontend/.env.local` を準備してから実行します。

```bash
docker compose --profile dev up --build
```

ソースコードをコンテナへ bind mount し、`pnpm dev --webpack` を実行します。`app/` などのソースを保存すると Fast Refresh が反映されます。Docker Desktop 上での変更検知のため、開発コンテナには `WATCHPACK_POLLING=true` を設定しています。ホストで直接実行する `pnpm dev` は Turbopack を使用します。

### Production イメージの確認（frontend profile）

```bash
docker compose --profile frontend up --build
```

ビルド済みの standalone frontend が起動します。公開 Firebase 設定は Compose がビルド引数として渡します。`NEXT_PUBLIC_*` はブラウザ向けバンドルへビルド時に埋め込まれるため、値を変更した場合は再ビルドしてください。

### 起動確認

ブラウザで [http://localhost:3000](http://localhost:3000) を開きます。`FRONTEND_PORT` を変更した場合は、そのポートを使用してください。

別のターミナルで、同じ実行ディレクトリから状態とログを確認できます。Production 用は `dev` を `frontend` に置き換えてください。

```bash
docker compose --profile dev ps -a
docker compose --profile dev logs --tail=100
```

`frontend-migrate` は正常終了（終了コード `0`）、フロントエンドと PostgreSQL は `healthy` が目安です。フロントエンドのヘルスチェックは DB 接続を確認するもので、Firebase 認証や AI 連携の成功までは保証しません。

### 停止・起動モードの切り替え

起動時と同じディレクトリで、使用中の profile に対応するコマンドを実行します。

| 起動モード | 停止コマンド |
| --- | --- |
| 開発用 | `docker compose --profile dev down` |
| Production 用 | `docker compose --profile frontend down` |

どちらも既定で同じホストポートを使うため、モードを切り替えるときは現在の構成を停止してから、切り替え先の起動コマンドを実行してください。ルートでの停止はバックエンドも対象になります。

上記の停止コマンドは PostgreSQL のデータを保持します。`-v` を付けると Compose が管理するデータ volume も削除されます。フロントエンドの DB、開発用の `node_modules`、pnpm store、Next.js キャッシュに加え、ルートで実行した場合はバックエンドの DB や成果物なども削除対象です。

### シードデータの追加（開発用・Production 共通）

画面確認用の公開サンプルデータが必要な場合は、同じ実行ディレクトリで別のターミナルから実行します。

```bash
docker compose --profile seed run --rm frontend-seed
```

このコマンドは架空ユーザーと公開マシンを追加します。同じ固定 ID のシードデータは再実行時に更新されますが、それ以外のデータは削除しません。通常の profile ではシードデータは投入されません。

### フロントエンドのイメージだけをビルド

同じ実行ディレクトリで実行します。コンテナは起動しません。

```bash
docker compose --profile frontend build frontend
```

## ホストでのビルド・Lint / Format

ホストで確認する場合は Node.js 24 と pnpm 10 を用意し、`frontend/` ディレクトリで依存関係をインストールしてください。

```bash
pnpm install --frozen-lockfile
```

ビルドを確認します。

```bash
pnpm build
```

Lint・型チェックと、自動修正・フォーマットを実行します。

```bash
pnpm lint
pnpm format
```
