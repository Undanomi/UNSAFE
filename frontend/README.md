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
| `DATABASE_URL` | Yes | フロントエンド用PostgreSQLの接続文字列。サーバーからのみ使用する |
| `AI_SERVER_URL` | No | AIサーバーの接続先。既定値は `http://localhost:8000` |

設定例:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<PROJECT_ID>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<PROJECT_ID>
NEXT_PUBLIC_FIREBASE_APP_ID=...

FIREBASE_ADMIN_PROJECT_ID=<PROJECT_ID>
FIREBASE_ADMIN_CLIENT_EMAIL=...
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"

# フロントエンド用PostgreSQL
DATABASE_URL=postgresql://frontend_service:change-me@localhost:5432/frontend_service

# AIサーバー（Next.js のBFFからのみ参照）
AI_SERVER_URL=http://localhost:8000
```

`NEXT_PUBLIC_*` はブラウザへ公開されます。`FIREBASE_ADMIN_*` と `DATABASE_URL` には秘密情報が含まれるため、`NEXT_PUBLIC_` を付けず、リポジトリへコミットしないでください。

## PostgreSQLマイグレーション

ローカル開発では、`DATABASE_URL` から接続できるPostgreSQL 17を用意し、初回起動前とマイグレーション追加後に次を実行します。マイグレーションコマンドは `.env.local` を自動では読み込まないため、`DATABASE_URL` をシェル環境へ渡します。

```bash
DATABASE_URL=postgresql://frontend_service:change-me@localhost:5432/frontend_service pnpm db:migrate
```

SQLは `db/migrations/`、ランナーは `db/migrate.ts` に配置します。ランナーはadvisory lock、`schema_migrations` の適用履歴、マイグレーション単位のトランザクションを使用します。適用済みSQLが同一であれば再実行しても変更は発生しません。通常のアプリケーション起動処理からDDLは実行しません。

## 開発サーバー起動

開発時は、開発用 Compose override で PostgreSQL だけを起動します。`.env.local` の `DATABASE_URL` に設定したパスワードと、`.env` の `FRONTEND_POSTGRES_PASSWORD` は同じ値にしてください。

```bash
docker compose -f compose.yml -f compose.dev.yml up -d frontend-postgres
DATABASE_URL=postgresql://frontend_service:<FRONTEND_POSTGRES_PASSWORD>@localhost:5432/frontend_service pnpm db:migrate
pnpm run dev
```

PostgreSQL を停止する場合:

```bash
docker compose -f compose.yml -f compose.dev.yml down
```

通常の開発サーバーだけを起動する場合は、次のコマンドを使用します。

```bash
pnpm run dev
```

[http://localhost:3000](http://localhost:3000) で起動します。

## Docker

### フロントエンド単独

`frontend/` だけを起動する場合は、`frontend/` ディレクトリで環境変数ファイルを作成します。フロントエンド用 PostgreSQL は Compose 内で起動し、AIサーバーはホストの `localhost:8000` で動作しているものへ接続します。

```bash
cd frontend
cp .env.example .env
# .env に Firebase 設定と FRONTEND_POSTGRES_PASSWORD を設定
# .env の AI_SERVER_URL を http://host.docker.internal:8000 に変更
docker compose up --build
```

AIサーバーを別途起動していない場合、フロントエンド自体は起動しますが、AI機能は利用できません。AIサーバーの公開ポートを変更した場合は、`.env` の `AI_SERVER_URL` を変更してください。

### 全サービス

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
