import assert from "node:assert/strict"
import test from "node:test"
import { createElement, createRef } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { FlagHelpDialog } from "./flag-help-dialog"

test("shows the user and system flag explanations", () => {
  const html = renderToStaticMarkup(
    createElement(FlagHelpDialog, {
      dialogRef: createRef<HTMLDialogElement>(),
    }),
  )

  assert.match(html, /aria-labelledby="slsg-flag-help-title"/)
  assert.match(html, /<h2 id="slsg-flag-help-title">フラグとは？<\/h2>/)
  assert.match(html, /<h3 id="slsg-user-flag-help-title">ユーザーフラグ<\/h3>/)
  assert.match(html, /一般ユーザとして対象マシンへの侵入に成功したことを示す/)
  assert.match(html, /<h3 id="slsg-system-flag-help-title">システムフラグ<\/h3>/)
  assert.match(html, /管理者権限を取得し、対象マシンを最終段階まで攻略したことを示す/)
  assert.match(html, /aria-label="フラグの説明を閉じる"/)
})
