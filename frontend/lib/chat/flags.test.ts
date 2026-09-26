import assert from "node:assert/strict"
import test from "node:test"
import { resolveMachineFlag } from "./flags"

test("uses the AI flag when flag selection was omitted", () => {
  assert.equal(resolveMachineFlag(null, "  flag{generated}  "), "flag{generated}")
})

test("discards the AI flag when the flag was explicitly disabled", () => {
  assert.equal(resolveMachineFlag(false, "flag{unexpected}"), "")
})

test("keeps an explicitly requested AI flag", () => {
  assert.equal(resolveMachineFlag(true, "flag{requested}"), "flag{requested}")
})

test("uses an empty string when the AI did not return a flag", () => {
  assert.equal(resolveMachineFlag(null, null), "")
})
