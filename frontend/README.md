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

`.env.example` をコピーして `.env` を作成します。

```bash
cp .env.example .env
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
| `FRONTEND_POSTGRES_PASSWORD` | Yes | Compose内のPostgreSQLに使用するパスワード |
| `FRONTEND_PORT` | No | フロントエンドを公開するホスト側ポート。既定値は`3000` |
| `AI_SERVER_URL` | No | フロントエンド単独起動時のAIサーバー接続先 |

設定例:

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
AI_SERVER_URL=http://host.docker.internal:8000
```

`NEXT_PUBLIC_*` はブラウザへ公開されます。`FIREBASE_ADMIN_*`、`*_POSTGRES_PASSWORD` には秘密情報が含まれるため、リポジトリへコミットしないでください。

## 起動方法

フロントエンド、PostgreSQL、マイグレーションはまとめてComposeで起動します。PostgreSQLはDocker内部ネットワークに閉じ、ホストには公開しません。マイグレーションは起動時に自動適用されます。

```bash
cd frontend
cp .env.example .env
# .env にFirebase設定とFRONTEND_POSTGRES_PASSWORDを設定
docker compose up --build
```

画面開発用の公開サンプルデータが必要な場合は、別のターミナルからシードサービスを明示的に実行します。

```bash
docker compose run --rm frontend-seed
```

このコマンドは架空ユーザーと公開マシンを追加します。同じ固定IDのシードデータは再実行時に更新されますが、それ以外のデータは削除しません。通常の `docker compose up` ではシードデータは投入されません。

AIサーバーを別途起動していない場合、フロントエンド自体は起動しますが、AI機能は利用できません。AIサーバーの公開ポートを変更した場合は、`.env` の `AI_SERVER_URL` を変更してください。

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
