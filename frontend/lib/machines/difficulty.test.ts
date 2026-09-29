import assert from "node:assert/strict"
import test from "node:test"
import { toMachineDifficulty, toMachineLevel } from "./difficulty"
import {
  type MachineListItem,
  machineListHref,
  parseMachineListQuery,
  selectMachinePage,
} from "./list-query"

test("keeps Very Easy distinct from Easy when saving and displaying a machine", () => {
  assert.equal(toMachineLevel("Very Easy"), "very_easy")
  assert.equal(toMachineDifficulty("very_easy"), "Very Easy")
  assert.equal(toMachineLevel("Easy"), "easy")
  assert.equal(toMachineDifficulty("easy"), "Easy")
})

test("filters Very Easy machines without including Easy machines", () => {
  const query = parseMachineListQuery({ level: ["very_easy"] })
  const machines: MachineListItem[] = (["very_easy", "easy"] as const).map((level, index) => ({
    id: String(index),
    name: `machine-${index}`,
    description: "",
    tags: [],
    level,
    published: true,
    status: "ready",
    created_at: "2026-09-29T00:00:00.000Z",
    authorId: "author",
    author: "Author",
    authorAvatarUrl: "",
    isOwned: false,
    isSolved: false,
  }))

  assert.deepEqual(query.level, ["very_easy"])
  assert.equal(machineListHref(query), "/machines?level=very_easy")
  assert.deepEqual(
    selectMachinePage(machines, query).machines.map((machine) => machine.level),
    ["very_easy"],
  )
})
