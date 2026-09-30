import type { RefObject } from "react"

type FlagHelpDialogProps = {
  dialogRef: RefObject<HTMLDialogElement | null>
}

export function FlagHelpDialog({ dialogRef }: FlagHelpDialogProps) {
  return (
    <dialog
      aria-labelledby="slsg-flag-help-title"
      className="slsg-flag-help-dialog"
      ref={dialogRef}
    >
      <div className="slsg-flag-help-dialog-header">
        <h2 id="slsg-flag-help-title">フラグとは？</h2>
        <button
          aria-label="フラグの説明を閉じる"
          className="slsg-flag-help-dialog-close"
          onClick={() => dialogRef.current?.close()}
          type="button"
        >
          ×
        </button>
      </div>

      <div className="slsg-flag-help-dialog-content">
        <section aria-labelledby="slsg-user-flag-help-title">
          <h3 id="slsg-user-flag-help-title">ユーザーフラグ</h3>
          <p>
            ユーザーフラグは、
            <strong>一般ユーザとして対象マシンへの侵入に成功したことを示す「答え」の文字列</strong>
            です。
          </p>
          <p>
            プレイヤーは、サービスやアプリケーションの脆弱性、設定ミスなどを利用して対象マシンにアクセスし、一般ユーザの権限で参照できる場所からフラグを探します。
          </p>
          <p>このフラグを取得することで、対象マシンへの最初の侵入に成功したことを確認できます。</p>
        </section>

        <hr />

        <section aria-labelledby="slsg-system-flag-help-title">
          <h3 id="slsg-system-flag-help-title">システムフラグ</h3>
          <p>
            システムフラグは、
            <strong>
              管理者権限を取得し、対象マシンを最終段階まで攻略したことを示す「答え」の文字列
            </strong>
            です。
          </p>
          <p>
            多くの場合、ユーザーフラグを取得したあとに、OSやソフトウェアの設定ミス、権限設定などを調査し、より高い権限への昇格を目指します。
          </p>
          <p>
            管理者権限を取得すると、通常のユーザではアクセスできない場所にあるシステムフラグを確認できるようになります。
          </p>
        </section>
      </div>
    </dialog>
  )
}
