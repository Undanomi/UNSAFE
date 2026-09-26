# システム構成

## 1. 対象範囲

- システムを構成するサービス
- 各コンポーネントの責務
- コンポーネント間の通信方向
- 認証、データアクセスおよびサービス間通信の境界
- シナリオ生成から VM のビルド・取得までの流れ

API、データ構造、ジョブ制御、移行および運用の詳細設計は対象外とします。

## 2. 構成

![システム構成図](./images/system-architecture.drawio.png)

| 領域 | コンポーネント | 役割 |
| --- | --- | --- |
| ブラウザ | Next.js クライアント | ユーザー操作 |
| サーバー側 | Next.js + BFF | 画面とAPIを提供する |
| Firebase | Firebase Authentication | 認証基盤 |
| サーバー側 | フロントエンド用PostgreSQL | ユーザー、マシン、チャット、回答履歴を保存する |
| サーバー側 | AI サーバー | シナリオとマシンのソースを生成し、ビルドを依頼する |
| サーバー側 | AI サーバー用PostgreSQL | 生成セッションを保存する |
| サーバー側 | ビルドサーバー | Packer / QEMU で VM をビルドする |
| サーバー側 | ビルドサーバー用PostgreSQL | ビルドジョブと成果物の情報を保存する |

### 2.1 フロントエンド／BFF

- フロントエンドと BFF は、同じ Next.js アプリケーションで動作する
- BFF がブラウザからの操作を受け、AI サーバーや DB とのやり取りを仲介する
- Webアプリケーションからフロントエンド用DBへの読み書きは、Next.jsのサーバー側で行う

### 2.2 認証基盤

- 利用者認証にはFirebase Authenticationを使用する
- ログイン方式はGoogle SSOのみに限定する
- 認証・認可は、次の流れで行う
  1. ブラウザでGoogleログインを完了する
  2. ブラウザがFirebase ID tokenをBFFへ送信する
  3. BFFがID tokenを検証し、Firebase Session Cookieを作成する
  4. BFFがSession Cookieに`HttpOnly`と`SameSite=Lax`を設定し、本番環境では`Secure`も付けて返す
  5. BFFがSession Cookieを検証し、適切な認可を行う
- メールアドレスとパスワードによる登録・認証は提供しない

### 2.3 データストア

- 各サービスは専用のPostgreSQLとDBユーザーを使用する
- フロントエンド用DBの利用者単位の認可はBFFで実施する
- ブラウザ、AIサーバーおよびビルドサーバーには、フロントエンド用PostgreSQLの資格情報を配布しない
- ログイン時に未登録の利用者をFirebase UIDでフロントエンド用PostgreSQLへ登録する
- スキーマは各サービスのマイグレーションで更新する

### 2.4 生成とビルドの連携

- BFF は AI サーバーの API を呼び出し、シナリオとマシンのソース生成を依頼する
- AI サーバーは生成したソースをビルドサーバーへ送り、ビルド状況を取得する

### 2.5 ビルド成果物

- VMのビルド成果物はZIPとしてビルドサーバーのストレージに保存する
- フロントエンドのダウンロード用APIは、対象マシンの公開設定と作成者を確認し、AIサーバーが発行した署名付きURLからZIPを取得してブラウザへ返す

## 3. セキュリティ境界

| 通信元 | 通信先 | 認証・識別 |
| --- | --- | --- |
| ブラウザ | Firebase Authentication | Firebase Authentication |
| ブラウザ | Next.js / BFF | Firebase Session Cookie |
| Next.js / BFF | フロントエンド用PostgreSQL | フロントエンド専用DBユーザー |
| Next.js / BFF | AI サーバー | 利用者 ID ヘッダー（識別用。認証は行わない） |
| AI サーバー | ビルドサーバー | Bearer トークン |
