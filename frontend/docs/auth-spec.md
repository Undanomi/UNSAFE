# 認証方針

## 方針

認証は Firebase Authentication の Google ログインを利用する。ブラウザは Google ログインで取得した ID トークンだけを Next.js に渡し、アプリケーションの認証状態は Firebase Session Cookie で管理する。

Firestore にはブラウザから直接アクセスしない。データ操作と認可は Next.js の BFF（Server Action、Route Handler、Service）で行い、サーバー側の Firebase Admin SDK から Firestore へアクセスする。

## 認証フロー

1. ブラウザで Google ログインを実行する。
2. 取得した ID トークンを `createSessionAction` に送る。
3. `createSessionService` が ID トークンを検証し、認証時刻が 5 分以内であることを確認する。
4. Service が Firebase Session Cookie を発行し、Action が `slsg-session` として保存する。`HttpOnly`、`SameSite=Lax`、本番環境では `Secure` とする。
5. 初回ログイン時はFirebase側で `users/{uid}` ドキュメントを作成する。

ログアウト時は Session Cookie を削除する。クライアント側の Firebase Auth の状態はログイン後に破棄し、認証状態の正本を Cookie に一本化する。

## ルート保護

`/machines`、`/profile`、`/users` 配下は認証必須とする。未認証または無効な Cookie でアクセスした場合は `/login` にリダイレクトし、無効な Cookie は削除する。認証済み利用者が `/login` にアクセスした場合は `/machines` にリダイレクトする。

各 BFF の更新・参照処理でも、認証用Serviceを通じて利用者本人の権限を確認する。ルート保護だけを認可の根拠にしない。

## 責務と命名

Server Action は入力の軽い検証、認証・認可の実行、Service呼び出し、UI向けのエラーハンドリング、CookieやリダイレクトなどNext.js固有のHTTP操作にとどめる。Actionの公開関数名は `〜Action` とする。

Service は Firebase、Firestoreなど下流システムとの通信と、複数処理のオーケストレーションを担う。Service を定義するモジュールには必ず `import "server-only"` を記述し、Client Component から誤って import した場合にビルド時に検出できるようにする。外部から呼ぶServiceの公開関数名は `〜Service` とする。接続取得関数や値を組み立てる関数、非公開ヘルパーにはこの接尾辞を付けない。

## Firestore と秘密情報

Firestore Security Rules はブラウザからの read/write をすべて拒否する。Admin SDK はサーバー専用とし、サービスアカウントのメールアドレスと秘密鍵は `FIREBASE_ADMIN_*` 環境変数で渡す。これらを `NEXT_PUBLIC_` 付きの変数、クライアントコード、リポジトリに含めない。

Firebase Console で管理している Firestore Rules と、リポジトリの `firestore.rules` は同じ内容を保つ。CLI で反映する場合は、対象プロジェクトを確認した上で `firebase deploy --only firestore:rules --project <PROJECT_ID>` を実行する。

## 設定

Google プロバイダーを Firebase Authentication で有効化し、開発・公開環境のドメインを承認済みドメインに登録する。必要な環境変数は `.env.example` を参照する。
