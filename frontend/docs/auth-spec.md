# 認証方針

## 方針

認証は Firebase Authentication の Google ログインを利用する。ブラウザは Google ログインで取得した ID トークンだけを Next.js に渡し、アプリケーションの認証状態は Firebase Session Cookie で管理する。

PostgreSQL にはブラウザから直接アクセスしない。データ操作と認可は Next.js の BFF（Server Action、Route Handler、Service）で行う。

## 認証フロー

1. ブラウザで Google ログインを実行する。
2. 取得した ID トークンを `createSessionAction` に送る。
3. `createSessionService` が ID トークンを検証し、認証時刻が 1 分以内であることを確認する。
4. Service が有効期限24時間の Firebase Session Cookie を発行し、Action が `slsg-session` として保存する。ブラウザ側のCookieには `Max-Age` と `Expires` を設定せず、セッションCookieとする。ただし、ブラウザのセッション復元機能でCookieが復元される場合があるため、ブラウザ終了によるログアウトは保証しない。サーバー側では発行から24時間で認証を無効とする。操作を続けても有効期限は延長せず、期限切れ後は再ログインを必要とする。`HttpOnly`、`SameSite=Lax`、本番環境では `Secure` とする。
5. 初回ログイン時はPostgreSQLの `users` テーブルへFirebase UIDを主キーとするユーザーを作成する。

ログアウト時は Session Cookie を削除する。クライアント側の Firebase Auth の状態はログイン後に破棄し、認証状態の正本を Cookie に一本化する。

## ルート保護

`/machines`、`/profile`、`/users` 配下は認証必須とする。未認証または無効な Cookie でアクセスした場合は `/login` にリダイレクトし、無効な Cookie は削除する。認証済み利用者が `/login` にアクセスした場合は `/machines` にリダイレクトする。

各 BFF の更新・参照処理でも、認証用Serviceを通じて利用者本人の権限を確認する。ルート保護だけを認可の根拠にしない。

## 責務と命名

Server Action は入力の軽い検証、認証・認可の実行、Service呼び出し、UI向けのエラーハンドリング、CookieやリダイレクトなどNext.js固有のHTTP操作にとどめる。Actionの公開関数名は `〜Action` とする。

Service は Firebase Authentication、PostgreSQLなど下流システムとの通信と、複数処理のオーケストレーションを担う。Service を定義するモジュールには必ず `import "server-only"` を記述し、Client Component から誤って import した場合にビルド時に検出できるようにする。外部から呼ぶServiceの公開関数名は `〜Service` とする。接続取得関数や値を組み立てる関数、非公開ヘルパーにはこの接尾辞を付けない。

## PostgreSQL と秘密情報

PostgreSQLは外部へポートを公開せず、BFF専用ネットワークからだけ接続する。接続文字列はサーバー専用の `DATABASE_URL` で渡し、`NEXT_PUBLIC_` 付きの変数、クライアントコード、リポジトリに含めない。Firebase Admin SDKは認証専用としてサーバー側で使用する。

## 設定

Google プロバイダーを Firebase Authentication で有効化し、開発・公開環境のドメインを承認済みドメインに登録する。必要な環境変数は `.env.example` を参照する。
