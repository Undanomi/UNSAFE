# UNSAFE AI Server

## 概要

AI Server は、学習用マシンのシナリオと VM 構築用ソースを生成するサービスです。生成条件と進捗をセッションごとに保存し、ソースを検証してから Build Server にビルドを依頼します。完成したマシンは、AI Server が発行する一時的な URL からダウンロードできます。

## 起動方法

### AI Server と Build Server を一緒に起動する

リポジトリのルートにある Docker Compose を使います。この構成では AI Server、Build Server と、それぞれの PostgreSQL が起動します。フロントエンドは別のプロファイルなので、通常の `docker compose up` では起動しません。

**1. ビルドに必要なものを確認する**

VM のビルドには、Docker を実行する Linux ホストで `/dev/kvm` が使えることと、対象 OS のベースイメージが必要です。KVM は VM の実行を高速化する Linux の機能です。ベースイメージは VM の土台になるディスクファイルで、既定の `Debian 13.7.0` には次のファイルを用意します。

```text
build_server/builder/base_images/debian-13.7.0-amd64.qcow2
```

AI Server のイメージをビルドすると、パスワード解析を含む演習で使う `rockyou.txt` も取得されます。これはよく使われるパスワードの一覧です。手動で配置する必要はありません。

**2. 環境変数を設定する**

リポジトリのルートでテンプレートをコピーし、`.env` を編集します。

```sh
cp .env.example .env
stat -c '%g' /dev/kvm
```

`stat` の出力は KVM デバイスのグループ ID です。次の表に従って `.env` の値を設定してください。パスワードやトークンには、それぞれ `openssl rand -hex 32` などで生成した値を使えます。

| 変数 | 設定する値 |
| --- | --- |
| `AI_POSTGRES_PASSWORD` | AI Server 用 PostgreSQL のパスワード。 |
| `BUILD_POSTGRES_PASSWORD` | Build Server 用 PostgreSQL のパスワード。上とは別の値にする。 |
| `FRONTEND_POSTGRES_PASSWORD` | フロントエンド用 PostgreSQL のパスワード。フロントエンドを起動しない場合も、Compose の設定を読み込むために値が必要。 |
| `INTERNAL_API_TOKEN` / `BUILD_SERVER_TOKEN` | Build Server への内部リクエストを認証するトークン。**両方に同じ 32 文字以上の値**を設定する。 |
| `KVM_GID` | 上の `stat` で表示された数値。Build Server の worker が `/dev/kvm` を使うために必要。 |

AI による生成を使う場合は、選ぶプロバイダーに応じて次の値も `.env` に追加します。

| `AI_PROVIDER` | あわせて設定する変数 | 用途 |
| --- | --- | --- |
| `gemini` | `GEMINI_API_KEY` | Gemini でシナリオとソースを生成する。 |
| `openai` | `OPENAI_API_KEY` | OpenAI でシナリオとソースを生成する。 |
| `stub` | なし | API の接続確認用。AI による生成の代わりに固定の応答を使う。 |

`DOWNLOAD_SIGNING_SECRET` はダウンロード URL の署名鍵、`SOURCE_SANDBOX_TOKEN` は生成ソースの検証環境との通信に使うトークンです。Compose には開発用の既定値があります。共有環境で動かす場合は、どちらも 32 文字以上のランダムな値を `.env` に追加してください。

**3. 起動して確認する**

```sh
docker compose up --build -d
docker compose ps
curl http://localhost:8000/v1/health/ready
```

正常ならヘルスチェックは `{"status":"ok"}` を返します。API は `http://localhost:8000`、対話的な API 画面は `http://localhost:8000/docs` です。Build Server の API は Compose 内部の `http://server:8080` にあり、ホストへは公開されません。

### AI Server だけを起動する

AI Server の API だけを確認する場合は、専用の Compose 設定を使えます。リポジトリのルートでテンプレートをコピーしてから、`ai_server/.env` の値を編集してください。

```sh
cp ai_server/.env.example ai_server/.env
```

| 変数 | 設定する値 |
| --- | --- |
| `AI_POSTGRES_PASSWORD` | AI Server 用 PostgreSQL のパスワード。 |
| `BUILD_SERVER_TOKEN` | 32 文字以上のランダムな値。既定の例示値は必ず変更する。 |
| `AI_PROVIDER` と対応する API キー | Gemini または OpenAI を使う場合に設定する。接続確認だけなら `AI_PROVIDER=stub`。 |
| `AI_BUILD_SERVER_URL` | 別に起動した Build Server と連携するときに設定する、AI Server コンテナから到達可能な URL。 |

この Compose では Build Server は起動しません。マシンのビルドまで行う場合は、別の Build Server を用意し、その `INTERNAL_API_TOKEN` と `BUILD_SERVER_TOKEN` を同じ値にしてください。テンプレートの `DATABASE_URL` はホストから直接起動する場合の設定で、Compose では使用しません。共有環境では `DOWNLOAD_SIGNING_SECRET` と `SOURCE_SANDBOX_TOKEN` も変更してください。

```sh
docker compose --env-file ai_server/.env -f ai_server/compose.yml up --build -d
```

管理画面が必要な場合は、使用する `.env` に `SQLADMIN_USERNAME`、`SQLADMIN_PASSWORD`、`SQLADMIN_SESSION_SECRET` を設定します。ルートの Compose なら `docker compose --profile admin up --build -d`、AI Server 単体なら上の起動コマンドに `--profile admin` を追加してください。

## API仕様

API の詳細な仕様は[こちら](docs/spec.md)を参照してください。機械可読な定義は [OpenAPI](api/openapi.yaml) にあります。
