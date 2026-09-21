# SLSG フロントエンド
SLSG アプリケーションのフロントエンドです。

## 技術スタック

| 項目 | 内容 |
|------|------|
| フレームワーク | Next.js 16（App Router） |
| UI ライブラリ | React 19 |
| 言語 | TypeScript（strict） |
| スタイリング | Tailwind CSS 4 |
| 業務データベース | PostgreSQL 17 |
| Linter / Formatter | Biome |
| パッケージマネージャー | pnpm |

## セットアップ

Node.js 24、pnpm 10 を使用します。

```bash
pnpm install --frozen-lockfile
```

## Firebase Authentication

### プロジェクト情報の取得
Firebase Console画面に行き、設定 > プロジェクトの設定 > ウェブアプリから「SDKの設定と構成」に接続情報が記載されています。

### 環境変数の設定

`.env.example` をコピーし、ローカル開発用の `.env.local` を作成します。

```bash
cp .env.example .env.local
```

主な環境変数は次のとおりです。

| 環境変数 | 必須 | 用途 |
| --- | --- | --- |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Yes | FirebaseクライアントSDK。ブラウザ向けバンドルへ埋め込まれる |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Yes | Firebase Authenticationのドメイン |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Yes | FirebaseプロジェクトID |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Yes | Firebase Web App ID |
| `FIREBASE_ADMIN_PROJECT_ID` | No | Admin SDK用プロジェクトID。未設定時は `NEXT_PUBLIC_FIREBASE_PROJECT_ID` を使用する |
| `FIREBASE_ADMIN_CLIENT_EMAIL` | Yes | Firebase Admin SDKのサービスアカウント |
| `FIREBASE_ADMIN_PRIVATE_KEY` | Yes | Firebase Admin SDKの秘密鍵。改行は `\\n` で記述する |
| `DEV_DATABASE_URL` | `pnpm run dev` のみ | ホストで実行するNext.js用のPostgreSQL接続文字列。サーバーからのみ使用する |
| `DEV_AI_SERVER_URL` | `pnpm run dev` のみ | ホストで実行するNext.js用のAIサーバー接続先 |

設定例:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<PROJECT_ID>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<PROJECT_ID>
NEXT_PUBLIC_FIREBASE_APP_ID=...

FIREBASE_ADMIN_PROJECT_ID=<PROJECT_ID>
FIREBASE_ADMIN_CLIENT_EMAIL=...
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"

# pnpm run dev 用PostgreSQL
DEV_FRONTEND_POSTGRES_PASSWORD=change-me
DEV_FRONTEND_POSTGRES_PORT=5432
DEV_DATABASE_URL=postgresql://frontend_service:change-me@localhost:5432/frontend_service

# pnpm run dev 用AIサーバー（Next.jsのBFFからのみ参照）
DEV_AI_SERVER_URL=http://localhost:8000
```

`NEXT_PUBLIC_*` はブラウザへ公開されます。`FIREBASE_ADMIN_*`、`DEV_DATABASE_URL`、`*_POSTGRES_PASSWORD` には秘密情報が含まれるため、リポジトリへコミットしないでください。

## 起動方法

### 1. DBだけDocker、フロントエンドは `pnpm run dev`

日常の画面開発向けです。Next.jsのホットリロードをそのまま利用できます。初回は `.env.example` を `.env.local` にコピーし、`DEV_FRONTEND_POSTGRES_PASSWORD` と `DEV_DATABASE_URL` のパスワードを同じ値に設定します。

```bash
pnpm dev:db
pnpm db:seed
pnpm dev
```

`pnpm dev:db` はPostgreSQLを `127.0.0.1` に限定して起動し、未適用のマイグレーションも適用します。`pnpm db:seed` はサンプルユーザー、公開・非公開マシン、チャット履歴、回答済み状態を追加します。`DEV_DATABASE_URL` がローカルホストを指す場合だけ実行でき、何度実行しても同じシードデータを更新します。ポート競合時は `DEV_FRONTEND_POSTGRES_PORT` と `DEV_DATABASE_URL` のポートを同じ値へ変更してください。停止時は次を実行します。

```bash
pnpm dev:db:stop
```

### 2. フロントエンドとDBをDockerで起動

Dockerに近い状態を確認したいときはこちらを使います。PostgreSQLはDocker内部ネットワークに閉じ、ホストには公開しません。

#### フロントエンド単独

`frontend/` だけを起動する場合は、`frontend/` ディレクトリで環境変数ファイルを作成します。フロントエンド用 PostgreSQL は Compose 内で起動し、AIサーバーはホストの `localhost:8000` で動作しているものへ接続します。

```bash
cd frontend
cp .env.example .env
# .env にFirebase設定と FRONTEND_POSTGRES_PASSWORD を設定
# .env の AI_SERVER_URL を http://host.docker.internal:8000 に変更
docker compose up --build
```

AIサーバーを別途起動していない場合、フロントエンド自体は起動しますが、AI機能は利用できません。AIサーバーの公開ポートを変更した場合は、`.env` の `AI_SERVER_URL` を変更してください。

#### 全サービス

リポジトリのルートで共通の環境変数ファイルを作成し、全サービスを起動します。

```bash
cp .env.example .env
# .env に Firebase、PostgreSQL、バックエンド用の値を設定
docker compose up --build
```

[http://localhost:3000](http://localhost:3000) でフロントエンドを開けます。ホスト側のポートを変更する場合は、`.env` の `FRONTEND_PORT` を変更してください。

フロントエンドだけをビルドする場合は、公開 Firebase 設定をビルド引数として渡します。`NEXT_PUBLIC_*` はブラウザ向けバンドルへビルド時に埋め込まれるため、値を変更した場合はイメージを再ビルドしてください。

```bash
docker compose build frontend
```

## ビルド

```bash
pnpm build
```

## Lint / Format

```bash
pnpm lint
pnpm format
```
