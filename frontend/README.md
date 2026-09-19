# SLSG フロントエンド
SLSG アプリケーションのフロントエンドです。

## 技術スタック

| 項目 | 内容 |
|------|------|
| フレームワーク | Next.js 16（App Router） |
| UI ライブラリ | React 19 |
| 言語 | TypeScript（strict） |
| スタイリング | Tailwind CSS 4 |
| Linter / Formatter | Biome |
| パッケージマネージャー | pnpm |

## セットアップ

Node.js 24、pnpm 10 を使用します。

```bash
pnpm install --frozen-lockfile
```

## Firebase

### プロジェクト情報の取得
Firebase Console画面に行き、設定 > プロジェクトの設定 > ウェブアプリから「SDKの設定と構成」に接続情報が記載されています。

### 環境変数の設定

以下の接続情報を `.env.local` に設定します。

```env
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<PROJECT_ID>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<PROJECT_ID>
NEXT_PUBLIC_FIREBASE_APP_ID=...

FIREBASE_ADMIN_PROJECT_ID=<PROJECT_ID>
FIREBASE_ADMIN_CLIENT_EMAIL=...
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"

# AIサーバー（Next.js のBFFからのみ参照）
AI_SERVER_URL=http://localhost:8000
```

## 開発サーバー起動

```bash
pnpm dev
```

[http://localhost:3000](http://localhost:3000) で起動します。

## Docker

リポジトリのルートで共通の環境変数ファイルを作成し、全サービスを起動します。

```bash
cp .env.example .env
# .env に Firebase とバックエンド用の値を設定
docker compose up --build
```

[http://localhost:3000](http://localhost:3000) でフロントエンドを開けます。ホスト側のポートを変更する場合は、`.env` の `FRONTEND_PORT` を変更してください。

フロントエンドだけをビルドする場合は、公開 Firebase 設定をビルド引数として渡します。`NEXT_PUBLIC_*` はブラウザ向けバンドルへビルド時に埋め込まれるため、値を変更した場合はイメージを再ビルドしてください。

```bash
docker compose build frontend
```

本番イメージは Next.js の standalone 出力を使い、非 root ユーザーで実行します。`FIREBASE_ADMIN_*` はイメージには含めず、コンテナ起動時にのみ渡されます。

## ビルド

```bash
pnpm build
```

## Lint / Format

```bash
pnpm lint
pnpm format
```
