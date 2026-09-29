import assert from "node:assert/strict"
import test from "node:test"
import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { ActiveSessionLimitPanel } from "./active-session-limit-panel"

test("shows every active chat as a link when the machine limit is reached", () => {
  const html = renderToStaticMarkup(
    createElement(ActiveSessionLimitPanel, {
      notice: {
        message: "同時に作成できるマシンは2つまでです。",
        activeChats: [
          { id: "session-one", name: "Web 演習" },
          { id: "session-two", name: "Linux 演習" },
        ],
      },
    }),
  )

  assert.match(html, /同時に作成できるマシンは2つまでです。/)
  assert.match(html, /href="\/machines\/chat\/session-one"[^>]*>Web 演習<\/a>/)
  assert.match(html, /href="\/machines\/chat\/session-two"[^>]*>Linux 演習<\/a>/)
})
