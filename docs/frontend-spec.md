# フロントエンド設計

## 1. 本ドキュメントの目的

- 本ドキュメントは、SLSG のフロントエンドアプリケーションの設計及び責務の方針を示し、以降の実装を進める際の指針とすることを目的とする
- 対象：フロントエンドの構成・フロントエンドの責務・フロントエンドに持たせる機能
- 対象外：実装の詳細・認証認可・フロントエンドDB定義
- システム全体の基本方針は [システム仕様書](./spec.md) に従う

## 2. 構成

```mermaid
flowchart LR
  subgraph Browser["ブラウザ（クライアント）"]
    CC["Client Component"]
  end

  subgraph Next["Next.js サーバー（BFF）"]
    SC["Server Component"]
    SA["Server Action"]
    RH["Route Handler"]
    S["Service"]
  end

  AI["AIサーバー"]
  Build["ビルドサーバー"]
  DB["BFF用データストア"]

  CC -->|"更新操作"| SA
  CC -->|"ポーリング・ダウンロード"| RH
  SC -->|"データ取得"| S
  SA --> S
  RH --> S
  S --> AI
  S --> Build
  S --> DB
  SC -->|"HTML / RSC Payload"| CC
```

図の破線より左側が利用者のブラウザで動くクライアント、右側が Next.js サーバー上で動く BFF である。UI コンポーネントはクライアントから Server Action または Route Handler を呼び出す。BFF 内では、それらの入口が Service を呼び出し、Service が AI サーバー、ビルドサーバー、フロント用 DB と通信する。

Server Action、Route Handler、Service はいずれも Next.js サーバー上で動作する。Service は BFF 内部の処理であり、ブラウザから直接呼び出さない。

## 3. 各構成要素の役割

### 3.1 Client Component

Client Component はブラウザ上で動作し、利用者との対話を担当する。画面の入力、ボタン操作、表示中のUI状態を扱う。下流システムおよび Service へ直接通信しない。

- 画面の入力欄、ボタン、一覧の表示などを行う
- シナリオ生成やビルド要求などの更新操作を Server Action へ渡す
- ビルド進捗の取得や成果物のダウンロードを Route Handler へ要求する

### 3.2 Server Component

Server Component は Next.js サーバー上で動作し、画面の初期表示および画面遷移時のサーバー描画を担当する。必要なデータは Service を直接呼び出して取得し、HTML および React Server Components Payload としてブラウザへ返す。

- 画面表示に必要なデータを取得し、画面を組み立てる
- Client Component へ表示データを渡す
- ブラウザ上のイベント処理や継続的なUI状態の管理は行わない

### 3.3 Server Action

Server Action は、React のフォーム送信やボタン操作に対応する Next.js サーバー側の関数である。シナリオの生成やビルド要求など、利用者による更新操作の入口として使用する。下流システムとの通信方法・接続先・応答形式は Service に隠蔽する。

```text
「仮想マシンを作成」ボタン
   ↓
createMachineAction(入力値)
   ↓
仮想マシン生成リクエスト Service
```

Server Action の責務は次のとおりである。
- Client Component から受け取った入力を検証する
- 認証済み利用者の権限を確認する
- 対応する Service を呼び出す
- Service の結果を UI 向けに返す

### 3.4 Route Handler

Route Handler は、Next.js 内で HTTP リクエストを受け取り、HTTP レスポンスを返す入口である。通常の更新操作には使用せず、HTTP メソッド、レスポンスヘッダー、ストリーミングなどを利用する必要がある場合に使用する。

採用する用途は次のとおりである。

| 用途 | Server Action ではなく Route Handler を使う理由 |
|---|---|
| ビルド進捗のポーリング | ブラウザが繰り返し `GET` で状態を取得するため、進捗取得が HTTP の読み取り操作であることを明確にできる |
| 成果物のダウンロード | 大容量ファイルをストリームで返し、`Range` や `Content-Disposition` などの HTTP ヘッダーを扱うため（これはブラウザから直接ダウンロードする場合もある） |

Route Handler 自身も、下流サービスの呼び出しは Service に委譲する。

### 3.5 Service

Service は、Next.js サーバーの内部に置くサーバー専用の処理である。Server Component、Server Action、Route Handler から呼び出され、下流システムとの通信を集約する。ブラウザから直接呼び出さない。

Service の責務は次のとおりである。

- AI サーバー、ビルドサーバー、BFF用データストアとの通信を一箇所にまとめる
- 下流サービスごとのデータ形式を、画面で利用する形式へ変換する
- 複数の下流サービスから得た情報を必要に応じてまとめる
