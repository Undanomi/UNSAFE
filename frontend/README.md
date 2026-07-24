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

## 開発サーバー起動

```bash
pnpm dev
```

[http://localhost:3000](http://localhost:3000) で起動します。

## ビルド

```bash
pnpm build
```

## Lint / Formatter

```bash
pnpm lint
pnpm format
```
