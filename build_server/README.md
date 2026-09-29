# UNSAFE Build Server

## 概要

Build Server は学習用 VM を作る内部サービスです。AI Server から受け取ったシナリオソースを使い、ビルドを非同期で進めます。進捗と成果物は PostgreSQL に保存します。完成した VM イメージと起動手順は ZIP にまとめ、AI Server 経由で利用者に配信します。

## 起動方法

### Build Server だけを起動する

**1. VM のビルド環境を用意する**

Docker を実行する Linux ホストで `/dev/kvm` が使えることを確認してください。KVM は VM の実行を高速化する Linux の機能です。worker は、対象 OS のベースイメージを土台にして VM を作ります。ベースイメージは `qcow2` 形式のディスクファイルです。既定の `Debian 13.7.0` をビルドする場合は、次の場所に配置します。

```text
build_server/builder/base_images/debian-13.7.0-amd64.qcow2
```

**2. 環境変数を設定する**

リポジトリのルートでテンプレートをコピーし、KVM デバイスのグループ ID を調べます。

```sh
cp build_server/.env.example build_server/.env
stat -c '%g' /dev/kvm
```

次の表に従って `build_server/.env` を編集してください。パスワードとトークンには、`openssl rand -hex 32` などで**別々の値**を生成します。

| 変数 | 設定する値 |
| --- | --- |
| `INTERNAL_API_TOKEN` | 内部 API を呼ぶための 32 文字以上のトークン。AI Server と接続する場合は、AI Server の `BUILD_SERVER_TOKEN` に同じ値を設定する。 |
| `BUILD_POSTGRES_PASSWORD` | ビルド状態を保存する PostgreSQL のパスワード。トークンとは別の値にする。 |
| `KVM_GID` | 上の `stat` で表示された数値。worker が `/dev/kvm` を使うために必要。 |

**3. 起動して確認する**

```sh
docker compose --env-file build_server/.env -f build_server/compose.yml up --build -d
docker compose --env-file build_server/.env -f build_server/compose.yml ps
```

Build Server の API は Compose 内部の 8080 番ポートで待ち受けます。ホストからは直接アクセスできません。AI Server と連携する場合は、次のルート Compose を使うと両サービスが同じ内部ネットワークにつながります。

### AI Server と一緒に起動する

両サービスを連携させる場合は、リポジトリのルートにある Compose を使います。テンプレートをコピーしてから、`.env` に次の値を設定してください。

```sh
cp .env.example .env
```

| 変数 | 設定する値 |
| --- | --- |
| `BUILD_POSTGRES_PASSWORD` | Build Server 用 PostgreSQL のパスワード。 |
| `AI_POSTGRES_PASSWORD` / `FRONTEND_POSTGRES_PASSWORD` | ほかの PostgreSQL 用パスワード。それぞれ異なる値にする。フロントエンドを起動しない場合も後者は Compose の設定読み込みに必要。 |
| `INTERNAL_API_TOKEN` / `BUILD_SERVER_TOKEN` | サービス間通信の認証に使う同じ 32 文字以上の値。 |
| `KVM_GID` | `/dev/kvm` のグループ ID。`stat -c '%g' /dev/kvm` で確認する。 |

AI による生成を使う場合は、`AI_PROVIDER` と選択したプロバイダーの API キーも必要です。設定値と `rockyou.txt` の説明は [AI Server の起動方法](../ai_server/README.md#起動方法)を参照してください。ベースイメージは、単体起動と同じ場所に用意します。

```sh
docker compose up --build -d
docker compose ps
```

利用者向け API は AI Server の `http://localhost:8000` です。Build Server の内部 API は AI Server が呼び出し、完成した ZIP も AI Server 経由で配信します。

## API仕様

API の詳細な仕様は[こちら](docs/spec.md)を参照してください。機械可読な定義は [OpenAPI](api/openapi.yaml) にあります。
