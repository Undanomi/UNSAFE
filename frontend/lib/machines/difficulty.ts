import type { MachineDifficulty } from "@/types/machine-list"
import type { MachineRecord } from "@/types/postgres"

export const MACHINE_LEVELS = ["very_easy", "easy", "medium", "hard"] as const

export const MACHINE_DIFFICULTY_LABELS: Record<MachineRecord["level"], MachineDifficulty> = {
  very_easy: "Very Easy",
  easy: "Easy",
  medium: "Medium",
  hard: "High",
}

const LEVEL_BY_DIFFICULTY: Record<MachineDifficulty, MachineRecord["level"]> = {
  "Very Easy": "very_easy",
  Easy: "easy",
  Medium: "medium",
  High: "hard",
}

export function toMachineLevel(difficulty: MachineDifficulty): MachineRecord["level"] {
  return LEVEL_BY_DIFFICULTY[difficulty]
}

export function toMachineDifficulty(level: MachineRecord["level"]): MachineDifficulty {
  return MACHINE_DIFFICULTY_LABELS[level]
}
