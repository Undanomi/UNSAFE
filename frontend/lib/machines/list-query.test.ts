import assert from "node:assert/strict"
import test from "node:test"
import {
  type MachineListItem,
  machineListHref,
  parseMachineListQuery,
  selectMachinePage,
} from "./list-query"

function machine(id: string, name: string, tags: string[]): MachineListItem {
  return {
    id,
    name,
    tags,
    description: "",
    level: "easy",
    published: true,
    status: "ready",
    created_at: "2026-09-29T00:00:00.000Z",
    authorId: "author",
    author: "Author",
    authorAvatarUrl: "",
    isOwned: false,
    isSolved: false,
  }
}

test("tag links add selections, keep other conditions, and restart at page one", () => {
  const query = parseMachineListQuery({
    page: "3",
    q: "auth",
    level: ["easy", "medium"],
    owned: "1",
    solved: "no",
    sort: "asc",
    tag: "Web",
  })

  const taggedHref = machineListHref({ ...query, tags: [...query.tags, "Web セキュリティ"] }, 1)
  const taggedParams = new URL(taggedHref, "http://localhost").searchParams
  assert.equal(taggedParams.get("q"), "auth")
  assert.deepEqual(taggedParams.getAll("tag"), ["Web", "Web セキュリティ"])
  assert.deepEqual(taggedParams.getAll("level"), ["easy", "medium"])
  assert.equal(taggedParams.get("owned"), "1")
  assert.equal(taggedParams.get("solved"), "no")
  assert.equal(taggedParams.get("sort"), "asc")
  assert.equal(taggedParams.has("page"), false)

  const selected = parseMachineListQuery({
    q: "auth",
    tag: ["Web", "Web セキュリティ", "Web"],
    level: "easy",
  })
  assert.equal(
    machineListHref(selected, 2),
    "/machines?q=auth&tag=Web&tag=Web+%E3%82%BB%E3%82%AD%E3%83%A5%E3%83%AA%E3%83%86%E3%82%A3&level=easy&page=2",
  )
  assert.equal(
    machineListHref({ ...selected, tags: selected.tags.filter((tag) => tag !== "Web") }, 1),
    "/machines?q=auth&tag=Web+%E3%82%BB%E3%82%AD%E3%83%A5%E3%83%AA%E3%83%86%E3%82%A3&level=easy",
  )
  assert.equal(machineListHref({ ...selected, tags: [] }, 1), "/machines?q=auth&level=easy")
})

test("all selected tags match exactly while keyword matching remains partial", () => {
  const query = parseMachineListQuery({ q: "auth", tag: ["Web", "API"], level: "easy" })
  const items = [
    machine("exact", "Auth lab", ["Web", "API"]),
    machine("longer-tag", "Auth course", ["Web Security"]),
    machine("other-name", "Networking lab", ["Web"]),
    machine("missing-api", "Auth primer", ["Web"]),
  ]

  assert.deepEqual(
    selectMachinePage(items, query).machines.map((item) => item.id),
    ["exact"],
  )
})
