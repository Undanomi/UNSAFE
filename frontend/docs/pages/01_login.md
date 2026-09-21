# ログイン画面

## 基本情報

| 項目 | 内容 |
| --- | --- |
| 対応 Issue | [#23: フロント／タイトル画面の機能設計](https://github.com/Undanomi/SLSG/issues/23) |
| ルート | `/login` |
| アクセス条件 | 未認証の利用者が表示する。認証済みの場合は `/machines` へ遷移する。 |
| 目的 | 利用者を認証し、マシン一覧の利用を開始できる状態にする。 |
| 仕様状態 | 確定。Firebase AuthenticationによるGoogle SSOを使用する。 |

## 認証方式

Firebase AuthenticationによるGoogle SSOだけを提供する。ブラウザでGoogle認証を完了した後、Firebase ID tokenをBFFへ送り、BFFが検証済みのFirebase Session Cookieへ交換する。以後の画面アクセスとBFF処理ではSession Cookieを認証根拠とする。

メールアドレスとパスワードによる登録、保存、再設定および認証は提供しない。認証キャンセルまたは失敗時は`/login`に留まり、再試行できるようにする。

## 表示要素

- サービス名またはタイトル
- 「Google でログイン」ボタン
- プライバシーポリシーへのリンク
- 認証失敗時に表示する共通エラーメッセージ

認証失敗の詳細は画面に出さず、再試行可能な共通メッセージを表示する。

## 操作と遷移

| 操作 | 結果 |
| --- | --- |
| 「Google でログイン」を選択 | Google認証を開始する。BFFでのSession Cookie発行成功後は `/machines` へ遷移する。 |
| 「プライバシーポリシー」を選択 | `/privacy` へ遷移する。 |
| 認証失敗またはキャンセル | 画面遷移せず、共通エラーを表示して再試行可能にする。 |
| すでに認証済みでアクセス | `/machines` へ遷移する。 |

## 画面状態

| 状態 | 表示・操作 |
| --- | --- |
| 初期 | Googleログインボタンを表示する。 |
| 認証中 | 二重送信を防ぐためGoogleログインボタンを無効化する。 |
| 認証失敗 | 共通エラーを表示し、再入力・再送信できるようにする。 |
| 認証済み | マシン一覧へ遷移する。 |

## 実装時の責務

- ログイン状態の確認は画面表示時に行う。
- Google認証の操作状態、認証エラー、送信中の状態はClient Componentで扱う。
- ID tokenの検証、ユーザー初期作成、Session Cookieの発行はServer Actionを経由してBFFで行う。
- 認証必須ルートの早期判定はProxyで行い、Server Action、Route Handler、PostgreSQLアクセス時もBFFでSession Cookieを検証する。
